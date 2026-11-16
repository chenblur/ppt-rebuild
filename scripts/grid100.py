#!/usr/bin/env python3
"""grid100 - overlay a labelled coordinate grid on any image.

A *visual ruler* for measuring element positions in screenshots, slide captures,
design mockups or dataset images. It does NOT detect layout automatically: it
prints a ruler onto a copy of the image so a human (or a vision-capable model)
can read x/y coordinates straight off the picture.

Labels always refer to SOURCE pixels (or to source percentages in --percent
mode). --scale only enlarges the canvas for legibility and never changes the
numbers printed on it.

Two coordinate systems
----------------------
  pixel mode (default)  one line every STEP source pixels, labelled 0,100,200...
                        Use this when the downstream builder takes pixel
                        coordinates, e.g. python-pptx / slidekit rebuilds.
  --percent mode        one line every N% of width/height, labelled 0..100.
                        Use this when transferring a layout between different
                        image sizes; step is a percentage, default 10.

Examples
--------
  python grid100.py page.png
  python grid100.py page.png -o grid.png --step 50 --major 5
  python grid100.py page.png --percent --scale 1.6
  python grid100.py ref/ -o grids/ --step 100 --alpha 0.45
  python grid100.py crop.png --origin 38 44
  python grid100.py --help

Requires: Pillow only (no numpy / OpenCV). Python 3.8+.
The source image is never modified; output goes to a new file.
"""

import argparse
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
RESAMPLE_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS

# Cross-platform font candidates. Falls back to Pillow's built-in bitmap font.
FONT_CANDIDATES = (
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/consola.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
)


def load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def parse_color(value, name):
    try:
        return ImageColor.getcolor(value, "RGB")
    except (ValueError, AttributeError):
        raise SystemExit(f"invalid --{name}: {value!r} (use '#RRGGBB' or a colour name)")


def collect_inputs(src):
    if os.path.isfile(src):
        return [src]
    if os.path.isdir(src):
        files = [
            os.path.join(src, n)
            for n in sorted(os.listdir(src))
            if os.path.splitext(n)[1].lower() in IMAGE_EXTS
            and os.path.isfile(os.path.join(src, n))
        ]
        if not files:
            raise SystemExit(f"no images found in {src}")
        return files
    raise SystemExit(f"not a file or directory: {src}")


def draw_grid(src, dst, args):
    with Image.open(src) as im:
        base = im.convert("RGBA")
    w0, h0 = base.size

    scale = args.scale
    W = max(1, int(round(w0 * scale)))
    H = max(1, int(round(h0 * scale)))
    canvas = base.resize((W, H), RESAMPLE_LANCZOS) if scale != 1.0 else base.copy()

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    cx = parse_color(args.color_x, "color-x")
    cy = parse_color(args.color_y, "color-y")
    alpha = int(round(args.alpha * 255))
    thin = cx + (alpha,)
    thin_y = cy + (alpha,)
    strong = cx + (255,)
    strong_y = cy + (255,)

    percent_mode = args.percent is not None
    step = args.percent if percent_mode else args.step
    ox, oy = (0, 0) if percent_mode else args.origin

    if percent_mode:
        ticks = [*range(0, 100, step), 100]
        xs = [(p, int(round(p / 100 * W))) for p in ticks]
        ys = [(p, int(round(p / 100 * H))) for p in ticks]
        unit = f"{step}%"
    else:
        xs = [(v, int(round(v * scale))) for v in range(0, w0 + 1, step)]
        ys = [(v, int(round(v * scale))) for v in range(0, h0 + 1, step)]
        unit = f"{step}px"

    # Vertical lines + top labels.
    f = load_font(max(8, int(round(args.label_size * max(1.0, scale)))))
    for i, (v, px) in enumerate(xs):
        px = min(px, W - 1)
        col = strong if args.major > 0 and i % args.major == 0 else thin
        width = args.width + (1 if args.major > 0 and i % args.major == 0 else 0)
        d.line([(px, 0), (px, H - 1)], fill=col, width=width)
    for i, (v, py) in enumerate(ys):
        py = min(py, H - 1)
        col = strong_y if args.major > 0 and i % args.major == 0 else thin_y
        width = args.width + (1 if args.major > 0 and i % args.major == 0 else 0)
        d.line([(0, py), (W - 1, py)], fill=col, width=width)

    if not args.no_labels:
        max_x_label = str(max(v for v, _ in xs) + (0 if percent_mode else ox))
        max_y_label = str(max(v for v, _ in ys) + (0 if percent_mode else oy))
        probe = d.textbbox((0, 0), max_x_label, font=f)
        text_w = probe[2] - probe[0]
        line_px_x = max(1, step * scale) if not percent_mode else max(1, step / 100 * W)
        line_px_y = max(1, step * scale) if not percent_mode else max(1, step / 100 * H)
        every_x = max(1, math.ceil((text_w + 12) / line_px_x))
        every_y = max(1, math.ceil((text_w + 12) / line_px_y))

        for i, (v, px) in enumerate(xs):
            if i % every_x:
                continue
            txt = str(v) if percent_mode else str(v + ox)
            _tag(d, px + 3, 2, txt, f, cx, W, H)
        for i, (v, py) in enumerate(ys):
            if i % every_y or i == 0:  # i == 0 would collide with the top-axis "0"
                continue
            txt = str(v) if percent_mode else str(v + oy)
            _tag(d, 2, py + 3, txt, f, cy, W, H)

    out = Image.alpha_composite(canvas, layer).convert("RGB")
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "xb") as stream:
        out.save(stream, format="PNG")
    print(f"{dst}  source={w0}x{h0}  canvas={W}x{H}  "
          f"grid={unit}  lines={len(xs)}x{len(ys)}  "
          f"mode={'percent' if percent_mode else 'pixel+origin(' + str(ox) + ',' + str(oy) + ')'}")


