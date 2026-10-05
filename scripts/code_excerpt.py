"""Pull code into the guide from the real files, never from a typed copy.

This module is the reason the guide cannot drift from the code, and it is the
direct answer to the way the previous guide in this series failed: the
document held its own hand typed copy of the code, the two were maintained
separately, and the reader was the one who found out.

How it works
------------
Source files mark regions:

    # region: gateway_ask
    def ask(self, question, credential):
        ...
    # endregion: gateway_ask

The guide builder never contains a code string. It calls:

    excerpt("gateway_ask")

and gets back the exact text between those markers, dedented, with the marker
lines removed. Change the code and the next guide build carries the change.
Delete the region and the guide build fails rather than printing something
that no longer exists.

Three rules this enforces, each of which was a real defect elsewhere:

  1. Every region id is unique across the repository. Two regions with the
     same name is an error, not a silent first match win.
  2. Every region opened is closed, and closed with its own name. A mismatched
     endregion truncates a block, and a truncated code block in a guide looks
     exactly like a complete one.
  3. Every region that exists is used by the guide at least once, checked in
     the other direction by check_crossfile.py. A forward only check passes
     loudest when the guide contains no code at all.

Comment syntax is per file type, so shell, KQL and Python all work.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Directories that never hold guide source.
SKIP_DIRS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules", "results", "chapter_files",
    "data/corpus", ".pytest_cache", "docs",
}

# Extension to comment prefix. A region marker has to be a comment in its own
# language or the file stops being runnable, which would defeat the point.
COMMENT_PREFIX = {
    ".py": "#",
    ".sh": "#",
    ".yml": "#",
    ".yaml": "#",
    ".kql": "//",
    ".js": "//",
    ".ts": "//",
    ".sql": "--",
}

SCANNED_SUFFIXES = tuple(COMMENT_PREFIX)

# This file documents the marker format in its own docstring, so scanning it
# finds regions that are examples rather than code. Excluded by path, which is
# honest, rather than by trying to detect docstrings, which would be fragile.
SKIP_FILES = {"scripts/code_excerpt.py"}


@dataclass(frozen=True)
class Excerpt:
    region: str
    text: str
    path: str
    start_line: int
    end_line: int

    @property
    def language(self) -> str:
        return Path(self.path).suffix.lstrip(".")

    @property
    def source_label(self) -> str:
        """What the guide prints above the block, so a reader can find it."""
        return "{}  lines {} to {}".format(self.path, self.start_line, self.end_line)


class RegionError(Exception):
    pass


def _iter_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SCANNED_SUFFIXES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative in SKIP_FILES:
            continue
        if any(part in SKIP_DIRS for part in relative.split("/")):
            continue
        if any(relative.startswith(skip + "/") for skip in SKIP_DIRS):
            continue
        files.append(path)
    return sorted(files)


@lru_cache(maxsize=1)
def all_regions() -> dict[str, Excerpt]:
    """Every region in the repository, keyed by id. Raises on any malformation."""
    found: dict[str, Excerpt] = {}
    for path in _iter_files():
        prefix = re.escape(COMMENT_PREFIX[path.suffix])
        open_re = re.compile(r"^\s*{}\s*region:\s*(\S+)\s*$".format(prefix))
        close_re = re.compile(r"^\s*{}\s*endregion:\s*(\S+)\s*$".format(prefix))
        relative = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        open_stack: list[tuple[str, int]] = []
        for number, line in enumerate(lines, start=1):
            opened = open_re.match(line)
            if opened:
                open_stack.append((opened.group(1), number))
                continue
            closed = close_re.match(line)
            if not closed:
                continue
            name = closed.group(1)
            if not open_stack:
                raise RegionError(
                    "{}:{} closes region {!r} that was never opened".format(
                        relative, number, name
                    )
                )
            open_name, open_line = open_stack.pop()
            if open_name != name:
                raise RegionError(
                    "{}:{} closes region {!r} but {!r} was opened at line {}. "
                    "A mismatched marker truncates the block and a truncated "
                    "code block in a guide looks exactly like a complete "
                    "one.".format(relative, number, name, open_name, open_line)
                )
            if name in found:
                raise RegionError(
                    "region {!r} is defined twice: {} and {}:{}".format(
                        name, found[name].source_label, relative, open_line
                    )
                )
            # Regions may nest, so that one big region can print the whole
            # flow while smaller ones inside it print a single control. The
            # inner marker lines are stripped from the outer block: they are
            # scaffolding for the build, not part of the code a reader types.
            body_lines = [
                line
                for line in lines[open_line:number - 1]
                if not open_re.match(line) and not close_re.match(line)
            ]
            body = "\n".join(body_lines)
            found[name] = Excerpt(
                region=name,
                text=textwrap.dedent(body).strip("\n"),
                path=relative,
                start_line=open_line + 1,
                end_line=number - 1,
            )
        if open_stack:
            name, line_no = open_stack[-1]
            raise RegionError(
                "{}:{} opens region {!r} and never closes it".format(
                    relative, line_no, name
                )
            )
    return found


def excerpt(region: str) -> Excerpt:
    """The code for one region. Raises if it does not exist.

    Raising is the point. A guide builder that fell back to a placeholder
    would print a block that no longer matches the code, which is the exact
    failure this module exists to prevent.
    """
    regions = all_regions()
    if region not in regions:
        available = ", ".join(sorted(regions))
        raise RegionError(
            "no region named {!r}. The guide is asking for code that does not "
            "exist in the repository. Available regions: {}".format(region, available)
        )
    return regions[region]


def text(region: str) -> str:
    return excerpt(region).text


def verify_all(used: set[str]) -> list[str]:
    """Check both directions and return a list of problems.

    Forward: every region the guide asked for exists (already enforced by
    `excerpt` raising).
    Reverse: every region that exists is used by the guide. Without this, a
    region can be written, forgotten, and left to rot out of step with the
    prose that was supposed to describe it.
    """
    problems = []
    defined = set(all_regions())
    unused = sorted(defined - used)
    if unused:
        problems.append(
            "{} region(s) defined but never used by the guide: {}".format(
                len(unused), ", ".join(unused)
            )
        )
    missing = sorted(used - defined)
    if missing:
        problems.append(
            "{} region(s) used by the guide but not defined: {}".format(
                len(missing), ", ".join(missing)
            )
        )
    return problems


if __name__ == "__main__":
    regions = all_regions()
    print("{} regions across {} files".format(
        len(regions), len({r.path for r in regions.values()})))
    for name in sorted(regions):
        item = regions[name]
        print("  {:24s} {:3d} lines  {}".format(
            name, item.text.count("\n") + 1, item.source_label))
