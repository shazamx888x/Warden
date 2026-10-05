"""The target assistant, and the same assistant behind Warden.

NaiveAssistant is the target, built deliberately weak: it retrieves without
regard to permission, pastes everything into the prompt, and executes any tool
the model asks for. It is about one part in ten of the code, and it is what
most teams shipped.

Gateway is Warden. It wraps the SAME assistant without changing it, and runs
the eight controls in the order a request meets them:

  W1 fast rules   on the input, and on every retrieved document
  W2 classifier   Prompt Guard scores the input for injection
  W3 harm check   Llama Guard on the input
  W4 ingest scan  documents were scanned and PII-masked before indexing
  W5 permission   retrieval is filtered to the caller's access groups
  W6 output scan  the answer is scanned for identifiers and beacons
  W7 canary       the answer is checked for a system prompt leak
  W8 tool policy  every proposed tool call is allowed, held, or blocked

Both share one agent loop, so the comparison is honest: the only difference
between the two runs is the gateway.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from warden import constants as C
from warden.app.tools import ToolRuntime, tool_schemas
from warden.backends.classifiers import get_llama_guard, get_prompt_guard
from warden.backends.offline_llm import get_model
from warden.backends.search import Hit, LocalIndex
from warden.gateway import canary as canary_mod
from warden.gateway.identity import Directory, NotAuthenticated, Principal
from warden.gateway.output import scan_output
from warden.gateway.pii import get_engine
from warden.gateway.harm import harm_block
from warden.gateway.injection import injection_block
from warden.gateway.permission import allowed_groups
from warden.gateway.shields import fast_scan, spotlight
from warden.policy.tool_policy import decide


@dataclass
class Reply:
    answer: str
    decision: str = C.POLICY_ALLOW
    reason: str = ""
    hits: list = field(default_factory=list)
    side_effects: list = field(default_factory=list)
    controls_acted: list = field(default_factory=list)
    blocked_tool_calls: list = field(default_factory=list)
    quarantined: list = field(default_factory=list)
    correlation_id: str = ""
    latency_ms: int = 0


def _context(hits: list) -> str:
    return "\n".join("[{}] {}. {}".format(h.doc_id, h.title, h.text)
                     for h in hits)


# region: naive_assistant
class NaiveAssistant:
    """RAG plus an agent, with no controls. Insecure on purpose."""

    def __init__(self, index: LocalIndex, model=None, directory=None):
        self.index = index
        self.model = model or get_model()
        self.directory = directory or Directory()
        # The naive assistant also carries a secret and canary in its system
        # prompt: that is WHY a prompt leak matters. It simply has nothing
        # watching for the leak, which is the point of the comparison.
        self.system = canary_mod.system_prompt()

    def ask(self, question: str, credential: str, requested_tools=None,
            web_inject: dict | None = None) -> Reply:
        principal = self.directory.resolve(credential, initiated_by_user=True)
        runtime = ToolRuntime(web_result=web_inject)
        # No permission filter: retrieve from the whole index.
        hits = self.index.query(question, allowed_groups=None,
                                top_k=C.RETRIEVAL_TOP_K)
        context = _context(hits)
        tools = tool_schemas(None)          # naive offers every tool to anyone
        answer = self._agent_loop(principal, context, question, tools, runtime,
                                  gateway=None)
        return Reply(answer=answer, hits=hits, side_effects=runtime.side_effects)

    def _agent_loop(self, principal, context, question, tools, runtime, gateway):
        seen_calls = set()
        text = ""
        system = gateway.system if gateway is not None else self.system
        for _ in range(C.AGENT_MAX_STEPS):
            result = self.model.complete(system, context, question, tools)
            text = result.text
            if not result.tool_calls:
                break
            progressed = False
            for call in result.tool_calls[:C.MAX_TOOL_CALLS_PER_TURN]:
                key = (call.name, tuple(sorted(call.arguments.items())))
                if key in seen_calls:
                    continue
                seen_calls.add(key)
                if gateway is not None:
                    out = gateway.handle_tool(call, principal, runtime)
                else:
                    out = runtime.run(call.name, call.arguments)
                if call.name == C.TOOL_WEB:
                    context += "\n[web] " + out       # web result re-enters context
                    progressed = True
                else:
                    text = (text + "\n" + out).strip()
            if not progressed:
                break
        return text
# endregion: naive_assistant


# W4 lives in warden.gateway.ingest. It is imported here too so the demo and
# the scripts can keep importing ingest_scan from this module.
from warden.gateway.ingest import build_secure_index, ingest_scan  # noqa: E402,F401


# region: gateway
class Gateway:
    """Warden: the eight controls around the naive assistant."""

    def __init__(self, index: LocalIndex, model=None, prompt_guard=None,
                 llama_guard=None, engine=None, directory=None,
                 quarantined=None):
        self.index = index                    # already ingest-scanned
        self.model = model or get_model()
        self.prompt_guard = prompt_guard or get_prompt_guard()
        self.llama_guard = llama_guard or get_llama_guard()
        self.engine = engine or get_engine()
        self.directory = directory or Directory()
        self.system = canary_mod.system_prompt()
        self._quarantined = quarantined or []
        self._naive = NaiveAssistant(index, self.model, self.directory)

    def handle_tool(self, call, principal, runtime) -> str:
        """W8: route a proposed tool call through the policy engine."""
        decision = decide(call.name, call.arguments, principal)
        runtime_decision = getattr(runtime, "_tool_log", None)
        if runtime_decision is None:
            runtime._tool_log = []
        runtime._tool_log.append(decision)
        if decision.outcome == C.POLICY_ALLOW:
            return runtime.run(call.name, call.arguments)
        if decision.outcome == C.POLICY_ASK:
            return "[held for approval: {}]".format(decision.reason)
        return "[blocked: {}]".format(decision.reason)

    def ask(self, question: str, credential: str, requested_tools=None,
            web_inject: dict | None = None) -> Reply:
        started = time.time()
        cid = str(uuid.uuid4())
        # `acted` records only controls that CHANGED the outcome, not every
        # stage that ran. Crediting a stage for merely executing overstates
        # the defence and hides which control did the real work (AegisAI's
        # control-attribution trap).
        acted = []

        # W1/W2/W3 on the input. Each returns immediately if it fires.
        if fast_scan(question):
            return self._blocked(cid, "W1", "input matched a fast rule", started)
        why = injection_block(question, self.prompt_guard)
        if why:
            return self._blocked(cid, "W2", why, started)
        why = harm_block(question, self.llama_guard)
        if why:
            return self._blocked(cid, "W3", why, started)

        try:
            principal = self.directory.resolve(credential, initiated_by_user=True)
        except NotAuthenticated as exc:
            return self._blocked(cid, "identity", "not authenticated: {}".format(exc),
                                 started)

        # W5: retrieve only what the caller may read. It ACTED if an unfiltered
        # query would have pulled in a document this caller is not entitled to.
        grants = allowed_groups(principal)
        hits = self.index.query(question, allowed_groups=grants,
                                top_k=C.RETRIEVAL_TOP_K)
        unfiltered = self.index.query(question, allowed_groups=None,
                                      top_k=C.RETRIEVAL_TOP_K)
        if grants is not None and any(h.acl_group not in grants for h in unfiltered):
            acted.append("W5")
        web = self._scan_web(web_inject)
        if web is not None and web.get("text", "").startswith("[web result removed"):
            acted.append("W4")
        context = spotlight(_context(hits))

        runtime = ToolRuntime(web_result=web)
        tools = tool_schemas(principal.role)
        raw = self._naive._agent_loop(principal, context, question, tools, runtime,
                                      gateway=self)

        # W6 output scan and W7 canary.
        pii_cleared = principal.role in (C.ROLE_PAYROLL, C.ROLE_HR_ADVISOR)
        scan = scan_output(raw, self.engine, pii_cleared)
        answer = scan["safe_answer"]
        leak, why = canary_mod.leaked(raw, self.system)
        blocked_reason = ""
        if leak:
            answer = "I cannot share that."
            blocked_reason = "W7: " + why
            acted.append("W7")
        elif scan["findings"]:
            blocked_reason = "W6: " + "; ".join(scan["findings"])
            acted.append("W6")

        tool_log = getattr(runtime, "_tool_log", [])
        if any(d.outcome != C.POLICY_ALLOW for d in tool_log):
            acted.append("W8")

        latency = int((time.time() - started) * 1000)
        return Reply(
            answer=answer,
            decision=C.POLICY_BLOCK if leak else C.POLICY_ALLOW,
            reason=blocked_reason,
            hits=hits, side_effects=runtime.side_effects,
            controls_acted=sorted(set(acted)),
            blocked_tool_calls=[d.__dict__ for d in tool_log
                                if d.outcome != C.POLICY_ALLOW],
            quarantined=self._quarantined,
            correlation_id=cid, latency_ms=latency)

    def _scan_web(self, web_inject):
        if web_inject is None:
            return None
        outcome = ingest_scan(web_inject, self.prompt_guard, self.engine)
        if outcome["quarantined"]:
            return {"text": "[web result removed by Warden: {}]".format(
                outcome["reason"])}
        return outcome["record"]

    def _blocked(self, cid, control, reason, started):
        return Reply(
            answer="Warden blocked this request.",
            decision=C.POLICY_BLOCK, reason="{}: {}".format(control, reason),
            controls_acted=[control], correlation_id=cid,
            latency_ms=int((time.time() - started) * 1000))
# endregion: gateway
