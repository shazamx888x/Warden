"""Check this machine before you build on it.

    python scripts/preflight.py

The worst way to lose an afternoon is to get four chapters in and find that
step one was wrong. This checks the Python version, the packages, write
permissions and the corpus, and tells you what you can do right now. It never
fails on a missing cloud credential: the offline chapters don't need one.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import guide_chapters as ch  # noqa: E402

OK, BAD, NOTE = "  ok  ", " FAIL ", " note "

REQUIRED = [("docx", "python-docx", "building the guide"),
            ("pptx", "python-pptx", "building the deck"),
            ("PIL", "pillow", "building the thumbnail"),
            ("pytest", "pytest", "the tests")]
OPTIONAL = [("presidio_analyzer", "presidio-analyzer",
             "the trained PII engine (" + ch.ref("ingest") + ")"),
            ("transformers", "transformers",
             "the real Prompt Guard 2 (" + ch.ref("cloudflare") + ")"),
            ("requests", "requests", "the Cloudflare backend")]


def main() -> int:
    fails = 0
    print("Warden preflight")
    print("=" * 60)

    v = sys.version_info
    print("\nPython")
    if v >= (3, 11):
        print("{} {}.{}.{}".format(OK, v.major, v.minor, v.micro))
    else:
        fails += 1
        print("{} {}.{}.{} is too old; 3.11+ is needed".format(BAD, v.major, v.minor, v.micro))

    print("\nRequired packages")
    for mod, pkg, why in REQUIRED:
        try:
            importlib.import_module(mod)
            print("{} {:20s} {}".format(OK, pkg, why))
        except ImportError:
            fails += 1
            print("{} {:20s} {}   pip install {}".format(BAD, pkg, why, pkg))

    print("\nOptional packages")
    for mod, pkg, why in OPTIONAL:
        try:
            importlib.import_module(mod)
            print("{} {:20s} {}".format(OK, pkg, why))
        except ImportError:
            print("{} {:20s} not installed, needed for {}".format(NOTE, pkg, why))

    print("\nWrite permissions")
    for folder in ("results", "data/corpus", "docs"):
        target = ROOT / folder
        try:
            target.mkdir(parents=True, exist_ok=True)
            probe = target / ".preflight"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            print("{} {}".format(OK, folder))
        except OSError as exc:
            fails += 1
            print("{} {} not writable: {}".format(BAD, folder, exc))

    print("\nCorpus")
    corpus = ROOT / "data/corpus/documents.jsonl"
    if corpus.exists():
        n = sum(1 for _ in corpus.open(encoding="utf-8"))
        print("{} {} documents generated".format(OK, n))
    else:
        print("{} not generated yet. Run:".format(NOTE))
        print("        python data/generator/generate_corpus.py --out data/corpus")

    print("\n" + "=" * 60)
    if fails:
        print("{} blocking problem(s). Fix those and run this again.".format(fails))
        return 1
    print("You can do {} right now, with no cloud account.".format(ch.offline_range()))
    print("{} need a Cloudflare account.".format(ch.cloud_range().capitalize()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
