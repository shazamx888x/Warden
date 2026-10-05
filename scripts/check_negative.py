"""Prove the checks fail when they should.

    python scripts/check_negative.py       (build the guide first)

A validator that has never been seen to fail is one you're trusting on faith.
This breaks each protected seam on purpose, one at a time, confirms the
matching check reports it, and puts the file back.

It edits real files and restores each in a finally block. Children run with
-B and PYTHONDONTWRITEBYTECODE, and every __pycache__ is purged after each
case, because a mutate/import/restore inside one second can otherwise leave
stale bytecode serving the mutated code (the stale-bytecode trap).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def child_env() -> dict:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + str(ROOT)
    return env


def purge_bytecode() -> None:
    for folder in ROOT.rglob("__pycache__"):
        shutil.rmtree(folder, ignore_errors=True)
    for stray in ROOT.rglob("*.pyc"):
        stray.unlink(missing_ok=True)


def run_check(only: str):
    r = subprocess.run(
        [sys.executable, "-B", "scripts/check_crossfile.py", "--only", only],
        cwd=ROOT, capture_output=True, text=True, env=child_env())
    return r.returncode, r.stdout + r.stderr


GUIDE = ROOT / "docs/Warden_Build_Guide.docx"


class Case:
    def __init__(self, name, path, check, mutate, expect, command=None,
                 needs_guide=False):
        self.name = name
        self.path = ROOT / path
        self.check = check
        self.mutate = mutate
        self.expect = expect
        self.command = command
        self.needs_guide = needs_guide

    def run(self):
        original = self.path.read_bytes()
        try:
            text = original.decode("utf-8")
            broken = self.mutate(text)
            if broken == text:
                return False, "mutation changed nothing; the anchor moved"
            self.path.write_bytes(broken.encode("utf-8"))
            if self.command:
                r = subprocess.run(self.command, cwd=ROOT, capture_output=True,
                                   text=True, env=child_env())
                code, out = r.returncode, r.stdout + r.stderr
            else:
                code, out = run_check(self.check)
            if code == 0:
                return False, "check {} passed on broken input".format(self.check)
            if self.expect not in out:
                return False, "failed for the wrong reason:\n{}".format(out.strip()[:300])
            return True, ""
        finally:
            self.path.write_bytes(original)
            purge_bytecode()


DASH = chr(0x2014)

CASES = [
    Case("an em dash in a source file", "src/warden/constants.py", "no_dashes",
         lambda t: t.replace('PROJECT_NAME = "Warden"',
                             'PROJECT_NAME = "Warden"  # ' + DASH + ' renamed'),
         "has an em dash"),
    Case("a banned phrase in the README", "README.md", "banned_phrases",
         lambda t: t.replace("An AI firewall for RAG and agents.",
                             "We leverage a robust firewall.", 1),
         "banned phrase"),
    Case("a phone number outside the fiction range", "data/corpus/employees.csv",
         "synthetic_identifiers_only",
         lambda t: t.replace("07700 900", "07911 123", 1),
         "outside the Ofcom drama range"),
    Case("the worker using a model name that is not in constants",
         "infra/worker/src/index.js", "worker_names_match_constants",
         lambda t: t.replace('"@cf/meta/llama-guard-3-8b"',
                             '"@cf/meta/llama-guard-9-99b"', 1),
         "does not use model"),
    Case("the held-out attacks changed after being frozen",
         "eval/templates_heldout.py", "heldout_frozen",
         lambda t: t.replace('"benign" or "malicious"', '"benign" or "malicious".', 1)
                    if '"benign" or "malicious"' in t
                    else t.replace("TEMPLATE_COUNT = len(TEMPLATES)",
                                   "TEMPLATE_COUNT = len(TEMPLATES)  # x"),
         "held-out templates changed"),
    Case("a control declared in constants but not used in code",
         "src/warden/constants.py", "controls_all_referenced",
         lambda t: t.replace('("W8", "tool_policy",', '("W9", "tool_policy",', 1),
         "never used in code"),
    Case("a region marker closed with the wrong name",
         "src/warden/gateway/shields.py", "code_regions",
         lambda t: t.replace("# endregion: fast_rules", "# endregion: spotlight", 1),
         "closes region"),
    Case("a reference to a file that does not ship", "README.md",
         "referenced_files_exist",
         lambda t: t.replace("scripts/run_all.py", "scripts/run_everything.py", 1),
         "does not exist"),
    Case("an attack naming a family that does not exist",
         "eval/templates_dev.py", "probe_families_exist",
         lambda t: t.replace('"direct_injection", "salary_leak"',
                             '"bogus_family", "salary_leak"', 1),
         "unknown family"),
    Case("a measured number changed without rebuilding the guide",
         "results/manifest.json", "guide_numbers_match_manifest",
         lambda t: t.replace('"gateway_exposure_rate": 0.225',
                             '"gateway_exposure_rate": 0.111'),
         "not a measured value", needs_guide=True),
    Case("the guide going stale against the code",
         "src/warden/gateway/shields.py", "guide_code_matches_source",
         # A comment line inside a printed region. The module still imports, so
         # the guide is now quoting a version of the code that no longer exists.
         lambda t: t.replace("Return the names of every fast rule that fires",
                             "Return the NAMES of every fast rule that fires", 1),
         "in no source region", needs_guide=True),
    Case("a chapter number typed into prose", "scripts/guide_content.py",
         "chapter_references",
         lambda t: t.replace(
             'b.h2("The one question this answers")',
             'b.h2("The one question this answers")\n    b.para("See chapter 5.")', 1),
         "types a chapter number into prose", needs_guide=True),
    Case("the guide telling you a flag that no longer exists",
         "eval/utility.py", "commands_in_the_guide",
         lambda t: t.replace('"--assert-answer-rate"', '"--require-answer-rate"', 1),
         "does not accept --assert-answer-rate",
         command=[sys.executable, "scripts/check_commands.py"], needs_guide=True),
]


def main() -> int:
    print("Negative tests: each check must FAIL on broken input")
    print("=" * 70)
    passed = 0
    skipped = 0
    failed = []
    guide_here = GUIDE.exists()
    for case in CASES:
        if case.needs_guide and not guide_here:
            skipped += 1
            print("  skip  {:52s} (guide not built)".format(case.name[:52]))
            continue
        if not case.path.exists():
            failed.append((case.name, "target missing: {}".format(case.path)))
            print("  MISS  {}".format(case.name))
            continue
        ok, reason = case.run()
        if ok:
            passed += 1
            print("  ok    {:52s} [{}]".format(case.name[:52], case.check))
        else:
            failed.append((case.name, reason))
            print("  FAIL  {:52s} [{}]".format(case.name[:52], case.check))
            print("          {}".format(reason))
    print("\n" + "=" * 70)
    print("{} of {} checks proved they fire{}".format(
        passed, len(CASES) - skipped,
        " ({} skipped, guide not built)".format(skipped) if skipped else ""))
    if failed:
        print("\nThese did not catch their breakage:")
        for name, reason in failed:
            print("  {}: {}".format(name, reason))
        return 1
    purge_bytecode()
    r = subprocess.run([sys.executable, "-B", "scripts/check_crossfile.py"],
                       cwd=ROOT, capture_output=True, text=True, env=child_env())
    if r.returncode != 0:
        print("\nWARNING: the tree did not come back clean:")
        print(r.stdout[-1500:])
        return 1
    print("working tree restored and all checks pass again")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
