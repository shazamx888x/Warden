"""Work out what Warden costs to run, from the prices in constants.py.

    python -m warden.cost

Nothing here is typed into the guide. The cost chapter reads results/cost.json,
which this writes, so the figure in the document is the figure this computed
from the published prices. Change a price in constants.py and the number moves.

The traffic assumption is stated out loud: a 400 person firm, lightly used, at
constants.COST_REQUESTS_PER_DAY requests a day. Every request makes one chat
call, one input safety check and one embedding lookup; roughly one in five also
runs a safety check on the answer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from warden import constants as C

ROOT = Path(__file__).resolve().parents[2]

# region: cost_assumptions
# Tokens per request. Deliberately generous so the estimate is not flattering.
TOKENS = {
    "chat_input": 900,      # system prompt + retrieved context + question
    "chat_output": 180,     # the answer
    "guard_input": 220,     # question, and sometimes the answer
    "guard_output": 12,     # "safe" or "unsafe\n<category>"
    "embed_input": 24,      # the query, embedded for retrieval
}
OUTPUT_GUARD_FRACTION = 0.2   # share of requests that also scan the answer


def per_request_usd(prices: dict) -> float:
    m = 1_000_000
    chat = (TOKENS["chat_input"] / m * prices["chat_usd_per_m_input"]
            + TOKENS["chat_output"] / m * prices["chat_usd_per_m_output"])
    guard_in = TOKENS["guard_input"] / m * prices["guard_usd_per_m_input"]
    guard_out = TOKENS["guard_output"] / m * prices["guard_usd_per_m_output"]
    guard = (guard_in + guard_out) * (1 + OUTPUT_GUARD_FRACTION)
    embed = TOKENS["embed_input"] / m * prices["embed_usd_per_m_input"]
    return chat + guard + embed
# endregion: cost_assumptions


def build() -> dict:
    p = C.PRICES
    per_req = per_request_usd(p)
    per_month = per_req * C.COST_REQUESTS_PER_DAY * 30
    requests_per_month = C.COST_REQUESTS_PER_DAY * 30

    lines = [
        ("Workers AI tokens (chat, safety, embeddings)",
         "usage", round(per_month, 2)),
        ("Cloudflare Workers (gateway)",
         "free tier: {:,} requests/day".format(p["workers_free_requests_per_day"]), 0.0),
        ("Vectorize (vector store)",
         "free tier: {:,} stored, {:,} queried dims/month".format(
             p["vectorize_free_stored_dims"],
             p["vectorize_free_queried_dims_per_month"]), 0.0),
        ("AI Gateway (logs, caching, rate limits)", "free", 0.0),
        ("Prompt Guard 2 on Oracle Always Free VM",
         "{} OCPU / {} GB, always free".format(C.ORACLE_OCPUS, C.ORACLE_MEMORY_GB), 0.0),
        ("Presidio (PII) and open red-team tools", "open source", 0.0),
    ]
    total = round(sum(cost for _, _, cost in lines), 2)
    return {
        "checked_date": C.DOCS_CHECKED_DATE,
        "requests_per_day": C.COST_REQUESTS_PER_DAY,
        "requests_per_month": requests_per_month,
        "per_request_usd": round(per_req, 6),
        "token_assumptions": TOKENS,
        "output_guard_fraction": OUTPUT_GUARD_FRACTION,
        "line_items": [{"item": i, "basis": b, "usd_per_month": c} for i, b, c in lines],
        "total_usd_per_month": total,
        "budget_low": C.MONTHLY_BUDGET_USD_LOW,
        "budget_high": C.MONTHLY_BUDGET_USD_HIGH,
        "within_budget": C.MONTHLY_BUDGET_USD_LOW <= total <= C.MONTHLY_BUDGET_USD_HIGH,
        "free_allowance_note": (
            "Workers AI gives {:,} free neurons a day, which covers a demo and "
            "most of a small pilot, so real spend is often 0.".format(
                p["workers_ai_free_neurons_per_day"])),
        "sources": [{"name": n, "url": u} for n, u in C.PRICE_SOURCES],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    argparse.ArgumentParser(description="Compute the Warden monthly cost").parse_args(argv)
    result = build()
    out = ROOT / "results/cost.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Warden monthly cost estimate (checked {})".format(result["checked_date"]))
    for item in result["line_items"]:
        print("  {:52s} {:>8}  {}".format(
            item["item"][:52], "${:.2f}".format(item["usd_per_month"]), item["basis"]))
    print("  {:52s} {:>8}".format("TOTAL per month",
                                  "${:.2f}".format(result["total_usd_per_month"])))
    print("  budget {} to {} USD/month: {}".format(
        result["budget_low"], result["budget_high"],
        "within" if result["within_budget"] else "OVER"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
