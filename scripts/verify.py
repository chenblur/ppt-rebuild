"""verify — is the rebuild actually close? Two numbers and one picture.

    python verify.py ref.jpg render.png out_prefix

Writes
  out_prefix_sbs.png      reference | rebuild | abs-diff  (the picture you look at)
  out_prefix_overlay.png  50/50 blend — misalignment shows as ghosting

Prints
  MAE  (mean abs error, lower is better; <15 is close, <8 is very close)
  edge agreement (does the rebuild put lines where the reference has lines)
  3x3 regional MAE (tells you WHICH corner is drifting, instead of guessing)

Extras
  --ren-crop=x0,y0,x1,y1   compare only a sub-rect of the render (for a
                           near-square figure centred on a 16:9 page)
  --width N                normalise both to N px wide (default 1338)

Reading the numbers honestly
  * a JPEG screenshot carries compression noise, so MAE has a floor: do not
    chase it below ~6.
  * the 3x3 grid is the useful part — a uniform 20+ somewhere means an element
    is missing or misplaced, not "the font is slightly off".
  * always look at the sbs image. The numbers rank problems; the picture decides.
"""
import argparse
import os

import numpy as np
from PIL import Image, ImageDraw


def _arr(im, size):
    return np.asarray(im.resize(size, Image.LANCZOS), dtype=np.float32)


def verify(ref, ren, prefix=None, width=1338, ren_crop=None):
    r_img = Image.open(ref).convert("RGB")
    h = int(round(width * r_img.height / r_img.width))
    s = _arr(r_img, (width, h))

    b_img = Image.open(ren).convert("RGB")
    if ren_crop:
        b_img = b_img.crop(tuple(ren_crop))
    b = _arr(b_img, (width, h))

    d = np.abs(s - b)
    mae = float(d.mean())

    gs = np.abs(np.gradient(s.mean(axis=2))[0]) + np.abs(np.gradient(s.mean(axis=2))[1])
    gb = np.abs(np.gradient(b.mean(axis=2))[0]) + np.abs(np.gradient(b.mean(axis=2))[1])
    edge = 1.0 - np.abs(gs - gb).mean() / (np.abs(gs).mean() + 1e-6)

    reg = [[round(float(d[j * h // 3:(j + 1) * h // 3, i * width // 3:(i + 1) * width // 3].mean()), 1)
            for i in range(3)] for j in range(3)]

    print(f"MAE(all) = {mae:6.2f}        edge-agreement = {edge:+.3f}")
    print("regional MAE 3x3 (rows top->bottom, cols left->right):")
    for r in reg:
        print("   ", r)
    worst = max(((reg[j][i], j, i) for j in range(3) for i in range(3)))
    names = [["左上", "中上", "右上"], ["左中", "正中", "右中"], ["左下", "中下", "右下"]]
    print(f"worst cell: {names[worst[1]][worst[2]]} = {worst[0]}  <- look here first")

    if prefix:
        heat = np.zeros((h, width, 3), np.float32)
        g = np.clip(d.mean(axis=2) * 2.2, 0, 255)
        heat[..., 0] = g
        heat[..., 1] = 255 - g * .55
        strip = np.concatenate([s, np.full((h, 8, 3), 40.), b,
                                np.full((h, 8, 3), 40.), heat], axis=1)
        im = Image.fromarray(strip.astype(np.uint8))
        dr = ImageDraw.Draw(im)
        for k, t in enumerate(("reference", "rebuild", "abs diff")):
            dr.text((k * (width + 8) + 4, 3), t, fill=(255, 60, 60))
        im.save(prefix + "_sbs.png")
        Image.fromarray((s * .5 + b * .5).astype(np.uint8)).save(prefix + "_overlay.png")
        print("wrote", prefix + "_sbs.png", "and", prefix + "_overlay.png")
    return mae


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("render")
    ap.add_argument("prefix", nargs="?")
    ap.add_argument("--width", type=int, default=1338)
    ap.add_argument("--ren-crop", default="")
    a = ap.parse_args()
    crop = [int(v) for v in a.ren_crop.split(",")] if a.ren_crop else None
    verify(a.ref, a.render, a.prefix, a.width, crop)


if __name__ == "__main__":
    main()
