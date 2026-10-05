"""Build the spoiler-free overview deck.

    python scripts/build_overview_ppt.py

Ten slides that say what the project is and why it matters, without giving
away the build. Companion to the video, not a substitute for the guide.

House rules from the other decks in this series:
  * Never put text inside a chevron or arrow shape. It wraps to one character
    per line and overflows. Use rounded rectangles with an EMPTY arrow between.
  * Every number comes from results/manifest.json, so the deck cannot quote a
    figure the project never produced.
  * Render every slide and look at it before declaring done.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SERIES_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from warden import constants as C  # noqa: E402


def rgb(v):
    return RGBColor.from_string(v)


INK = rgb(C.COLOR_INK)
ACCENT = rgb(C.COLOR_ACCENT)         # Warden Magenta
AMBER = rgb(C.COLOR_AMBER)
GREEN = rgb(C.COLOR_GREEN)
GREY = rgb(C.COLOR_GREY)
MIST = rgb(C.COLOR_MIST)
PAPER = rgb(C.COLOR_PAPER)
WHITE = rgb(C.COLOR_WHITE)

W = Inches(13.333)
H = Inches(7.5)


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width = W
        self.prs.slide_height = H

    def slide(self, dark=False):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
        bg.fill.solid()
        bg.fill.fore_color.rgb = INK if dark else WHITE
        bg.line.fill.background()
        bg.shadow.inherit = False
        return s

    def text(self, slide, left, top, width, height, text, size=18, bold=False,
             color=INK, align=PP_ALIGN.LEFT, italic=False, anchor=MSO_ANCHOR.TOP,
             spacing=1.0):
        box = slide.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        for i, line in enumerate(text.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = spacing
            run = p.add_run()
            run.text = line
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = color
            run.font.name = "Calibri"
        return box

    def card(self, slide, left, top, width, height, title, body, accent=ACCENT,
             title_size=15, body_size=12, body_offset=0.62):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = WHITE
        shape.line.color.rgb = accent
        shape.line.width = Pt(1.25)
        shape.shadow.inherit = False
        shape.text_frame.text = ""
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top,
                                     Emu(int(width * 0.06)), height)
        bar.fill.solid()
        bar.fill.fore_color.rgb = accent
        bar.line.fill.background()
        bar.shadow.inherit = False
        pad = Inches(0.22)
        self.text(slide, left + pad + Emu(int(width * 0.06)), top + Inches(0.14),
                  width - pad * 2 - Emu(int(width * 0.06)), Inches(0.4),
                  title, size=title_size, bold=True, color=INK)
        self.text(slide, left + pad + Emu(int(width * 0.06)), top + Inches(body_offset),
                  width - pad * 2 - Emu(int(width * 0.06)),
                  height - Inches(body_offset) - Inches(0.08),
                  body, size=body_size, color=GREY, spacing=1.12)
        return shape

    def arrow(self, slide, left, top, width, height, colour=ACCENT):
        shape = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = colour
        shape.line.fill.background()
        shape.shadow.inherit = False
        shape.text_frame.text = ""
        return shape

    def rule(self, slide, top, colour=ACCENT, left=Inches(0.9), width=Inches(1.6)):
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, Pt(4))
        bar.fill.solid()
        bar.fill.fore_color.rgb = colour
        bar.line.fill.background()
        bar.shadow.inherit = False

    def footer(self, slide, number, dark=False):
        self.text(slide, Inches(0.5), H - Inches(0.5), Inches(7), Inches(0.3),
                  "{}  |  {}".format(C.BRAND, C.BRAND_SITE), size=10,
                  color=MIST if dark else GREY)
        self.text(slide, W - Inches(1.2), H - Inches(0.5), Inches(0.7), Inches(0.3),
                  str(number), size=10, align=PP_ALIGN.RIGHT, color=MIST if dark else GREY)


def pct(v):
    return "{:.0f}%".format(v * 100)


def build(m) -> Deck:
    d = Deck()
    r = m["redteam"]
    u = m["utility"]
    headshot = SERIES_ROOT / "Haseeb formal.jpeg"

    # 1 title
    s = d.slide(dark=True)
    d.text(s, Inches(0.9), Inches(1.9), Inches(9.2), Inches(1.3),
           "{}".format(C.PROJECT_NAME), size=64, bold=True, color=WHITE)
    d.text(s, Inches(0.9), Inches(3.15), Inches(9.2), Inches(0.6),
           "the AI Firewall", size=28, color=ACCENT, bold=True)
    d.rule(s, Inches(3.9), colour=ACCENT)
    d.text(s, Inches(0.9), Inches(4.2), Inches(9.2), Inches(1.0),
           C.PROJECT_TAGLINE, size=22, color=WHITE)
    d.text(s, Inches(0.9), Inches(5.1), Inches(9.2), Inches(1.0),
           "Secure a RAG chatbot and its agent. {} attacks, and the numbers to "
           "prove it.".format(m["probe_counts"]["total"]), size=15, color=MIST)
    if headshot.exists():
        s.shapes.add_picture(str(headshot), W - Inches(3.4), Inches(1.9), height=Inches(3.4))
    d.text(s, W - Inches(3.4), Inches(5.5), Inches(2.7), Inches(1.0),
           "{}\n{}".format(C.AUTHOR, C.BRAND), size=13, bold=True, color=WHITE)
    d.footer(s, 1, dark=True)

    # 2 the story
    s = d.slide()
    d.text(s, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.8),
           "Every company shipped an AI assistant. Almost nobody secured one.",
           size=28, bold=True)
    d.rule(s, Inches(1.55))
    d.text(s, Inches(0.9), Inches(1.85), Inches(11.5), Inches(1.0),
           "{} runs an HR chatbot with an agent that can look up staff, change "
           "payroll and email documents. It works. No security team went near "
           "it.".format(C.COMPANY), size=17, color=GREY)
    for i, (t, b) in enumerate([
        ("Outsiders can talk to it",
         "A candidate's CV or a web page it reads is pasted into the prompt. A "
         "hidden line becomes an instruction."),
        ("Retrieval ignores who is asking",
         "A recruiter, a manager and a payroll officer all get the same "
         "answers. Permissions are gone."),
        ("The agent can act",
         "It can email a file out or change pay. An injection doesn't leak "
         "data, it does something."),
    ]):
        d.card(s, Inches(0.9) + Inches(3.85) * i, Inches(3.35),
               Inches(3.55), Inches(2.5), t, b)
    d.footer(s, 2)

    # 3 the demo
    s = d.slide()
    d.text(s, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.8),
           "The attack that makes people sit up", size=30, bold=True)
    d.rule(s, Inches(1.6))
    steps = [
        ("A candidate uploads a CV",
         "It reads like a normal CV. Buried in it is a line addressed to the "
         "assistant, not to a person."),
        ("A recruiter asks a normal question",
         "About the candidate. They never see the buried line. The model "
         "does."),
        ("The agent acts on it",
         "It tries to email the payroll file to an outside address. Nobody "
         "typed that."),
    ]
    left = Inches(0.9)
    for i, (t, b) in enumerate(steps):
        d.card(s, left, Inches(2.5), Inches(3.3), Inches(2.0), t, b)
        left += Inches(3.3)
        if i < len(steps) - 1:
            d.arrow(s, left + Inches(0.12), Inches(3.2), Inches(0.5), Inches(0.55))
            left += Inches(0.75)
    d.text(s, Inches(0.9), Inches(5.0), Inches(11.5), Inches(0.9),
           "Nobody stole a password. A candidate sent in a CV.",
           size=20, bold=True, color=ACCENT)
    d.footer(s, 3)

    # 4 the controls
    s = d.slide()
    d.text(s, Inches(0.9), Inches(0.55), Inches(11.5), Inches(0.8),
           "One gateway, eight controls, in front of the app", size=28, bold=True)
    d.rule(s, Inches(1.45))
    d.text(s, Inches(0.9), Inches(1.65), Inches(11.5), Inches(0.5),
           "The app is not changed. The team that built it keeps their code.",
           size=15, color=GREY)
    for i, (cid, key, purpose) in enumerate(C.CONTROLS):
        row, col = divmod(i, 4)
        d.card(s, Inches(0.9) + Inches(3.0) * col, Inches(2.3) + Inches(1.6) * row,
               Inches(2.8), Inches(1.42),
               "{}  {}".format(cid, key.replace("_", " ")),
               purpose, title_size=12, body_size=10, body_offset=0.46)
    d.footer(s, 4)

    # 5 the proof
    s = d.slide(dark=True)
    d.text(s, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.8),
           "Measured, not asserted", size=30, bold=True, color=WHITE)
    d.rule(s, Inches(1.6), colour=ACCENT)
    metrics = [
        (pct(r["naive_breach_rate"]), "of attacks breached\nthe unprotected app", AMBER),
        (pct(r["gateway_breach_rate"]), "breached it\nbehind Warden", GREEN),
        (pct(u["answer_rate"]), "of normal questions\nstill answered", WHITE),
        (str(m["probe_counts"]["held_out"]), "attacks written and frozen\nbefore any control", WHITE),
    ]
    for i, (val, label, colour) in enumerate(metrics):
        left = Inches(0.9) + Inches(3.0) * i
        d.text(s, left, Inches(2.4), Inches(2.7), Inches(1.2), val,
               size=52, bold=True, color=colour, align=PP_ALIGN.CENTER)
        d.text(s, left, Inches(3.8), Inches(2.7), Inches(1.2), label,
               size=13, color=MIST, align=PP_ALIGN.CENTER, spacing=1.15)
    d.text(s, Inches(0.9), Inches(5.4), Inches(11.5), Inches(1.0),
           "The third number matters as much as the second. A gateway that "
           "refused everything would score zero attacks and be useless.",
           size=16, italic=True, color=MIST)
    d.footer(s, 5, dark=True)

    # 6 the honest bit
    s = d.slide()
    d.text(s, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.8),
           "The part most write-ups leave out", size=30, bold=True)
    d.rule(s, Inches(1.6))
    d.card(s, Inches(0.9), Inches(2.2), Inches(5.4), Inches(3.0),
           "Detection is not the boundary",
           "The injection classifier caught nothing on its own that the other "
           "controls didn't already stop. Reworded attacks slip past it. That "
           "is the honest result.", accent=AMBER)
    d.card(s, Inches(6.9), Inches(2.2), Inches(5.4), Inches(3.0),
           "The structural controls hold",
           "Permission-aware retrieval and the tool-call policy don't depend on "
           "spotting the attack. An email can only go to the company domain, "
           "whatever wording the injection used.", accent=GREEN)
    d.text(s, Inches(0.9), Inches(5.5), Inches(11.5), Inches(0.7),
           "Input rules catch what you know. Permissions and a tool policy "
           "catch what you don't.", size=17, bold=True, color=ACCENT)
    d.footer(s, 6)

    # 7 the stack
    s = d.slide()
    d.text(s, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.8),
           "Built on free tiers", size=30, bold=True)
    d.rule(s, Inches(1.6))
    rows = [
        ("Cloudflare Workers", "the gateway at the edge"),
        ("Workers AI", "Llama Guard 3, the chat model, embeddings"),
        ("Vectorize", "retrieval with the permission filter"),
        ("AI Gateway", "logs, caching, rate limits"),
        ("Prompt Guard 2", "injection classifier, on a free Oracle VM"),
        ("Presidio", "personal data detection, open source"),
    ]
    for i, (name, purpose) in enumerate(rows):
        row, col = divmod(i, 2)
        d.card(s, Inches(0.9) + Inches(5.9) * col, Inches(2.1) + Inches(1.05) * row,
               Inches(5.6), Inches(0.92), name, purpose,
               title_size=13, body_size=11, body_offset=0.44)
    d.text(s, Inches(0.9), Inches(5.9), Inches(11.5), Inches(0.6),
           "Whole build: about {} dollars a month, inside a {} to {} dollar "
           "budget. The offline half costs nothing.".format(
               m["cost"]["total_usd_per_month"], m["cost"]["budget_low"],
               m["cost"]["budget_high"]), size=16, bold=True, color=GREEN)
    d.footer(s, 7)

    # 8 who it is for
    s = d.slide()
    d.text(s, Inches(0.9), Inches(0.7), Inches(11.5), Inches(0.8),
           "Who this is for", size=30, bold=True)
    d.rule(s, Inches(1.6))
    for i, (t, b) in enumerate([
        ("Security engineers",
         "You've been handed an AI system to secure and there's no runbook for "
         "it. This is the runbook."),
        ("Data and ML engineers",
         "You built the RAG pipeline and the agent. This is what happens to it "
         "next, and what you'll be asked for."),
        ("Anyone hiring for AI security",
         "The job barely existed two years ago and now has more openings than "
         "people who can do it."),
    ]):
        d.card(s, Inches(0.9) + Inches(3.85) * i, Inches(2.5),
               Inches(3.55), Inches(2.7), t, b)
    d.text(s, Inches(0.9), Inches(5.7), Inches(11.5), Inches(0.6),
           "You need Python. You don't need a cloud account to finish most of "
           "it.", size=17, color=GREY)
    d.footer(s, 8)

    # 9 the offer
    s = d.slide(dark=True)
    d.text(s, Inches(0.9), Inches(0.9), Inches(11.5), Inches(0.9),
           "The full build guide", size=34, bold=True, color=WHITE)
    d.rule(s, Inches(1.95), colour=ACCENT)
    d.text(s, Inches(0.9), Inches(2.3), Inches(6.8), Inches(3.2),
           "Every chapter, every control, every command.\n\n"
           "The full source, the attack suite, the evaluations, the Cloudflare "
           "Worker and the CI gate.\n\n"
           "Every number was produced by a run you can repeat on your own "
           "machine, for nothing.", size=17, color=MIST, spacing=1.2)
    price = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.3),
                               Inches(2.3), Inches(4.0), Inches(2.6))
    price.fill.solid()
    price.fill.fore_color.rgb = ACCENT
    price.line.fill.background()
    price.shadow.inherit = False
    price.text_frame.text = ""
    d.text(s, Inches(8.3), Inches(2.7), Inches(4.0), Inches(1.0),
           "${}".format(C.GUIDE_PRICE_USD), size=64, bold=True, color=WHITE,
           align=PP_ALIGN.CENTER)
    d.text(s, Inches(8.3), Inches(3.9), Inches(4.0), Inches(0.8),
           "one guide, the whole project", size=15, color=WHITE, align=PP_ALIGN.CENTER)
    d.text(s, Inches(0.9), Inches(5.8), Inches(11.5), Inches(0.6),
           "The video is free. The guide is how you build it yourself.",
           size=16, italic=True, color=MIST)
    d.footer(s, 9, dark=True)

    # 10 close
    s = d.slide()
    d.text(s, Inches(0.9), Inches(1.4), Inches(11.5), Inches(1.0),
           "Build it. Break it. Then put Warden in front.", size=36, bold=True)
    d.rule(s, Inches(2.6))
    d.text(s, Inches(0.9), Inches(3.0), Inches(7.5), Inches(2.2),
           "{}\n{}\n\nYouTube, Upwork, Fiverr and LinkedIn are all linked from "
           "the site.".format(C.BRAND, C.BRAND_SITE), size=20, color=GREY, spacing=1.3)
    if headshot.exists():
        s.shapes.add_picture(str(headshot), Inches(9.3), Inches(2.6), height=Inches(3.0))
    d.text(s, Inches(9.3), Inches(5.75), Inches(3.3), Inches(0.7),
           "{}\n{}".format(C.AUTHOR, C.AUTHOR_TITLE), size=12, bold=True)
    d.footer(s, 10)
    return d


def main() -> int:
    mpath = ROOT / "results/manifest.json"
    if not mpath.exists():
        raise SystemExit("results/manifest.json missing. Run python scripts/run_all.py")
    m = json.loads(mpath.read_text(encoding="utf-8"))
    d = build(m)
    out = ROOT / "ppt/Warden_Project_Overview.pptx"
    out.parent.mkdir(parents=True, exist_ok=True)
    d.prs.save(str(out))

    problems = []
    for i, slide in enumerate(d.prs.slides, 1):
        for shape in slide.shapes:
            if shape.shape_type in (MSO_SHAPE.CHEVRON, MSO_SHAPE.RIGHT_ARROW):
                if shape.has_text_frame and shape.text_frame.text.strip():
                    problems.append("slide {}: text in an arrow/chevron".format(i))
            if shape.left is not None and shape.left + (shape.width or 0) > W + Emu(1000):
                problems.append("slide {}: shape overflows right edge".format(i))
            if shape.top is not None and shape.top + (shape.height or 0) > H + Emu(1000):
                problems.append("slide {}: shape overflows bottom edge".format(i))
    if problems:
        for p in problems:
            print("LAYOUT:", p, file=sys.stderr)
        return 1
    print("Wrote {}".format(out))
    print("  slides {}".format(len(d.prs.slides._sldIdLst)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
