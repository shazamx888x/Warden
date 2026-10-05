"""
Print the two values the Worker keeps as secrets: the canary and the system
prompt. They are the same ones the offline gateway uses, so a leak the
offline tests would catch is caught at the edge too.

    python scripts/worker_secrets.py --canary          # just the canary
    python scripts/worker_secrets.py --system-prompt   # just the system prompt

Pipe each one straight into Wrangler, from the infra/worker folder, so the
value never sits in your clipboard or your shell history:

    python ../../scripts/worker_secrets.py --canary | npx wrangler secret put CANARY

The values are synthetic, like everything in this project, but treat them as
secrets anyway: that's the habit the project is teaching.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from warden.gateway import canary  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Print the Worker's secret values")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--canary", action="store_true", help="print the canary")
    group.add_argument("--system-prompt", action="store_true",
                       help="print the system prompt")
    args = ap.parse_args(argv)
    print(canary.CANARY if args.canary else canary.system_prompt())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
