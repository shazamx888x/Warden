"""How well does the PII scan (W4 and W6) find personal data?

    python eval/pii_eval.py                 # Presidio if installed, else regex
    python eval/pii_eval.py --engine regex   # force the regex-only engine

Warden masks PII before a document is indexed (W4) and again on the way out
(W6). This measures recall: of the identifiers planted in the corpus, how many
does the engine catch. It reports the regex engine and the Presidio engine
separately, and it is honest that the UK identifiers (NI number, sort code,
account) are caught by regex either way; Presidio adds names and places.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from warden import constants as C  # noqa: E402
from warden.gateway.pii import PresidioEngine, RegexEngine  # noqa: E402


def build_gold():
    """Every identifier we planted, from the employees file, as (kind, value)."""
    gold = []
    with (ROOT / "data/corpus/employees.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            gold.append(("NINO", row["national_insurance_no"]))
            gold.append(("SORT_CODE", row["sort_code"]))
            gold.append(("EMAIL", row["email"]))
    return gold


def run(engine_name: str) -> dict:
    if engine_name == "presidio":
        try:
            engine = PresidioEngine()
        except Exception as exc:          # noqa: BLE001
            return {"engine": "regex", "presidio_error": str(exc)[:120],
                    **run("regex")}
    else:
        engine = RegexEngine()

    gold = build_gold()
    by_kind = {}
    for kind, value in gold:
        sentence = "For reference the {} on file is {} thank you.".format(
            {"NINO": "NI number", "SORT_CODE": "sort code",
             "EMAIL": "email"}[kind], value)
        found = {s.kind.replace("UK_", "") for s in engine.find(sentence)}
        rec = by_kind.setdefault(kind, {"total": 0, "found": 0})
        rec["total"] += 1
        if kind in found:
            rec["found"] += 1
    total = sum(r["total"] for r in by_kind.values())
    found = sum(r["found"] for r in by_kind.values())
    return {
        "engine": engine.name,
        "total": total,
        "found": found,
        "recall": round(found / total, 4) if total else 0.0,
        "by_kind": {k: {**v, "recall": round(v["found"] / v["total"], 4)}
                    for k, v in by_kind.items()},
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Warden PII detection eval")
    ap.add_argument("--engine", default="presidio", choices=["presidio", "regex"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--assert-recall", type=float, default=None)
    args = ap.parse_args(argv)

    result = run(args.engine)
    out = ROOT / (args.out or "results/pii_{}.json".format(result["engine"]))
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("PII engine {}: recall {:.1%} ({}/{})".format(
        result["engine"], result["recall"], result["found"], result["total"]))
    for kind, rec in result["by_kind"].items():
        print("  {:10s} {:.1%}".format(kind, rec["recall"]))
    if args.assert_recall is not None and result["recall"] < args.assert_recall:
        print("FAIL: recall below {:.1%}".format(args.assert_recall), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
