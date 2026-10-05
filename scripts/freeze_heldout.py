"""Re-freeze the held-out attack templates.

    python scripts/freeze_heldout.py

The held-out set is frozen by hash so that nobody can quietly reword an attack
to make the defence look better after the fact (the whole point of a held-out
set). Run this ONLY when you have deliberately added new held-out attacks, and
say in the guide that the frozen date moved. Running it to silence a failing
check would defeat the mechanism.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    target = ROOT / "eval/templates_heldout.py"
    frozen = ROOT / "eval/FROZEN.json"
    data = json.loads(frozen.read_text(encoding="utf-8"))
    old = data["sha256"]
    new = hashlib.sha256(target.read_bytes()).hexdigest()
    if old == new:
        print("unchanged: {}".format(new))
        return 0
    data["sha256"] = new
    data["frozen_utc"] = time.strftime("%Y-%m-%d")
    frozen.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("re-froze {} -> {}".format(old[:12], new[:12]))
    print("Say in the guide that the held-out set was refrozen on {}.".format(
        data["frozen_utc"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
