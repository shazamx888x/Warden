"""Run the attack corpus against both targets and score it honestly.

    python eval/redteam.py --target both --backend offline
    python eval/redteam.py --target gateway --fail-over 0.05   (the CI gate)

Two targets, one scorer:
  naive     the assistant with no controls
  gateway   the same assistant behind Warden

Running both in one pass is the point. "2 attacks succeeded" means nothing
until you know 30 succeeded before. Each probe runs against a CLEAN corpus plus
exactly its own one hostile document, so a probe can never be blocked by a
different attack's document and score as a pass (an AegisAI contamination
trap).

Results land in results/redteam_<target>.json and results/redteam_compare.json.
Every number the guide, deck and README quote comes from those files.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from warden import constants as C  # noqa: E402
from warden.app.assistant import Gateway, NaiveAssistant, build_secure_index  # noqa: E402
from warden.backends.classifiers import get_llama_guard, get_prompt_guard  # noqa: E402
from warden.backends.offline_llm import get_model  # noqa: E402
from warden.backends.search import LocalIndex  # noqa: E402
from warden.gateway.identity import Directory  # noqa: E402
from warden.gateway.pii import get_engine  # noqa: E402
from eval.build_attacks import all_probes  # noqa: E402
from eval.detectors import Evidence, breached, exposed  # noqa: E402


@dataclass
class ProbeResult:
    probe_id: str
    family: str
    goal: str
    vector: str
    held_out: bool
    breached: bool
    exposed: bool
    reason: str = ""
    decision: str = ""
    blocked_reason: str = ""
    controls_acted: list = field(default_factory=list)
    quarantined: int = 0
    reached_model: bool = True
    latency_ms: int = 0


def _clean_docs():
    docs = []
    with (ROOT / "data/corpus/documents.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                record = json.loads(line)
                if not record.get("is_hostile"):
                    docs.append(record)
    return docs


# region: run_target
def run_target(target: str, backend: str) -> dict:
    model = get_model(backend)
    engine = get_engine()
    guard = get_prompt_guard(backend)
    llama = get_llama_guard(backend)
    directory = Directory()
    clean = _clean_docs()

    naive_base = LocalIndex(records=clean)
    secure_base, base_quarantined = build_secure_index(clean, guard, engine)

    from warden.app.assistant import ingest_scan

    def without(base, doc_id):
        idx = LocalIndex()
        idx.records = [(r, c) for (r, c) in base.records if r["doc_id"] != doc_id]
        return idx

    results = []
    for probe in all_probes():
        web_inject = None
        naive_index = without(naive_base, probe.replaces) if probe.replaces \
            else naive_base.clone()
        secure_index = without(secure_base, probe.replaces) if probe.replaces \
            else secure_base.clone()
        probe_quarantined = 0
        if probe.vector == "indirect":
            if probe.family == "web_injection":
                web_inject = probe.planted_doc
            else:
                naive_index.plant(probe.planted_doc)
                # W4: scan the hostile doc before it joins the secure index.
                outcome = ingest_scan(probe.planted_doc, guard, engine)
                if outcome["quarantined"]:
                    probe_quarantined = 1
                else:
                    secure_index.add(outcome["record"])

        started = time.time()
        if target == "naive":
            app = NaiveAssistant(naive_index, model, directory)
            reply = app.ask(probe.question, probe.persona_id, web_inject=web_inject)
        else:
            app = Gateway(secure_index, model, guard, llama, engine, directory,
                          quarantined=base_quarantined)
            reply = app.ask(probe.question, probe.persona_id, web_inject=web_inject)
        latency = int((time.time() - started) * 1000)

        grants = C.grants_for(probe.persona_role, probe.persona_id,
                              directory.people.get(probe.persona_id, {}).get(
                                  "department", ""))
        ev = Evidence(reply.answer, reply.side_effects, reply.hits, grants,
                      probe.goal, probe.persona_role)
        did_breach, reason = breached(probe.goal, ev, engine)
        was_exposed, _ = exposed(ev)
        reached = not (reply.reason.startswith(("W1", "W2", "W3", "identity")))
        controls = list(reply.controls_acted)
        if probe_quarantined and "W4" not in controls:
            controls.append("W4")           # the planted CV was quarantined at ingest
        reply.controls_acted = sorted(set(controls))
        results.append(ProbeResult(
            probe_id=probe.probe_id, family=probe.family, goal=probe.goal,
            vector=probe.vector, held_out=probe.held_out, breached=did_breach,
            exposed=was_exposed, reason=reason, decision=reply.decision,
            blocked_reason=reply.reason[:160],
            controls_acted=reply.controls_acted,
            quarantined=probe_quarantined + (len(reply.quarantined) if False else 0),
            reached_model=reached, latency_ms=latency))
    return summarise(target, backend, results)
# endregion: run_target


# region: summarise
def summarise(target, backend, results) -> dict:
    def rate(subset, attr="breached"):
        return round(sum(getattr(r, attr) for r in subset) / len(subset), 4) \
            if subset else 0.0

    dev = [r for r in results if not r.held_out]
    held = [r for r in results if r.held_out]
    by_family = {}
    for fam in C.FAMILY_KEYS:
        subset = [r for r in results if r.family == fam]
        by_family[fam] = {"total": len(subset),
                          "breached": sum(r.breached for r in subset),
                          "rate": rate(subset)}
    latencies = sorted(r.latency_ms for r in results)
    return {
        "target": target, "backend": backend,
        "total": len(results),
        "breached": sum(r.breached for r in results),
        "breach_rate": rate(results),
        "exposed": sum(r.exposed for r in results),
        "exposure_rate": rate(results, "exposed"),
        "reached_model": sum(r.reached_model for r in results),
        "dev": {"total": len(dev), "breached": sum(r.breached for r in dev),
                "rate": rate(dev)},
        "held_out": {"total": len(held), "breached": sum(r.breached for r in held),
                     "rate": rate(held)},
        "by_family": by_family,
        "latency_ms_median": latencies[len(latencies) // 2] if latencies else 0,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": [asdict(r) for r in results],
    }
# endregion: summarise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the Warden red team")
    ap.add_argument("--target", choices=["naive", "gateway", "both"], default="both")
    ap.add_argument("--backend", default="offline")
    ap.add_argument("--out", default="results")
    ap.add_argument("--fail-over", type=float, default=None,
                    help="exit non-zero if the gateway breach rate exceeds this")
    args = ap.parse_args(argv)

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    targets = ["naive", "gateway"] if args.target == "both" else [args.target]

    summaries = {}
    for target in targets:
        summary = run_target(target, args.backend)
        (out / "redteam_{}.json".format(target)).write_text(
            json.dumps(summary, indent=2), encoding="utf-8")
        summaries[target] = summary
        print("{:8s} breach {}/{} ({:.1%})  exposure {:.1%}  dev {:.1%} / held {:.1%}"
              .format(target, summary["breached"], summary["total"],
                      summary["breach_rate"], summary["exposure_rate"],
                      summary["dev"]["rate"], summary["held_out"]["rate"]))

    if "naive" in summaries and "gateway" in summaries:
        n, g = summaries["naive"], summaries["gateway"]
        compare = {
            "backend": args.backend,
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "naive": {k: n[k] for k in ("breached", "total", "breach_rate",
                                        "exposure_rate", "dev", "held_out")},
            "gateway": {k: g[k] for k in ("breached", "total", "breach_rate",
                                          "exposure_rate", "dev", "held_out",
                                          "latency_ms_median")},
            "newly_blocked": sum(
                1 for a, b in zip(n["results"], g["results"])
                if a["breached"] and not b["breached"]),
            "still_succeeding": [
                {"probe_id": r["probe_id"], "family": r["family"],
                 "goal": r["goal"], "held_out": r["held_out"], "reason": r["reason"]}
                for r in g["results"] if r["breached"]],
        }
        (out / "redteam_compare.json").write_text(
            json.dumps(compare, indent=2), encoding="utf-8")
        print("\nblocked by Warden: {} of {} attacks that worked before".format(
            compare["newly_blocked"], n["breached"]))
        for item in compare["still_succeeding"]:
            print("  still: {} {} {}".format(
                item["probe_id"], "[held]" if item["held_out"] else "[dev] ",
                item["goal"]))

    if args.fail_over is not None and "gateway" in summaries:
        rate = summaries["gateway"]["breach_rate"]
        if rate > args.fail_over:
            print("\nFAIL: gateway breach rate {:.1%} exceeds {:.1%}".format(
                rate, args.fail_over), file=sys.stderr)
            return 1
        print("\nPASS: gateway breach rate {:.1%} within {:.1%}".format(
            rate, args.fail_over))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
