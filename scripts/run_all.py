"""Produce every number the guide, deck and README quote, in one run.

    python scripts/run_all.py                 # offline, no key needed
    python scripts/run_all.py --backend cloudflare

Order matters: generate the corpus first, then measure it. Each stage writes
its own JSON into results/, and this gathers the headline figures into
results/manifest.json. The guide builder reads manifest.json and nothing else,
so a figure in the document cannot disagree with the run that produced it. A
missing stage fails the build rather than printing a stale value.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from warden import constants as C  # noqa: E402
from warden import cost as cost_mod  # noqa: E402
from eval.build_attacks import counts as probe_counts  # noqa: E402

STAGES = [
    ("corpus", [sys.executable, "data/generator/generate_corpus.py", "--out", "data/corpus"], False),
    ("demo", [sys.executable, "-m", "warden.demo"], False),
    ("redteam", [sys.executable, "eval/redteam.py", "--target", "both"], True),
    ("utility", [sys.executable, "eval/utility.py"], True),
    ("pii", [sys.executable, "eval/pii_eval.py", "--engine", "presidio"], False),
    ("pii_regex", [sys.executable, "eval/pii_eval.py", "--engine", "regex"], False),
]


def run(name, command, takes_backend, backend):
    import os

    if takes_backend:
        command = command + ["--backend", backend]
    print("\n>>> {}{}".format(name, " (backend {})".format(backend) if takes_backend else ""))
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    started = time.time()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
    sys.stdout.write(result.stdout)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        raise SystemExit("stage {} failed ({})".format(name, result.returncode))
    return {"stage": name, "seconds": round(time.time() - started, 2)}


def load(path):
    file = ROOT / path
    if not file.exists():
        raise SystemExit("expected {} after the run".format(path))
    return json.loads(file.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run every Warden measurement")
    ap.add_argument("--backend", default="offline")
    ap.add_argument("--out", default="results/manifest.json")
    args = ap.parse_args(argv)

    timings = [run(n, c, b, args.backend) for n, c, b in STAGES]
    # Pass an empty list so cost.py does not read run_all's own flags
    # (such as --backend cloudflare) off the command line.
    cost_mod.main([])

    corpus = load("data/corpus/manifest.json")
    demo = load("results/demo.json")
    naive = load("results/redteam_naive.json")
    gateway = load("results/redteam_gateway.json")
    compare = load("results/redteam_compare.json")
    utility = load("results/utility.json")
    # Presidio is optional. Without it, pii_eval.py measures the regex engine
    # instead and writes only pii_regex.json, so fall back to that rather than
    # stopping. The manifest's pii.engine says which engine was measured.
    if (ROOT / "results/pii_presidio.json").exists():
        pii = load("results/pii_presidio.json")
    else:
        print("Presidio is not installed, so the PII numbers are from the "
              "regex engine. That's fine: see the optional step in chapter 3.")
        pii = load("results/pii_regex.json")
    pii_regex = load("results/pii_regex.json")
    cost = load("results/cost.json")

    manifest = {
        "project": C.PROJECT_NAME,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "backend": args.backend,
        "python": sys.version.split()[0],
        "docs_checked_date": C.DOCS_CHECKED_DATE,
        "timings": timings,
        "corpus": corpus,
        "controls": [{"id": cid, "key": key, "purpose": p} for cid, key, p in C.CONTROLS],
        "roles": C.ROLES,
        "tools": C.TOOLS,
        "probe_counts": probe_counts(),
        "thresholds": {
            "classifier_threshold": C.CLASSIFIER_THRESHOLD,
            "retrieval_top_k": C.RETRIEVAL_TOP_K,
            "payroll_ask_above_gbp": C.PAYROLL_ASK_ABOVE_GBP,
            "payroll_block_above_gbp": C.PAYROLL_BLOCK_ABOVE_GBP,
            "redteam_max_success_rate": C.REDTEAM_MAX_SUCCESS_RATE,
            "utility_min_correct_rate": C.UTILITY_MIN_CORRECT_RATE,
        },
        "redteam": {
            "naive_breach": naive["breached"],
            "naive_total": naive["total"],
            "naive_breach_rate": naive["breach_rate"],
            "naive_exposure_rate": naive["exposure_rate"],
            "naive_dev_rate": naive["dev"]["rate"],
            "naive_held_rate": naive["held_out"]["rate"],
            "gateway_breach": gateway["breached"],
            "gateway_total": gateway["total"],
            "gateway_breach_rate": gateway["breach_rate"],
            "gateway_exposure_rate": gateway["exposure_rate"],
            "gateway_dev_rate": gateway["dev"]["rate"],
            "gateway_held_rate": gateway["held_out"]["rate"],
            "newly_blocked": compare["newly_blocked"],
            "still_succeeding": compare["still_succeeding"],
            "latency_ms_median": gateway["latency_ms_median"],
            "naive_latency_ms_median": naive["latency_ms_median"],
            "latency_added_ms": gateway["latency_ms_median"] - naive["latency_ms_median"],
            "by_family": gateway["by_family"],
            "naive_by_family": naive["by_family"],
            "controls_acted": _controls_acted(gateway),
        },
        "utility": {
            "answer_rate": utility["answer_rate"],
            "correct_rate": utility["correct_rate"],
            "boundary_total": utility["boundary_total"],
            "boundary_held": utility["boundary_held"],
            "boundary_rate": utility["boundary_rate"],
            "naive_boundary_leaked": utility["naive_boundary_leaked"],
            "false_block": utility["false_block"],
        },
        "pii": {
            "engine": pii["engine"], "recall": pii["recall"],
            "regex_recall": pii_regex["recall"],
        },
        "cost": {
            "total_usd_per_month": cost["total_usd_per_month"],
            "per_request_usd": cost["per_request_usd"],
            "requests_per_day": cost["requests_per_day"],
            "budget_low": cost["budget_low"], "budget_high": cost["budget_high"],
            "within_budget": cost["within_budget"],
        },
        "demo": {
            "scene2_naive_breached": demo["scenes"]["scene2_naive_cv"]["breached"],
            "scene3_emails_sent": len(demo["scenes"]["scene3_warden_cv"]["emails_sent"]),
            "scene4_naive_leak": demo["scenes"]["scene4_boundary"]["naive_leak"],
            "scene4_warden_leak": demo["scenes"]["scene4_boundary"]["warden_leak"],
            "scene5_payroll_changes": len(demo["scenes"]["scene5_agent"]["payroll_changes"]),
        },
    }

    out = ROOT / args.out
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    r = manifest["redteam"]
    u = manifest["utility"]
    print("\n" + "=" * 70)
    print("HEADLINE NUMBERS (backend: {})".format(args.backend))
    print("=" * 70)
    print("  corpus                 {} documents".format(corpus["documents"]))
    print("  attacks                {} ({} dev, {} held out)".format(
        manifest["probe_counts"]["total"], manifest["probe_counts"]["dev"],
        manifest["probe_counts"]["held_out"]))
    print("  breach: naive          {}/{} ({:.1%})".format(
        r["naive_breach"], r["naive_total"], r["naive_breach_rate"]))
    print("  breach: behind Warden  {}/{} ({:.1%})".format(
        r["gateway_breach"], r["gateway_total"], r["gateway_breach_rate"]))
    print("      held out only      {:.1%} -> {:.1%}".format(
        r["naive_held_rate"], r["gateway_held_rate"]))
    print("  exposure (hostile text reached model): {:.1%} -> {:.1%}".format(
        r["naive_exposure_rate"], r["gateway_exposure_rate"]))
    print("  benign answered {:.1%}, correct {:.1%}; boundary held {:.1%}".format(
        u["answer_rate"], u["correct_rate"], u["boundary_rate"]))
    print("  latency added (median): {} ms".format(r["latency_added_ms"]))
    print("  cost: ${}/month (budget ${}-${})".format(
        manifest["cost"]["total_usd_per_month"], manifest["cost"]["budget_low"],
        manifest["cost"]["budget_high"]))
    print("\nWrote {}".format(out))
    return 0


def _controls_acted(gateway):
    from collections import Counter
    counter = Counter()
    for row in gateway["results"]:
        for control in row["controls_acted"]:
            counter[control] += 1
    return dict(sorted(counter.items()))


if __name__ == "__main__":
    raise SystemExit(main())
