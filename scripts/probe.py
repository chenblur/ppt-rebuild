"""probe — measure a reference screenshot so the rebuild can be numeric, not vibes.

Subcommands
-----------
  grid    <img> [out.png] [step=10] [scale=1.6]
      Overlay a labelled percent grid. Read element positions straight off it.
  zoom    <img> x0 y0 x1 y1 [scale=3] [out.png]
      Crop + upscale a region to read small text / count pixels. Also prints the
      crop's fraction-of-image box, so a measurement converts to slide fractions.
  palette <img> [k=14]
      k-means dominant colours with coverage % and bbox.
  bbox    <img>
      Content bounding box (non-white), to learn the page margins.
  row     <img> y [thr]        dark-pixel x clusters on a row
  col     <img> x [thr]        dark-pixel y clusters on a column
  panels  <img>                background tint panels (blue / green / peach) bboxes
  poly    <img> [min_area] [--eps .02] [--maxv 8]
      Extract dark-outline polygons (3D slabs, slanted blocks, beveled cards).
      Prints the vertex list AND writes <img>_poly.png annotated with indices.

Examples
--------
  python probe.py grid  ref/p1.jpg            # then LOOK at p1_grid.png
  python probe.py zoom  ref/p1.jpg 60 300 700 480 4
  python probe.py poly  ref/p3.jpg 1500 --eps .025 --maxv 6
  python probe.py col   ref/p1.jpg 120
"""
import sys

import numpy as np
import cv2


def load(p):
    img = cv2.imread(p, cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"cannot read {p}")
    return img


# ------------------------------------------------------------------ grid
def grid(img, path, out=None, step=10, scale=1.6):
    h, w = img.shape[:2]
    canvas = cv2.resize(img, (int(w * scale), int(h * scale)),
                        interpolation=cv2.INTER_LANCZOS4)
    H, W = canvas.shape[:2]
    for p in range(0, 101, step):
        x, y = min(int(p / 100 * W), W - 1), min(int(p / 100 * H), H - 1)
        col = (0, 0, 255) if p % 20 == 0 else (0, 200, 255)
        cv2.line(canvas, (x, 0), (x, H - 1), col, 1)
        cv2.line(canvas, (0, y), (W - 1, y), col, 1)
    for p in range(0, 101, step):
        x, y = min(int(p / 100 * W), W - 1), min(int(p / 100 * H), H - 1)
        col = (0, 0, 255) if p % 20 == 0 else (0, 160, 220)
        cv2.putText(canvas, str(p), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, .42, col, 1, cv2.LINE_AA)
        if p:
            cv2.putText(canvas, str(p), (2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, .42, col, 1, cv2.LINE_AA)
    out = out or path.rsplit(".", 1)[0] + "_grid.png"
    cv2.imwrite(out, canvas)
    print(f"wrote {out}  {W}x{H}  (grid {step}% of source {w}x{h})")


# ------------------------------------------------------------------ zoom
def zoom(img, path, x0, y0, x1, y1, scale=3.0, out=None):
    h, w = img.shape[:2]
    x0, x1 = max(0, min(x0, w)), max(0, min(x1, w))
    y0, y1 = max(0, min(y0, h)), max(0, min(y1, h))
    crop = img[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]
    big = cv2.resize(crop, (int(cw * scale), int(ch * scale)),
                     interpolation=cv2.INTER_LANCZOS4)
    out = out or f"{path.rsplit('.', 1)[0]}_zoom_{x0}_{y0}_{x1}_{y1}.png"
    cv2.imwrite(out, big)
    print(f"crop px=({x0},{y0})-({x1},{y1}) size={cw}x{ch} scale={scale}")
    print(f"frac x [{x0/w:.4f},{x1/w:.4f}]  y [{y0/h:.4f},{y1/h:.4f}]  (source {w}x{h})")
    print("wrote", out)


# ------------------------------------------------------------------ palette
def palette(img, k=14):
    h, w = img.shape[:2]
    small = cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    data = small.reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, .5)
    _, labels, centers = cv2.kmeans(data, k, None, crit, 6, cv2.KMEANS_PP_CENTERS)
    labels = labels.ravel()
    counts = np.bincount(labels, minlength=k)
    rows = []
    for i in range(k):
        if not counts[i]:
            continue
        b, g, r = [int(round(v)) for v in centers[i]]
        m = (labels == i).reshape(small.shape[:2])
        ys, xs = np.where(m)
        rows.append((100.0 * counts[i] / len(labels), f"#{r:02X}{g:02X}{b:02X}",
                     (int(xs.min() * 2), int(ys.min() * 2), int(xs.max() * 2), int(ys.max() * 2))))
    rows.sort(reverse=True)
    print(f"{'%':>6}  {'hex':8}  bbox(px)")
    for pct, hexv, bb in rows:
        print(f"{pct:6.2f}  {hexv:8}  {bb}")


