"""Build docs/Warden_Build_Guide.docx.

Two rules this builder enforces on itself, and they are the whole point:

  1. It contains no code. Every code block comes from `code_excerpt.excerpt`,
     which reads the real file. A block in the document that is not in the
     repository is impossible by construction.

  2. It contains no measured numbers. Every figure comes from
     results/manifest.json, written by scripts/run_all.py. If the manifest is
     missing or a key is absent, the build fails rather than printing a value
     somebody remembered.

House style, matching the rest of the series: black and white, Table Grid
with thin black borders, no shading, headings in bold black, Consolas for
code, and no em or en dashes anywhere.

    python scripts/run_all.py        first, to produce the numbers
    python scripts/build_guide.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from warden import constants as C  # noqa: E402
import guide_chapters as chapters  # noqa: E402
from code_excerpt import excerpt, verify_all  # noqa: E402

BLACK = RGBColor(0, 0, 0)
USED_REGIONS: set[str] = set()

# Chapter references in prose are TOKENS, substituted here, never typed as
# numbers. The first build of this guide carried four wrong chapter numbers in
# a single table because they were literals: insert a chapter anywhere and
# every literal after it is silently wrong, and nothing was comparing the
# document to itself. See scripts/guide_chapters.py.
#
#   [[ch:azure]]    ->  chapter 14
#   [[Ch:pii]]      ->  Chapter 7           (sentence start)
#   [[chn:cost]]    ->  17                  (bare number)
#   [[offline]]     ->  chapters 1 to 13
#   [[Offline]]     ->  Chapters 1 to 13
#   [[cloud]]       ->  chapters 14 to 17
TOKEN_RE = re.compile(
    r"\[\[(ch|Ch|chn|offline|Offline|cloud|Cloud)(?::([a-z_]+))?\]\]"
)


def substitute(value: str) -> str:
    """Resolve every chapter token in a piece of prose."""

    def replace(match):
        kind, key = match.group(1), match.group(2)
        if kind.lower() == "offline":
            resolved = chapters.offline_range()
        elif kind.lower() == "cloud":
            resolved = chapters.cloud_range()
        elif kind == "chn":
            return str(chapters.n(key))
        else:
            resolved = chapters.ref(key)
        if kind[0].isupper():
            return resolved[0].upper() + resolved[1:]
        return resolved

    return TOKEN_RE.sub(replace, value)


class Manifest:
    """Read only access to the measured results, with loud failures.

    A missing key raises. The alternative, a default, is how a guide ends up
    quoting zero percent for something that was never measured.
    """

    def __init__(self, path: Path) -> None:
        if not path.exists():
            raise SystemExit(
                "results/manifest.json is missing. The guide is built from "
                "measured results, so run this first:\n"
                "    python scripts/run_all.py"
            )
        self.data = json.loads(path.read_text(encoding="utf-8"))

    def get(self, dotted: str):
        node = self.data
        for part in dotted.split("."):
            if isinstance(node, list):
                node = node[int(part)]
            elif part in node:
                node = node[part]
            else:
                raise SystemExit(
                    "the guide asked for {!r} and results/manifest.json has no "
                    "such value. Either the measurement was not run or the key "
                    "was renamed.".format(dotted)
                )
        return node

    def pct(self, dotted: str) -> str:
        return "{:.1f}%".format(self.get(dotted) * 100)

    def num(self, dotted: str) -> str:
        return "{:,}".format(self.get(dotted))


# ---------------------------------------------------------------------------
# Document furniture
# ---------------------------------------------------------------------------
def set_cell_border(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        element = OxmlElement("w:{}".format(edge))
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "000000")
        borders.append(element)
    tc_pr.append(borders)


def shade(cell, hex_colour: str) -> None:
    """Only used for the single grey header row. House style is otherwise flat."""
    tc_pr = cell._tc.get_or_add_tcPr()
    element = OxmlElement("w:shd")
    element.set(qn("w:val"), "clear")
    element.set(qn("w:fill"), hex_colour)
    tc_pr.append(element)


class GuideBuilder:
    def __init__(self, manifest: Manifest) -> None:
        self.m = manifest
        self.doc = Document()
        self._styles()
        self.chapter = 0
        self.section = 0
        self._appendix = None
        self.screenshots = 0
        self.code_blocks = 0

    def _styles(self) -> None:
        doc = self.doc
        normal = doc.styles["Normal"]
        normal.font.name = C.FONT_BODY
        normal.font.size = Pt(11)
        normal.font.color.rgb = BLACK
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.15
        for name, size in (("Heading 1", 18), ("Heading 2", 14), ("Heading 3", 12)):
            style = doc.styles[name]
            style.font.name = C.FONT_HEADING
            style.font.size = Pt(size)
            style.font.bold = True
            style.font.color.rgb = BLACK
        for section in doc.sections:
            section.left_margin = Inches(1.0)
            section.right_margin = Inches(1.0)
            section.top_margin = Inches(0.9)
            section.bottom_margin = Inches(0.9)

    # -- primitives -------------------------------------------------------
    def para(self, text: str = "", bold: bool = False, italic: bool = False,
             size: int = 11, align=None, space_after: int = 6):
        p = self.doc.add_paragraph()
        run = p.add_run(substitute(text))
        run.bold = bold
        run.italic = italic
        run.font.size = Pt(size)
        run.font.color.rgb = BLACK
        if align is not None:
            p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        return p

    def h1(self, key: str) -> None:
        """Start a chapter, named by KEY rather than by number or title.

        The number and the title both come from guide_chapters.py, and the
        builder asserts that chapters are emitted in the declared order. That
        is what stops prose and headings drifting apart when a chapter moves.
        """
        self.chapter += 1
        self.section = 0
        self._appendix = None
        expected = chapters.CHAPTERS[self.chapter - 1][0]
        if key != expected:
            raise SystemExit(
                "chapter {} was emitted as {!r} but guide_chapters.py declares "
                "{!r} in that position".format(self.chapter, key, expected))
        title = chapters.TITLE[key]
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        heading = self.doc.add_heading("{}. {}".format(self.chapter, title), level=1)
        for run in heading.runs:
            run.font.color.rgb = BLACK

    def appendix(self, letter: str) -> None:
        """Appendices are lettered, and stop the chapter counter advancing."""
        self.section = 0
        self._appendix = letter
        titles = dict(chapters.APPENDICES)
        if letter not in titles:
            raise SystemExit(
                "no appendix {!r} declared in guide_chapters.py".format(letter))
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        heading = self.doc.add_heading(
            "Appendix {}. {}".format(letter, titles[letter]), level=1)
        for run in heading.runs:
            run.font.color.rgb = BLACK

    def h2(self, text: str) -> str:
        self.section += 1
        prefix = self._appendix if self._appendix else self.chapter
        number = "{}.{}".format(prefix, self.section)
        heading = self.doc.add_heading(
            "{} {}".format(number, substitute(text)), level=2)
        for run in heading.runs:
            run.font.color.rgb = BLACK
        return number

    def h3(self, text: str) -> None:
        heading = self.doc.add_heading(substitute(text), level=3)
        for run in heading.runs:
            run.font.color.rgb = BLACK

    def bullets(self, items: list[str]) -> None:
        # House style is bullets, never Word's List Number: that style shares
        # one counter across the whole document, so lists never restart and a
        # chapter 9 list renders as 63, 64, 65.
        for item in items:
            p = self.doc.add_paragraph(style="List Bullet")
            run = p.add_run(substitute(item))
            run.font.color.rgb = BLACK
            run.font.size = Pt(11)
            p.paragraph_format.space_after = Pt(3)

    def steps(self, items: list[str]) -> None:
        """Numbered steps, numbered by hand for the same reason."""
        for index, item in enumerate(items, start=1):
            p = self.doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.3)
            p.paragraph_format.space_after = Pt(3)
            run = p.add_run("{}.  ".format(index))
            run.bold = True
            run.font.color.rgb = BLACK
            body = p.add_run(substitute(item))
            body.font.color.rgb = BLACK
            body.font.size = Pt(11)

    def code(self, region: str, caption: str | None = None) -> None:
        """A code block, pulled verbatim from the repository."""
        item = excerpt(region)
        USED_REGIONS.add(region)
        self.code_blocks += 1
        if caption:
            desc = self.doc.add_paragraph()
            desc_run = desc.add_run(caption)
            desc_run.italic = True
            desc_run.font.size = Pt(9)
            desc_run.font.color.rgb = BLACK
            desc.paragraph_format.space_after = Pt(1)
        # Always emit the source label as the LAST line before the block, so
        # the validator can pair the block with its origin and byte-compare it.
        label = self.doc.add_paragraph()
        label_run = label.add_run("From {}".format(item.source_label))
        label_run.italic = True
        label_run.font.size = Pt(9)
        label_run.font.color.rgb = BLACK
        label.paragraph_format.space_after = Pt(2)
        self._mono_block(item.text)

    def shell(self, lines: list[str], caption: str = "Run this") -> None:
        label = self.doc.add_paragraph()
        run = label.add_run(caption)
        run.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = BLACK
        label.paragraph_format.space_after = Pt(2)
        self._mono_block("\n".join(lines))

    def output(self, text: str, caption: str = "What you should see") -> None:
        label = self.doc.add_paragraph()
        run = label.add_run(caption)
        run.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = BLACK
        label.paragraph_format.space_after = Pt(2)
        self._mono_block(text)

    def _mono_block(self, text: str) -> None:
        table = self.doc.add_table(rows=1, cols=1)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        cell = table.cell(0, 0)
        set_cell_border(cell)
        cell.paragraphs[0].text = ""
        for index, line in enumerate(text.split("\n")):
            p = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            run = p.add_run(line)
            run.font.name = C.FONT_CODE
            run.font.size = Pt(8.5)
            run.font.color.rgb = BLACK
            run._element.rPr.rFonts.set(qn("w:eastAsia"), C.FONT_CODE)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def table(self, headers: list[str], rows: list[list[str]],
              widths: list[float] | None = None) -> None:
        table = self.doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        header_cells = table.rows[0].cells
        for index, title in enumerate(headers):
            cell = header_cells[index]
            cell.text = ""
            run = cell.paragraphs[0].add_run(substitute(title))
            run.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = BLACK
            set_cell_border(cell)
            shade(cell, "EEEEEE")
        for row in rows:
            cells = table.add_row().cells
            for index, value in enumerate(row):
                cell = cells[index]
                cell.text = ""
                run = cell.paragraphs[0].add_run(substitute(str(value)))
                run.font.size = Pt(10)
                run.font.color.rgb = BLACK
                set_cell_border(cell)
        if widths:
            for row in table.rows:
                for index, width in enumerate(widths):
                    row.cells[index].width = Inches(width)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def callout(self, kind: str, text: str) -> None:
        table = self.doc.add_table(rows=1, cols=1)
        table.style = "Table Grid"
        cell = table.cell(0, 0)
        set_cell_border(cell)
        cell.text = ""
        p = cell.paragraphs[0]
        label = p.add_run("{}  ".format(kind.upper()))
        label.bold = True
        label.font.size = Pt(9)
        label.font.color.rgb = BLACK
        body = p.add_run(substitute(text))
        body.font.size = Pt(10)
        body.font.color.rgb = BLACK
        self.doc.add_paragraph().paragraph_format.space_after = Pt(4)

    def screenshot(self, caption: str) -> None:
        self.screenshots += 1
        p = self.doc.add_paragraph()
        run = p.add_run(
            "[SCREENSHOT {}]  {}".format(self.screenshots, substitute(caption)))
        run.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = BLACK
        p.paragraph_format.space_after = Pt(8)

    # -- front matter -----------------------------------------------------
    def cover(self) -> None:
        for _ in range(4):
            self.para()
        self.para("{}, {}".format(C.PROJECT_NAME, C.PROJECT_SUBTITLE),
                  bold=True, size=38, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.para(C.PROJECT_TAGLINE, size=15, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.para()
        self.para(
            "Build an HR chatbot and agent, break it with a hostile CV and a "
            "poisoned web page, then put one gateway in front that stops the "
            "attacks and still answers the real questions.",
            italic=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER,
        )
        for _ in range(6):
            self.para()
        self.para("{} | {}".format(C.BRAND, C.BRAND_SITE),
                  bold=True, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.para(C.CREDIT_LINE, size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.para("Built by {}. {}".format(C.OWNER, C.SERIES_POSITION), size=10,
                  align=WD_ALIGN_PARAGRAPH.CENTER)
        self.para(C.RIGHTS_LINE, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.para()
        self.para(
            "This guide is sold as one product covering the whole project. You "
            "can build it, adapt it and use it in your own work. You cannot "
            "resell or share the document itself.",
            italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER,
        )

    def contents(self) -> None:
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
        heading = self.doc.add_heading("Contents", level=1)
        for run in heading.runs:
            run.font.color.rgb = BLACK
        p = self.doc.add_paragraph()
        run = p.add_run()
        fld_begin = OxmlElement("w:fldChar")
        fld_begin.set(qn("w:fldCharType"), "begin")
        instr = OxmlElement("w:instrText")
        instr.set(qn("xml:space"), "preserve")
        instr.text = 'TOC \\o "1-2" \\h \\z \\u'
        fld_sep = OxmlElement("w:fldChar")
        fld_sep.set(qn("w:fldCharType"), "separate")
        placeholder = OxmlElement("w:t")
        placeholder.text = "Right click here and choose Update Field to build the contents."
        fld_end = OxmlElement("w:fldChar")
        fld_end.set(qn("w:fldCharType"), "end")
        for element in (fld_begin, instr, fld_sep, placeholder, fld_end):
            run._r.append(element)

    def footer(self) -> None:
        for section in self.doc.sections:
            paragraph = section.footer.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(
                "{} | {} | {}".format(C.PROJECT_NAME, C.BRAND, C.BRAND_SITE)
            )
            run.font.size = Pt(8)
            run.font.color.rgb = BLACK

    def save(self, path: Path) -> None:
        self.footer()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(path))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the Warden guide")
    ap.add_argument("--out", default="docs/Warden_Build_Guide.docx")
    ap.add_argument("--manifest", default="results/manifest.json")
    args = ap.parse_args(argv)

    manifest = Manifest(ROOT / args.manifest)
    builder = GuideBuilder(manifest)

    import guide_content

    builder.cover()
    builder.contents()
    guide_content.write(builder, manifest)

    # Both directions. Every region the guide asked for exists, because
    # `excerpt` raises otherwise. Every region that exists is used, checked
    # here, because a forward only check passes loudest when the guide
    # contains no code at all.
    if builder.chapter != len(chapters.CHAPTERS):
        print(
            "FAIL: guide_chapters.py declares {} chapters but {} were "
            "written".format(len(chapters.CHAPTERS), builder.chapter),
            file=sys.stderr,
        )
        return 1

    problems = verify_all(USED_REGIONS)
    if problems:
        for problem in problems:
            print("REGION PROBLEM: {}".format(problem), file=sys.stderr)
        return 1

    out = ROOT / args.out
    builder.save(out)

    text = "\n".join(p.text for p in Document(str(out)).paragraphs)
    # Scan EVERYTHING, including table cells, because prose lives in callouts
    # and tables too. Match the real token pattern rather than a bare "[[":
    # code blocks legitimately contain regex character classes like \[[^\]]*\]
    # and an over-eager check would fail on its own excerpts.
    rebuilt = Document(str(out))
    everywhere = list(rebuilt.paragraphs)
    for table in rebuilt.tables:
        for row in table.rows:
            for cell in row.cells:
                everywhere.extend(cell.paragraphs)
    joined = "\n".join(p.text for p in everywhere)
    unresolved = TOKEN_RE.search(joined)
    if unresolved:
        print(
            "FAIL: an unresolved reference token reached the document: "
            "{!r}".format(unresolved.group(0)),
            file=sys.stderr,
        )
        return 1
    for code_point, name in ((0x2014, "em dash"), (0x2013, "en dash")):
        if chr(code_point) in text:
            print("FAIL: the built guide contains an {}".format(name), file=sys.stderr)
            return 1

    print("Wrote {}".format(out))
    print("  chapters      {}".format(builder.chapter))
    print("  code blocks   {} (from {} distinct regions)".format(
        builder.code_blocks, len(USED_REGIONS)))
    print("  screenshots   {} markers".format(builder.screenshots))
    print("  paragraphs    {}".format(len(Document(str(out)).paragraphs)))
    print("  tables        {}".format(len(Document(str(out)).tables)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
