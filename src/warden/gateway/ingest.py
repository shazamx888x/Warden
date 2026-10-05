"""Control W4: scan and mask documents before they are indexed.

Everything a retrieval system indexes is something the model will one day
read. So untrusted documents (candidate CVs, web pages) are scanned for
injection on the way in, and a flagged document is quarantined: it is never
indexed, so its hidden instruction can never reach the model. Everything that
is indexed has its personal data masked first.
"""

from __future__ import annotations

from warden import constants as C
from warden.backends.search import LocalIndex
from warden.gateway.pii import mask
from warden.gateway.shields import fast_scan


# region: ingest_scan
def ingest_scan(record: dict, guard, engine) -> dict:
    """Control W4: decide a document's fate BEFORE it is indexed.

    Untrusted documents (candidate uploads, web pages) are scanned for
    injection. If the fast rules fire or the classifier scores the text
    malicious, the document is QUARANTINED: it is not indexed, so its hidden
    instruction can never reach the model. Trusted documents are indexed after
    PII masking. Detection is not a boundary here: a flagged document is
    removed, not merely flavoured with a warning.
    """
    from warden.backends.offline_llm import normalise_for_model

    result = {"record": None, "quarantined": False, "reason": ""}
    text = record["text"]
    if record["source"] in C.UNTRUSTED_SOURCES:
        scanned = normalise_for_model(text)
        rules = fast_scan(scanned)
        verdict = guard.score(scanned)
        if rules or verdict.label == "malicious":
            result["quarantined"] = True
            result["reason"] = ("fast rules {} / injection score {}".format(
                rules, verdict.score))
            return result
    masked, _ = mask(text, engine)          # mask PII in whatever we index
    clean = dict(record)
    clean["text"] = masked
    result["record"] = clean
    return result


def build_secure_index(records, guard, engine):
    """Index only what survives the ingest scan. Returns (index, quarantined)."""
    index = LocalIndex()
    quarantined = []
    for record in records:
        outcome = ingest_scan(record, guard, engine)
        if outcome["quarantined"]:
            quarantined.append({"doc_id": record["doc_id"], "reason": outcome["reason"]})
        else:
            index.add(outcome["record"])
    return index, quarantined
# endregion: ingest_scan
