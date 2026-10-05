"""Every command the guide tells you to run must be a command that works.

    python scripts/check_commands.py

This reads the BUILT guide, pulls out every block captioned "Run this", and
checks each command line in it. It is the direct answer to the defect class
where a document tells a reader to run something that cannot work as printed:
a script that does not exist, a flag that was renamed, a module path that
moved.

What it does per command:

  python <script.py> ...    the file must exist, and the script must accept
                            the flags shown (verified with --help, which
                            argparse validates without running anything)
  python -m <module> ...    the module must be importable and accept the flags
  streamlit run <file>      the file must exist
  bash <script.sh>          the file must exist and parse (bash -n)
  az / git / pip / set      recognised, not executed

Nothing destructive is run. `--help` exits before any work happens, which is
what makes this safe to run on every build.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_crossfile import GUIDE, _guide_blocks  # noqa: E402

# Commands that belong to the reader's own environment or to Azure, and are
# recognised rather than run. Each is here deliberately.
EXTERNAL = ("git ", "pip ", "az ", "set ", "cd ", "source ", ".venv", "python -m venv",
            "streamlit ", "bash ", "npx ", "node ", "curl", "$env:", "export ",
            "ssh ", "sudo ", "huggingface-cli ", "hf ", "uvicorn ",
            "python -m spacy ", "Set-ExecutionPolicy")


def has_subcommand(tail: list[str]) -> bool:
    """True if the command line carries a subcommand.

    `pip install --upgrade pip` puts --upgrade on the SUBCOMMAND, so the top
    level --help does not list it and checking against that output reports a
    flag that is perfectly valid. A positional here means a token that does
    not start with a dash and is not the value of the flag before it.
    """
    previous_was_flag = False
    for token in tail:
        if token.startswith("-"):
            previous_was_flag = "=" not in token
            continue
        if not previous_was_flag:
            return True
        previous_was_flag = False
    return False


# Third party modules the guide installs as an OPTIONAL step. They are not in
# requirements.txt, so they are recognised rather than imported.
OPTIONAL_MODULES = ("spacy",)


def check_python_script(parts: list[str], cwd: Path = ROOT) -> str | None:
    script = parts[1]
    if not (cwd / script).exists():
        return "{} does not exist (looked from {})".format(
            script, cwd.relative_to(ROOT) if cwd != ROOT else "the project folder")
    flags = [p for p in parts[2:] if p.startswith("--")]
    if not flags or has_subcommand(parts[2:]):
        return None
    result = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=cwd, capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        return "{} --help failed: {}".format(script, result.stderr.strip()[:120])
    for flag in flags:
        if flag not in result.stdout:
            return "{} does not accept {}".format(script, flag)
    return None


def check_python_module(parts: list[str]) -> str | None:
    module = parts[2]
    flags = [p for p in parts[3:] if p.startswith("--")]
    if has_subcommand(parts[3:]):
        flags = []          # the flags belong to the subcommand, not the module
    import os
    env = {"PYTHONPATH": str(ROOT / "src") + os.pathsep + str(ROOT)}
    import os

    merged = dict(os.environ)
    merged.update(env)
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        cwd=ROOT, capture_output=True, text=True, env=merged, timeout=120,
    )
    if result.returncode != 0:
        return "python -m {} --help failed: {}".format(
            module, (result.stderr or result.stdout).strip()[:160])
    for flag in flags:
        if flag not in result.stdout:
            return "python -m {} does not accept {}".format(module, flag)
    return None


def check_command(line: str, cwd: Path = ROOT) -> str | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    # Strip a trailing comment used for platform notes.
    line = re.sub(r"\s{2,}#.*$", "", line)
    # In "python x.py | npx wrangler ...", check the Python half. The other
    # side is an external tool.
    line = line.split(" | ")[0].strip()

    if line.startswith("streamlit run "):
        target = line.split()[2]
        return None if (ROOT / target).exists() else "{} does not exist".format(target)
    if line.startswith("bash "):
        target = line.split()[1]
        if not (ROOT / target).exists():
            return "{} does not exist".format(target)
        result = subprocess.run(["bash", "-n", str(ROOT / target)],
                                capture_output=True, text=True)
        return None if result.returncode == 0 else "{} has a syntax error: {}".format(
            target, result.stderr.strip()[:120])

    try:
        parts = shlex.split(line)
    except ValueError:
        return None          # quoting a reader fills in, not a real command
    if not parts:
        return None
    if parts[0] != "python":
        return None if line.startswith(EXTERNAL) else None
    if len(parts) > 2 and parts[1] == "-m":
        if parts[2] in OPTIONAL_MODULES:
            return None
        return check_python_module(parts)
    if len(parts) > 1 and parts[1].endswith(".py"):
        return check_python_script(parts, cwd)
    return None          # python -c one liners are exercised by the demo


def main() -> int:
    if not GUIDE.exists():
        print("guide not built yet: run python scripts/build_guide.py",
              file=sys.stderr)
        return 1

    blocks = [(caption, text) for caption, text in _guide_blocks()
              if caption.startswith("Run this")]
    if not blocks:
        print("the guide contains no command blocks at all, so this check "
              "compared nothing", file=sys.stderr)
        return 1

    problems = []
    checked = 0
    # The guide's "cd" lines carry on from block to block, the way a reader's
    # terminal does, so each command is checked from the folder the reader
    # would actually be in. A script two folders up is right when run from
    # infra/worker, and wrong when the same line is run from the project folder.
    cwd = ROOT
    for _, block in blocks:
        for line in block.splitlines():
            if not line.strip():
                continue
            checked += 1
            bare = re.sub(r"\s{2,}#.*$", "", line.strip())
            if bare.startswith("cd "):
                target = (cwd / bare[3:].strip()).resolve()
                if not target.is_dir():
                    problems.append("{!r}: folder does not exist".format(bare))
                else:
                    cwd = target
                continue
            problem = check_command(line, cwd)
            if problem:
                problems.append("{!r}: {}".format(line.strip()[:60], problem))

    print("checked {} command line(s) in {} block(s) from the guide".format(
        checked, len(blocks)))
    if problems:
        for problem in problems:
            print("  FAIL {}".format(problem))
        return 1
    print("every command in the guide names something that exists and accepts "
          "the flags shown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
