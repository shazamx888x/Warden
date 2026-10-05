"""Control W8: the tool-call policy engine.

This is Warden's centre of gravity, and the thing that separates it from a
chat firewall. A RAG chatbot can only ever leak information. An agent can act:
it can email a document out of the company or change somebody's pay. So the
last line of defence is not "was the text suspicious" but "is this specific
action, with these specific arguments, allowed for this caller right now".

Every proposed tool call gets exactly one of three outcomes:

  allow   the action runs
  ask     the action is held for a human to approve (a payroll change over a
          threshold, an email to an address inside the company that is not the
          caller's own)
  block   the action is refused outright (an email to an outside domain, a
          payroll change over the hard ceiling, a tool the caller's role may
          not use at all)

The rules are DECLARATIVE and per tool, so the policy can be read and audited
without reading the agent. Argument checks are the whole point: an email tool
is not "allowed" or "blocked", it is allowed to the company domain and blocked
to anywhere else. The classifier can be fooled; a rule that an email may only
go to peoplecraft.example cannot be talked out of it by clever phrasing.
"""

from __future__ import annotations

from dataclasses import dataclass

from warden import constants as C


@dataclass
class ToolDecision:
    outcome: str            # allow | ask | block
    tool: str
    reason: str
    arguments: dict


# Which roles may invoke which tools at all. Deny by default: a tool not
# listed for a role is blocked before its arguments are even considered.
# region: tool_role_matrix
TOOL_ROLES = {
    C.TOOL_LOOKUP: C.ROLES,                       # any authenticated staff
    C.TOOL_WEB: C.ROLES,
    C.TOOL_EMAIL: [C.ROLE_HR_ADVISOR, C.ROLE_PAYROLL, C.ROLE_LINE_MANAGER,
                   C.ROLE_RECRUITER],
    C.TOOL_PAYROLL: [C.ROLE_PAYROLL],             # payroll changes: payroll only
}
# endregion: tool_role_matrix


# region: tool_policy_decide
def decide(tool: str, arguments: dict, principal) -> ToolDecision:
    """One tool call in, one of allow / ask / block out.

    `principal` has .role, .employee_id, .department and .initiated_by_user, a
    flag the caller sets True only for a tool the human actually asked for.
    An action the human did not ask for, proposed by the model after reading a
    document, is the injection case and is never silently allowed for a tool
    that changes anything.
    """
    role = principal.role

    if tool not in C.TOOLS:
        return ToolDecision(C.POLICY_BLOCK, tool, "unknown tool", arguments)

    if role not in TOOL_ROLES.get(tool, []):
        return ToolDecision(C.POLICY_BLOCK, tool,
                            "role {} may not use {}".format(role, tool), arguments)

    # A side-effect tool the user did not ask for is the agent-hijack case.
    # It is proposed only because the model read something. Hold or refuse it.
    if tool in C.SIDE_EFFECT_TOOLS and not getattr(principal, "initiated_by_user", False):
        return ToolDecision(
            C.POLICY_ASK, tool,
            "a {} was proposed by the model, not requested by the user; "
            "held for human approval".format(tool), arguments)

    if tool == C.TOOL_EMAIL:
        return _email_rules(arguments, principal)
    if tool == C.TOOL_PAYROLL:
        return _payroll_rules(arguments, principal)

    # Read-only tools with no dangerous arguments.
    return ToolDecision(C.POLICY_ALLOW, tool, "read-only tool, allowed", arguments)


def _email_rules(arguments: dict, principal) -> ToolDecision:
    to = str(arguments.get("to", "")).strip().lower()
    domain = to.rsplit("@", 1)[-1] if "@" in to else ""
    if domain != C.COMPANY_DOMAIN:
        return ToolDecision(
            C.POLICY_BLOCK, C.TOOL_EMAIL,
            "recipient {!r} is not on the company domain {}".format(
                to or "(none)", C.COMPANY_DOMAIN), arguments)
    return ToolDecision(C.POLICY_ALLOW, C.TOOL_EMAIL,
                        "internal recipient on the company domain", arguments)


def _payroll_rules(arguments: dict, principal) -> ToolDecision:
    try:
        amount = abs(float(arguments.get("amount_gbp", 0)))
    except (TypeError, ValueError):
        return ToolDecision(C.POLICY_BLOCK, C.TOOL_PAYROLL,
                            "amount is not a number", arguments)
    if amount > C.PAYROLL_BLOCK_ABOVE_GBP:
        return ToolDecision(
            C.POLICY_BLOCK, C.TOOL_PAYROLL,
            "GBP {:,.0f} is above the hard ceiling of GBP {:,}".format(
                amount, C.PAYROLL_BLOCK_ABOVE_GBP), arguments)
    if amount > C.PAYROLL_ASK_ABOVE_GBP:
        return ToolDecision(
            C.POLICY_ASK, C.TOOL_PAYROLL,
            "GBP {:,.0f} is above GBP {:,}, so it needs a second person".format(
                amount, C.PAYROLL_ASK_ABOVE_GBP), arguments)
    return ToolDecision(C.POLICY_ALLOW, C.TOOL_PAYROLL,
                        "within the auto-approved limit", arguments)
# endregion: tool_policy_decide
