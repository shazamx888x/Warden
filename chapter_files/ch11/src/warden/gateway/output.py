"""Control W6: scan the answer before it reaches the caller.

Everything above is about keeping bad input away from the model. W6 assumes
all of that failed and asks a different question: is what the model just
produced safe to send to THIS caller? It catches three things:

  leaked identifiers   card numbers, NI numbers, bank details, API keys that
                       the caller is not cleared to see
  exfiltration beacons a link carrying data in its query string, the classic
                       way a model is talked into phoning home
  runaway output       a repetition bomb, the denial-of-wallet shape

Output scanning is the control that catches the attack nobody anticipated,
because it does not care how the answer was produced, only what it contains.
Input rules catch what you know; output checks catch what you do not.
"""

from __future__ import annotations

import re
from collections import Counter

from warden import constants as C
from warden.gateway.pii import RegexEngine, mask

# A bare URL is not a channel. A URL with a NON-EMPTY query value is: something
# has been appended to it, and that something is the payload.
LOADED_URL_RE = re.compile(r"https?://[^\s<>\)\]]*\?[^\s<>\)\]]*=[^\s<>\)\]&]+")
# Identifiers that must never reach a caller without clearance.
LEAKABLE = {"CARD", "NINO", "SORT_CODE", "ACCOUNT", "KEY"}


# region: output_scan
def scan_output(answer: str, engine: RegexEngine, pii_cleared: bool) -> dict:
    """Return findings and a safe-to-send answer.

    `pii_cleared` says whether this caller may see raw identifiers. Nobody is
    cleared for the API key: that is always masked.
    """
    findings = []
    kinds_present = {s.kind.replace("UK_", "") for s in engine.find(answer)}

    if "KEY" in kinds_present:
        findings.append("api key in answer")
    leaked = (kinds_present & LEAKABLE) - ({"KEY"})
    if leaked and not pii_cleared:
        findings.append("unmasked identifiers: " + ", ".join(sorted(leaked)))

    beacon = LOADED_URL_RE.search(answer)
    if beacon:
        findings.append("outbound link carrying data: " + beacon.group(0)[:60])

    hit, why = runaway_score(answer)
    if hit:
        findings.append(why)

    # Redact what we can rather than only refusing: an answer with one masked
    # NI number is still useful, an answer that is a beacon is not.
    mask_kinds = set(LEAKABLE) if not pii_cleared else {"KEY"}
    safe_answer, _ = mask(answer, engine, kinds=mask_kinds)
    if beacon:
        safe_answer = LOADED_URL_RE.sub("[link removed]", safe_answer)
    return {"findings": findings, "safe_answer": safe_answer}


def find_beacon(text: str) -> str | None:
    m = LOADED_URL_RE.search(text)
    return m.group(0) if m else None


def runaway_score(text: str) -> tuple:
    """A repetition bomb: one short phrase repeated far past any real use."""
    words = text.split()
    if len(words) < 200:
        return False, ""
    top, count = Counter(words).most_common(1)[0]
    if count > len(words) * 0.5:
        return True, "runaway repetition of {!r} ({} times)".format(top[:20], count)
    return False, ""
# endregion: output_scan
