"""Run every check, cheapest first.

    python scripts/check_all.py
    python scripts/check_all.py --allow-missing-guide     (before the first build)

Four layers: syntax, code regions, cross-file seams, unit tests. The red team
and the evaluations aren't run here (they take longer and need the corpus);
they live in scripts/run_all.py and in CI. This is the one to run after every
edit.
"""

from __future__ import annotations

import argparse
import compileall
import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def step_syntax():
    buf = io.StringIO()
    with redirect_stdout(buf):
        # Never legacy=True: a sourceless .pyc beside its source can shadow it
        # on import and serve code no longer on disk.
        ok = all(compileall.compile_dir(str(ROOT / f), quiet=1, force=True)
                 for f in ("src", "scripts", "eval", "data", "tests"))
    return bool(ok), buf.getvalue().strip()


def step_regions():
    sys.path.insert(0, str(ROOT / "scripts"))
    from code_excerpt import RegionError, all_regions
    try:
        regions = all_regions()
    except RegionError as exc:
        return False, str(exc)
    return True, "{} regions across {} files".format(
        len(regions), len({r.path for r in regions.values()}))


def step(cmd):
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-missing-guide", action="store_true")
    args = ap.parse_args(argv)

    cross = [sys.executable, "scripts/check_crossfile.py"]
    if args.allow_missing_guide:
        cross.append("--allow-missing-guide")

    steps = [
        ("syntax", step_syntax),
        ("code regions", step_regions),
        ("cross-file", lambda: step(cross)),
        ("guide commands", lambda: step([sys.executable, "scripts/check_commands.py"])),
        ("unit tests", lambda: step([sys.executable, "-m", "pytest", "tests", "-q"])),
    ]
    failed = []
    for name, fn in steps:
        print("\n=== {} ===".format(name))
        ok, out = fn()
        if out:
            print(out[-1500:])
        if not ok:
            failed.append(name)
            print("--> FAILED")
    print("\n" + "=" * 60)
    if failed:
        print("FAILED: {}".format(", ".join(failed)))
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