# ------------------------------------------------------------------ bbox / row / col
def bbox(img):
    g = img.mean(axis=2)
    ys, xs = np.where(g < 248)
    print(f"content bbox px: x {xs.min()}..{xs.max()}  y {ys.min()}..{ys.max()}"
          f"   (w={xs.max()-xs.min()} h={ys.max()-ys.min()})")


def _clusters(idx, gap=3):
    if not len(idx):
        return []
    out, s, p = [], idx[0], idx[0]
    for v in idx[1:]:
        if v - p > gap:
            out.append((int(s), int(p)))
            s = v
        p = v
    out.append((int(s), int(p)))
    return out


def row(img, y, thr=120):
    idx = np.where(img[y].mean(axis=1) < thr)[0]
    print(f"row y={y}: {len(idx)} dark px; x clusters:", _clusters(idx))


def col(img, x, thr=120):
    idx = np.where(img[:, x].mean(axis=1) < thr)[0]
    print(f"col x={x}: {len(idx)} dark px; y clusters:", _clusters(idx))


# ------------------------------------------------------------------ panels
def panels(img):
    b, g, r = [img[..., i].astype(np.int16) for i in range(3)]
    mx, mn = img.max(axis=2).astype(np.int16), img.min(axis=2).astype(np.int16)
    sat, bright = mx - mn, mx
    masks = {
        "pale-blue": ((b > r + 4) & (b > g + 1) & (bright > 200) & (sat < 60)),
        "pale-green": ((g > b + 4) & (g > r + 2) & (bright > 190) & (sat < 70)),
        "pale-peach": ((r > b + 8) & (r > g * .98) & (bright > 190) & (sat < 75)),
    }
    h, w = img.shape[:2]
    for name, m in masks.items():
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        big = sorted([s for s in stats[1:] if s[4] > 4000], key=lambda s: -s[4])[:3]
        for x, y, ww, hh, a in big:
            print(f"{name:11s} x={x:4d} y={y:4d} w={ww:4d} h={hh:4d} area={a:7d}"
                  f"  frac=({x/w:.3f},{y/h:.3f},{ww/w:.3f},{hh/h:.3f})")


# ------------------------------------------------------------------ poly
def poly(img, path, min_area=1200, eps=.02, maxv=8, thr=110):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    dark = (g < thr).astype(np.uint8) * 255
    dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cnts, _ = cv2.findContours(dark, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a < min_area:
            continue
        ap = cv2.approxPolyDP(c, eps * cv2.arcLength(c, True), True)
        if not (3 <= len(ap) <= maxv):
            continue
        pts = [(int(p[0][0]), int(p[0][1])) for p in ap]
        clean = []
        for p in pts:
            if not clean or abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1]) > 2:
                clean.append(p)
        if len(clean) >= 3:
            out.append((int(a), clean))
    out.sort(key=lambda d: -d[0])
    vis = img.copy()
    for i, (a, pts) in enumerate(out):
        cv2.polylines(vis, [np.array(pts, np.int32).reshape(-1, 1, 2)], True, (0, 0, 255), 1)
        cx, cy = int(np.mean([p[0] for p in pts])), int(np.mean([p[1] for p in pts]))
        cv2.putText(vis, str(i), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 0, 255), 2)
        print(f"[{i:2d}] area={a:6d} n={len(pts)}  {pts}")
    out_png = path.rsplit(".", 1)[0] + "_poly.png"
    cv2.imwrite(out_png, vis)
    print("annotated ->", out_png, " (look at it to map indices to objects)")


# ------------------------------------------------------------------ cli
def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    cmd, path = a[0], a[1]
    img = load(path)
    if cmd == "grid":
        grid(img, path, a[2] if len(a) > 2 else None,
             int(a[3]) if len(a) > 3 else 10,
             float(a[4]) if len(a) > 4 else 1.6)
    elif cmd == "zoom":
        zoom(img, path, int(a[2]), int(a[3]), int(a[4]), int(a[5]),
             float(a[6]) if len(a) > 6 else 3.0,
             a[7] if len(a) > 7 else None)
    elif cmd == "palette":
        palette(img, int(a[2]) if len(a) > 2 else 14)
    elif cmd == "bbox":
        bbox(img)
    elif cmd == "row":
        row(img, int(a[2]), int(a[3]) if len(a) > 3 else 120)
    elif cmd == "col":
        col(img, int(a[2]), int(a[3]) if len(a) > 3 else 120)
    elif cmd == "panels":
        bbox(img)
        panels(img)
    elif cmd == "poly":
        ma, eps, maxv, rest = 1200, .02, 8, a[2:]
        i = 0
        while i < len(rest):
            if rest[i] == "--eps":
                eps = float(rest[i + 1]); i += 2
            elif rest[i] == "--maxv":
                maxv = int(rest[i + 1]); i += 2
            else:
                ma = int(rest[i]); i += 1
        poly(img, path, ma, eps, maxv)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