def _tag(draw, x, y, text, font, color, W, H):
    """A small opaque white backing keeps labels readable on any background."""
    probe = draw.textbbox((0, 0), text, font=font)
    tw, th = probe[2] - probe[0], probe[3] - probe[1]
    x = max(1, min(x, W - tw - 4))  # keep the last edge label inside the canvas
    y = max(1, min(y, H - th - 4))
    box = draw.textbbox((x, y), text, font=font)
    draw.rectangle((box[0] - 2, box[1] - 1, box[2] + 2, box[3] + 1),
                   fill=(255, 255, 255, 225))
    draw.text((x, y), text, font=font, fill=color + (255,))


def build_parser():
    p = argparse.ArgumentParser(
        description="Overlay a labelled coordinate grid on an image (a visual ruler).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Labels use source pixels or percentages; --scale never changes their values.",
    )
    p.add_argument("src", help="image file or directory of images")
    p.add_argument("-o", "--out", help="output file (single input) or directory (batch)")
    p.add_argument("--step", type=int, default=100, help="pixel spacing, default 100")
    p.add_argument("--percent", nargs="?", const=10, type=int, default=None,
                   metavar="PCT", help="switch to percentage grid, default 10%% per line")
    p.add_argument("--scale", type=float, default=1.0,
                   help="enlarge canvas for legibility, default 1.0")
    p.add_argument("--alpha", type=float, default=0.55,
                   help="line opacity 0..1, default 0.55")
    p.add_argument("--major", type=int, default=5,
                   help="bold every Nth line, 0 disables, default 5")
    p.add_argument("--width", type=int, default=1, help="minor line width, default 1")
    p.add_argument("--color-x", default="#E02424", help="vertical line colour")
    p.add_argument("--color-y", default="#1B52D8", help="horizontal line colour")
    p.add_argument("--origin", nargs=2, type=int, default=(0, 0), metavar=("X", "Y"),
                   help="offset added to labels, for crops cut from a larger image")
    p.add_argument("--label-size", type=int, default=12, help="label font size, default 12")
    p.add_argument("--no-labels", action="store_true", help="draw lines only")
    return p


def main():
    args = build_parser().parse_args()
    if args.percent is not None and not 1 <= args.percent <= 100:
        raise SystemExit("--percent must be between 1 and 100")
    if args.step <= 0:
        raise SystemExit("--step must be > 0")
    if not 0.1 <= args.scale <= 8:
        raise SystemExit("--scale must be between 0.1 and 8")
    if not 0 < args.alpha <= 1:
        raise SystemExit("--alpha must be in (0, 1]")
    if args.major < 0 or args.width < 1 or args.label_size < 8:
        raise SystemExit("--major >= 0, --width >= 1, --label-size >= 8")
    if args.percent is not None and args.origin != (0, 0):
        print("note: --origin is ignored in --percent mode", file=sys.stderr)

    files = collect_inputs(args.src)
    batch = len(files) > 1 or os.path.isdir(args.src)

    outputs = []
    for src in files:
        if batch:
            outdir = args.out or os.path.join(os.path.dirname(os.path.abspath(src)), "grids")
            stem = os.path.splitext(os.path.basename(src))[0]
            dst = os.path.join(outdir, stem + "_grid.png")
        else:
            dst = args.out or os.path.join(
                os.path.dirname(os.path.abspath(src)),
                os.path.splitext(os.path.basename(src))[0] + "_grid.png",
            )
        outputs.append(Path(dst).resolve())

    if len(set(outputs)) != len(outputs):
        raise SystemExit("input names collide in the output directory; rename the inputs or run them separately")
    for dst in outputs:
        if dst.suffix.lower() != ".png":
            raise SystemExit(f"output must be a PNG file: {dst}")
        if dst.exists():
            raise SystemExit(f"output already exists: {dst}")
    for src, dst in zip(files, outputs):
        try:
            draw_grid(src, dst, args)
        except OSError as exc:
            raise SystemExit(f"cannot process {src}: {exc}") from None
    print(f"done: {len(files)} image(s)")


if __name__ == "__main__":
    main()
