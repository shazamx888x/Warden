"""Build the YouTube thumbnail.

    python scripts/build_thumbnail.py --part 1

1280 by 720, readable at 320 by 180 (the size most people see it at): at most
three words of headline, one number, nothing smaller than about 28 pixels. It
writes a 320-wide legibility preview too.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SERIES_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from warden import constants as C  # noqa: E402

W, H = 1280, 720
FONT_DIRS = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")]
FONTS = {
    "black": ["poppins-bold.ttf", "Poppins-Bold.ttf", "arialbd.ttf", "seguibl.ttf", "DejaVuSans-Bold.ttf"],
    "bold": ["poppins-semibold.ttf", "arialbd.ttf", "seguisb.ttf", "DejaVuSans-Bold.ttf"],
    "regular": ["poppins-regular.ttf", "arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"],
}


def font(kind, size):
    for d in FONT_DIRS:
        if not d.exists():
            continue
        for name in FONTS[kind]:
            if (d / name).exists():
                return ImageFont.truetype(str(d / name), size)
    return ImageFont.load_default()


def rgb(v):
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


INK = rgb(C.COLOR_INK)
ACCENT = rgb(C.COLOR_ACCENT)
AMBER = rgb(C.COLOR_AMBER)
GREEN = rgb(C.COLOR_GREEN)
WHITE = rgb(C.COLOR_WHITE)
MIST = rgb(C.COLOR_MIST)
HEADSHOT_BG = (0x0F, 0x17, 0x24)


def tw(draw, text, f):
    box = draw.textbbox((0, 0), text, font=f)
    return box[2] - box[0]


def build(part, m):
    img = Image.new("RGB", (W, H), INK)
    glow = Image.new("RGB", (W, H), INK)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 620, -160, W + 200, H + 160], fill=(120, 25, 85))
    glow = glow.filter(ImageFilter.GaussianBlur(110))
    img = Image.blend(img, glow, 0.75)
    draw = ImageDraw.Draw(img)

    draw.rectangle([64, 92, 214, 100], fill=ACCENT)
    draw.text((64, 122), "I BUILT AN", font=font("bold", 52), fill=MIST)
    draw.text((64, 184), "AI AGENT", font=font("black", 84), fill=WHITE)
    draw.text((64, 282), "THEN HIJACKED IT", font=font("black", 74), fill=ACCENT)

    r = m["redteam"]
    naive = "{:.0f}%".format(r["naive_breach_rate"] * 100)
    after = "{:.0f}%".format(r["gateway_breach_rate"] * 100)
    draw.text((64, 420), "ATTACKS THAT WORKED", font=font("bold", 26), fill=MIST)
    big = font("black", 92)
    draw.text((64, 452), naive, font=big, fill=AMBER)
    ax = 64 + tw(draw, naive, big) + 30
    draw.polygon([(ax, 508), (ax + 54, 508), (ax + 54, 492), (ax + 92, 516),
                  (ax + 54, 540), (ax + 54, 524), (ax, 524)], fill=WHITE)
    draw.text((ax + 112, 452), after, font=big, fill=GREEN)
    draw.text((64, 568), "then I put a firewall in front", font=font("regular", 30), fill=MIST)

    headshot = SERIES_ROOT / "Haseeb formal.jpeg"
    if headshot.exists():
        photo = Image.open(headshot).convert("RGB")
        th = 470
        ratio = th / photo.height
        photo = photo.resize((int(photo.width * ratio), th), Image.LANCZOS)
        px, py = W - photo.width - 60, H - th - 40
        pad = 16
        draw.rounded_rectangle([px - pad, py - pad, px + photo.width + pad, py + photo.height + pad],
                               radius=18, fill=HEADSHOT_BG, outline=ACCENT, width=4)
        img.paste(photo, (px, py))
        draw = ImageDraw.Draw(img)

    bw, bh = 178, 56
    bx, by = W - bw - 60, 44
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=10, fill=ACCENT)
    label = "PART {}".format(part)
    lf = font("black", 32)
    draw.text((bx + (bw - tw(draw, label, lf)) // 2, by + 10), label, font=lf, fill=WHITE)

    draw.text((64, H - 62), C.PROJECT_NAME, font=font("black", 34), fill=WHITE)
    nw = tw(draw, C.PROJECT_NAME, font("black", 34))
    draw.text((64 + nw + 18, H - 54), C.BRAND, font=font("regular", 24), fill=MIST)
    return img


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build the Warden thumbnail")
    ap.add_argument("--part", type=int, default=1)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    mpath = ROOT / "results/manifest.json"
    if not mpath.exists():
        raise SystemExit("results/manifest.json missing. Run python scripts/run_all.py")
    m = json.loads(mpath.read_text(encoding="utf-8"))
    img = build(args.part, m)

    out = Path(args.out) if args.out else (
        SERIES_ROOT / "Warden_Thumbnail_Part{}.png".format(args.part))
    img.save(out, "PNG")
    (ROOT / "assets").mkdir(exist_ok=True)
    img.resize((320, 180), Image.LANCZOS).save(ROOT / "assets/thumbnail_preview_320.png", "PNG")
    img.save(ROOT / "assets/thumbnail_full.png", "PNG")
    print("Wrote {}".format(out))
    print("  {} by {}, preview at assets/thumbnail_preview_320.png".format(img.width, img.height))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
