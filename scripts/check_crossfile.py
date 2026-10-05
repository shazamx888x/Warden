"""Cross-file checks: the seams where the project agrees with itself, or not.

Every check here exists because a defect of the same shape shipped in an
earlier guide in this series. Checks run in BOTH directions where that makes
sense: a forward-only "does every reference resolve" passes loudest when there
is nothing to resolve.

    python scripts/check_crossfile.py
    python scripts/check_crossfile.py --list
    python scripts/check_crossfile.py --only banned_phrases
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from warden import constants as C  # noqa: E402
from code_excerpt import RegionError, all_regions  # noqa: E402

GUIDE = ROOT / "docs/Warden_Build_Guide.docx"
BLUEPRINT = ROOT / "docs/Warden_Blueprint.md"
README = ROOT / "README.md"
MANIFEST = ROOT / "results/manifest.json"

TEXT_SUFFIXES = {".py", ".md", ".sh", ".yml", ".yaml", ".json", ".js", ".toml", ".txt"}
SKIP_PARTS = {".git", "__pycache__", ".venv", "node_modules", ".pytest_cache", "results", "chapter_files"}


def repo_text_files() -> list:
    out = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in SKIP_PARTS for part in rel.split("/")):
            continue
        if rel.startswith("data/corpus/"):
            continue
        out.append(path)
    return sorted(out)


SELF = "scripts/check_crossfile.py"


# === House style ===========================================================
def check_no_dashes() -> list:
    problems = []
    for path in repo_text_files():
        if path.relative_to(ROOT).as_posix() == SELF:
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for ch, name in (("—", "em dash"), ("–", "en dash")):
                if ch in line:
                    problems.append("{}:{} has an {}".format(
                        path.relative_to(ROOT).as_posix(), i, name))
    return problems


# Words and patterns that make prose read as machine written. The owner asked
# for plain, human writing, so these fail the build if they reach the guide,
# the README or the blueprint (the reader-facing text, not the code).
BANNED_PHRASES = [
    "delve", "robust", "leverage", "seamless", "seamlessly", "crucial",
    "landscape", "moreover", "furthermore", "in today's", "in today s",
    "realm", "utilize", "utilise", "plethora", "myriad", "tapestry",
    "navigating the", "at the end of the day", "it goes without saying",
    "unlock the", "supercharge", "game-changer", "game changer",
]
NOT_X_BUT_Y = re.compile(r"\bit(?:'s| is) not\b[^.]{0,40}\bit(?:'s| is)\b")
PROSE_FILES = ["README.md", "docs/Warden_Blueprint.md"]


def _reader_prose() -> list:
    """Reader-facing prose: the README, the blueprint, and the built guide."""
    chunks = []
    for rel in PROSE_FILES:
        path = ROOT / rel
        if path.exists():
            chunks.append((rel, path.read_text(encoding="utf-8")))
    if GUIDE.exists():
        chunks.append(("guide", "\n".join(
            p.text for p in _guide_paragraphs()
            if not any(r.font.name == C.FONT_CODE for r in p.runs if r.font.name))))
    return chunks


def check_banned_phrases() -> list:
    """No AI-tell words in reader-facing prose. Code and comments are exempt."""
    problems = []
    for label, text in _reader_prose():
        low = text.lower()
        for phrase in BANNED_PHRASES:
            if phrase in low:
                problems.append("{}: contains banned phrase {!r}".format(label, phrase))
        if NOT_X_BUT_Y.search(low):
            problems.append("{}: uses the 'it is not X, it is Y' pattern".format(label))
    return sorted(set(problems))


# === Secrets and synthetic identifiers =====================================
SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----")),
    ("bearer JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}")),
    ("cloudflare token", re.compile(r"(?i)CF_API_TOKEN\s*=\s*[\"'][A-Za-z0-9_-]{20,}")),
]


def check_no_secrets() -> list:
    problems = []
    for path in repo_text_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == SELF:
            continue
        text = path.read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS:
            for m in pattern.finditer(text):
                problems.append("{}: possible {} -> {!r}".format(rel, label, m.group(0)[:30]))
    return problems


def check_synthetic_identifiers_only() -> list:
    """Every generated identifier stays inside a range reserved for fiction."""
    problems = []
    import csv
    emp = ROOT / "data/corpus/employees.csv"
    if not emp.exists():
        return ["data/corpus/employees.csv missing: run the generator"]
    with emp.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if not row["email"].endswith("@" + C.COMPANY_DOMAIN):
                problems.append("employee {} email not on the fictional domain".format(
                    row["employee_id"]))
            if not row["national_insurance_no"].startswith(C.NINO_PREFIX):
                problems.append("employee {} NI number outside the {} specimen range".format(
                    row["employee_id"], C.NINO_PREFIX))
            if not row["sort_code"].startswith(C.SORT_CODE_PREFIX):
                problems.append("employee {} sort code outside the fictional range".format(
                    row["employee_id"]))
            if not row["phone"].startswith(C.PHONE_PREFIX):
                problems.append("employee {} phone outside the Ofcom drama range".format(
                    row["employee_id"]))
    cand = ROOT / "data/corpus/candidates.csv"
    if cand.exists():
        with cand.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                domain = row["email"].rsplit("@", 1)[-1]
                if domain not in C.OUTSIDE_DOMAINS:
                    problems.append("candidate {} email domain {} is not reserved".format(
                        row["candidate_id"], domain))
    return problems[:20]


# === One value, one place ==================================================
def check_worker_names_match_constants() -> list:
    """The Worker config cannot import constants.py, so it is checked."""
    toml = ROOT / "infra/worker/wrangler.toml"
    js = ROOT / "infra/worker/src/index.js"
    problems = []
    if toml.exists():
        text = toml.read_text(encoding="utf-8")
        if C.CF_VECTORIZE_INDEX not in text:
            problems.append("wrangler.toml does not name the index {}".format(
                C.CF_VECTORIZE_INDEX))
        if C.COMPANY_DOMAIN not in text:
            problems.append("wrangler.toml does not set the company domain")
    if js.exists():
        text = js.read_text(encoding="utf-8")
        for model in (C.CF_MODEL_GUARD, C.CF_MODEL_CHAT, C.CF_MODEL_EMBED):
            if model not in text:
                problems.append("worker index.js does not use model {}".format(model))
        if C.COMPANY_DOMAIN not in text:
            problems.append("worker index.js does not use the company domain")
    return problems


def check_prices_have_sources() -> list:
    """Every price key is a number and there is at least one source per claim."""
    problems = []
    for key, value in C.PRICES.items():
        if not isinstance(value, (int, float)):
            problems.append("price {!r} is not a number".format(key))
    if len(C.PRICE_SOURCES) < 5:
        problems.append("fewer than 5 price sources listed")
    for name, url in C.PRICE_SOURCES:
        if not url.startswith("http"):
            problems.append("price source {!r} has no url".format(name))
    return problems


# === Held-out set is frozen ================================================
def check_heldout_frozen() -> list:
    """The held-out attacks must match the hash frozen before controls existed."""
    frozen = ROOT / "eval/FROZEN.json"
    target = ROOT / "eval/templates_heldout.py"
    if not frozen.exists() or not target.exists():
        return ["eval/FROZEN.json or templates_heldout.py missing"]
    expected = json.loads(frozen.read_text(encoding="utf-8"))["sha256"]
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if expected != actual:
        return ["held-out templates changed since they were frozen. If this was "
                "deliberate, re-freeze with scripts/freeze_heldout.py and note the "
                "new date in the guide; otherwise the held-out result is no longer "
                "held out."]
    return []


# === Both directions =======================================================
def check_controls_all_referenced() -> list:
    """Every control in constants appears in the pipeline, the blueprint and
    the deck data, and nothing references a control that does not exist."""
    problems = []
    pipeline = (ROOT / "src/warden/app/assistant.py").read_text(encoding="utf-8")
    tool_policy = (ROOT / "src/warden/policy/tool_policy.py").read_text(encoding="utf-8")
    text = pipeline + tool_policy + (
        ROOT / "src/warden/backends/classifiers.py").read_text(encoding="utf-8") + (
        ROOT / "src/warden/gateway/pii.py").read_text(encoding="utf-8")
    for cid, key, _ in C.CONTROLS:
        if cid not in text:
            problems.append("control {} ({}) is declared but never used in code".format(
                cid, key))
    return problems


def check_probe_families_exist() -> list:
    """Every attack template names a real family and goal, and every family is
    used by at least one template."""
    from eval.build_attacks import all_probes
    probes = all_probes()
    problems = []
    used_family = set()
    for p in probes:
        used_family.add(p.family)
        if p.family not in C.FAMILY_KEYS:
            problems.append("probe {} uses unknown family {}".format(p.probe_id, p.family))
        if p.goal not in C.GOAL_KEYS:
            problems.append("probe {} uses unknown goal {}".format(p.probe_id, p.goal))
    for fam in C.FAMILY_KEYS:
        if fam not in used_family:
            problems.append("family {} has no attack, so it is never tested".format(fam))
    if not any(p.held_out for p in probes):
        problems.append("no held-out probes: the red team would only measure tuned attacks")
    ids = [p.probe_id for p in probes]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        problems.append("duplicate probe ids: {}".format(sorted(dupes)))
    return problems


def check_code_regions() -> list:
    try:
        regions = all_regions()
    except RegionError as exc:
        return [str(exc)]
    problems = []
    if len(regions) < 25:
        problems.append("only {} regions, expected at least 25".format(len(regions)))
    for name, item in regions.items():
        if not item.text.strip():
            problems.append("region {!r} is empty".format(name))
    return problems


def gitignored() -> set:
    ig = ROOT / ".gitignore"
    if not ig.exists():
        return set()
    return {l.strip().lstrip("/!") for l in ig.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")}


def check_referenced_files_exist() -> list:
    problems = []
    ignored = gitignored()
    pattern = re.compile(
        r"\b((?:src|scripts|data|eval|infra|tests|docs|ppt|assets)/[A-Za-z0-9_./-]+"
        r"\.(?:py|json|sh|kql|yml|yaml|md|docx|pptx|png|csv|jsonl|txt|js|toml))\b")
    for path in repo_text_files():
        rel = path.relative_to(ROOT).as_posix()
        # wrangler.toml uses paths relative to the Worker directory, not the
        # repo root, so its 'src/index.js' is not a repo path.
        if rel in {SELF, "scripts/check_negative.py", "infra/worker/wrangler.toml"}:
            continue
        for match in set(pattern.findall(path.read_text(encoding="utf-8"))):
            if match.endswith((".docx", ".pptx", ".png")):
                continue
            if "<" in match or "*" in match or match in ignored:
                continue
            if not (ROOT / match).exists():
                problems.append("{} references {} which does not exist".format(rel, match))
    return sorted(set(problems))


# === The guide =============================================================
def _guide_paragraphs() -> list:
    from docx import Document
    doc = Document(str(GUIDE))
    paras = list(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                paras.extend(cell.paragraphs)
    return paras


def _guide_blocks() -> list:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = Document(str(GUIDE))
    blocks = []
    last = ""
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            last = Paragraph(child, doc).text.strip()
        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            if len(table.rows) != 1 or len(table.columns) != 1:
                continue
            cell = table.cell(0, 0)
            is_code = any(r.font.name == C.FONT_CODE for p in cell.paragraphs
                          for r in p.runs if r.font.name)
            if is_code:
                blocks.append((last, "\n".join(p.text for p in cell.paragraphs)))
    return blocks


def check_guide_code_matches_source() -> list:
    if not GUIDE.exists():
        return ["guide not built yet: run python scripts/build_guide.py"]
    regions = all_regions()
    corpus = "\n\n".join(item.text for item in regions.values())
    problems = []
    blocks = _guide_blocks()
    if not blocks:
        problems.append("the guide has no code blocks at all")
    cited = 0
    for caption, block in blocks:
        if not caption.startswith("From "):
            continue
        cited += 1
        for line in block.splitlines():
            s = line.strip()
            if len(s) < 12:
                continue
            if s not in corpus:
                problems.append("guide block {!r} has a line in no source region: {!r}".format(
                    caption[:40], s[:60]))
                break
    if blocks and not cited:
        problems.append("no guide block cites a source file")
    return problems


def check_guide_numbers_match_manifest() -> list:
    if not GUIDE.exists():
        return ["guide not built yet: run python scripts/build_guide.py"]
    if not MANIFEST.exists():
        return ["results/manifest.json missing: run python scripts/run_all.py"]
    return _numbers_against_manifest(
        "\n".join(p.text for p in _guide_paragraphs()
                  if not any(r.font.name == C.FONT_CODE for r in p.runs if r.font.name)),
        "guide")


def check_readme_numbers_match_manifest() -> list:
    if not README.exists():
        return ["README.md missing"]
    if not MANIFEST.exists():
        return ["results/manifest.json missing"]
    table = "\n".join(l for l in README.read_text(encoding="utf-8").splitlines()
                      if l.startswith("|"))
    return _numbers_against_manifest(table, "README table")


def _allowed_percentages(manifest: dict) -> set:
    allowed = set()

    def add(v):
        allowed.add("{:.1f}%".format(v * 100))
        allowed.add("{:.0f}%".format(v * 100))

    r = manifest["redteam"]
    u = manifest["utility"]
    for v in (r["naive_breach_rate"], r["gateway_breach_rate"],
              r["naive_exposure_rate"], r["gateway_exposure_rate"],
              r["naive_dev_rate"], r["gateway_dev_rate"],
              r["naive_held_rate"], r["gateway_held_rate"],
              u["answer_rate"], u["correct_rate"], u["boundary_rate"],
              manifest["pii"]["recall"], manifest["pii"]["regex_recall"],
              manifest["thresholds"]["redteam_max_success_rate"]):
        add(v)
    for stats in r["by_family"].values():
        add(stats["rate"])
    for stats in r["naive_by_family"].values():
        add(stats["rate"])
    return allowed


def _numbers_against_manifest(text: str, label: str) -> list:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    allowed = _allowed_percentages(manifest)
    problems = []
    for found in set(re.findall(r"\b\d{1,3}\.\d%|\b\d{1,3}%", text)):
        if found not in allowed:
            problems.append("{} prints {} which is not a measured value".format(label, found))
    return sorted(problems)


def check_chapter_references() -> list:
    if not GUIDE.exists():
        return ["guide not built yet: run python scripts/build_guide.py"]
    import guide_chapters as ch
    total = len(ch.CHAPTERS)
    letters = {l for l, _ in ch.APPENDICES}
    problems = []
    text = "\n".join(p.text for p in _guide_paragraphs()
                     if not any(r.font.name == C.FONT_CODE for r in p.runs if r.font.name))
    for found in set(re.findall(r"[Cc]hapters?\s+(\d+)", text)):
        if not 1 <= int(found) <= total:
            problems.append("guide refers to chapter {} but there are {}".format(found, total))
    for found in set(re.findall(r"[Aa]ppendix\s+([A-Z])", text)):
        if found not in letters:
            problems.append("guide refers to Appendix {} which does not exist".format(found))
    for source in ("scripts/guide_content.py",):
        body = (ROOT / source).read_text(encoding="utf-8")
        for i, line in enumerate(body.splitlines(), 1):
            if re.search(r"\"[^\"]*\bchapters?\s+\d+", line, re.IGNORECASE):
                problems.append("{}:{} types a chapter number into prose; use [[ch:key]]".format(
                    source, i))
    return problems


def check_guide_uses_every_region() -> list:
    """Every code region is cited by the built guide, and every cited region
    exists. The forward half is enforced by the builder; this is the reverse."""
    if not GUIDE.exists():
        return ["guide not built yet: run python scripts/build_guide.py"]
    regions = all_regions()
    cited_text = "\n".join(b for _, b in _guide_blocks())
    problems = []
    for name, item in regions.items():
        sample = next((l.strip() for l in item.text.splitlines() if len(l.strip()) >= 15), "")
        if sample and sample not in cited_text:
            problems.append("region {!r} is defined but never appears in the guide".format(name))
    return problems


CHECKS = [
    ("no_dashes", check_no_dashes),
    ("banned_phrases", check_banned_phrases),
    ("no_secrets", check_no_secrets),
    ("synthetic_identifiers_only", check_synthetic_identifiers_only),
    ("worker_names_match_constants", check_worker_names_match_constants),
    ("prices_have_sources", check_prices_have_sources),
    ("heldout_frozen", check_heldout_frozen),
    ("controls_all_referenced", check_controls_all_referenced),
    ("probe_families_exist", check_probe_families_exist),
    ("code_regions", check_code_regions),
    ("referenced_files_exist", check_referenced_files_exist),
    ("guide_code_matches_source", check_guide_code_matches_source),
    ("guide_numbers_match_manifest", check_guide_numbers_match_manifest),
    ("readme_numbers_match_manifest", check_readme_numbers_match_manifest),
    ("chapter_references", check_chapter_references),
    ("guide_uses_every_region", check_guide_uses_every_region),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Warden cross-file checks")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--allow-missing-guide", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for name, fn in CHECKS:
            doc = (fn.__doc__ or "").strip().splitlines()
            print("  {:34s} {}".format(name, doc[0] if doc else ""))
        return 0

    failures = warnings = 0
    for name, fn in CHECKS:
        if args.only and args.only != name:
            continue
        problems = fn()
        deferred = [p for p in problems if p.startswith("guide not built yet")]
        if deferred and args.allow_missing_guide:
            print("  SKIP  {:34s} {}".format(name, deferred[0]))
            warnings += 1
            continue
        if problems:
            failures += 1
            print("  FAIL  {}".format(name))
            for p in problems[:12]:
                print("          {}".format(p))
            if len(problems) > 12:
                print("          ... and {} more".format(len(problems) - 12))
        else:
            print("  ok    {}".format(name))
    print()
    if failures:
        print("{} check(s) failed".format(failures))
        return 1
    print("all cross-file checks passed{}".format(
        " ({} skipped)".format(warnings) if warnings else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
