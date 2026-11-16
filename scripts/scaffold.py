"""scaffold — lay out a replica project and emit runnable stubs.

    python scaffold.py --src ref/ --out work/ [--name deck]

Creates
    work/
      src/            (copied reference screenshots)
      assets/
      build/  slidekit.py  build.py  p1.py p2.py ...
      out/

`p1.py` is a runnable template: fill in the measured numbers, then

    cd work/build
    python p1.py            # build one page + render it to out/p1/slide-01.png
    python build.py --render  # assemble every page and render the whole deck

Why a per-page module: one page = one file means several agents can work in
parallel on disjoint files with a frozen shared kit, and you can re-render a
single page in ~3 seconds while iterating.
"""
import argparse
import glob
import os
import shutil
import sys

PAGE_TMPL = '''"""{name} — replica of {src}

Work in the REFERENCE IMAGE's pixel coordinates ({w}x{h}); Canvas maps them to
the slide. Measure with:
    python ../scripts/probe.py grid {src}      # then LOOK at {stem}_grid.png
    python ../scripts/probe.py zoom {src} x0 y0 x1 y1 3
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slidekit as K

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = "{src}"
SRC_PX = ({w}, {h})


def build(prs):
    c = K.page(prs, SRC, SRC_PX, src_dir=os.path.join(ROOT, "src"),
               assets_dir=os.path.join(ROOT, "assets"))
    c.bg("#FFFFFF")

    # ---- 1. page furniture (header band, rule, footer) -------------------
    # c.rect(<x>, <y>, <w>, <h>, fill="#1F4E9C")

    # ---- 2. the big blocks (banners / columns / cards) -------------------
    # c.rect(x, y, w, h, fill="#E9EDF8", line="#3A6FB5", lw=1.0)

    # ---- 3. text --------------------------------------------------------
    # c.text(x, y, w, h, "标题", size=K.Pt(24), bold=True, color="#12305C")
    # c.rtext(cx, cy, 150, 18, "旋转标签", angle=-37, size=K.Pt(11))

    # ---- 4. pictures (cover-cropped, never stretched) -------------------
    # p = c.crop(SRC, x0, y0, x1, y1, scale=2)
    # c.pic(p, x, y, w, h)

    return c


if __name__ == "__main__":
    import devbox
    devbox.preview(__file__, ROOT)
'''

BUILD_TMPL = '''"""build — assemble every page module into one deck.

    python build.py            build + save ../out/{name}.pptx
    python build.py --render   ... and render every slide to ../out/final/
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import slidekit as K
import devbox

PAGES = sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(HERE, "p*.py"))
               if not os.path.basename(p).startswith("_"))


def build_deck():
    prs = K.new_deck()
    for name in PAGES:
        mod = devbox.load(os.path.join(HERE, name + ".py"))
        mod.build(prs)
        print("  ok ", name)
    return prs


def main():
    prs = build_deck()
    out = os.path.join(ROOT, "out")
    os.makedirs(out, exist_ok=True)
    pptx = os.path.join(out, "{name}.pptx")
    prs.save(pptx)
    print("saved", pptx, f"{{os.path.getsize(pptx)/1e6:.2f}} MB")
    if "--render" in sys.argv:
        devbox.render(pptx, os.path.join(out, "final"))


if __name__ == "__main__":
    main()
'''

DEVBOX_TMPL = '''"""devbox — iterate on ONE page module and look at the result.

`python p1.py`  ->  builds a 1-page deck and renders it to ../out/p1/slide-01.png
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.environ.get("PPT_REPLICA_SCRIPTS") or ""


def load(module_file):
    name = os.path.splitext(os.path.basename(module_file))[0]
    spec = importlib.util.spec_from_file_location(name, module_file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def render(pptx, outdir):
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (SKILL, os.path.join(here, "scripts"),
                 os.path.expanduser("~/.agents/skills/ppt-rebuild/scripts")):
        if cand and os.path.exists(os.path.join(cand, "render.py")):
            sys.path.insert(0, cand)
            import render as R
            with R.Clock(R.LOCK):
                return R.render(pptx, outdir)
    raise SystemExit("render.py not found — set PPT_REPLICA_SCRIPTS")


def preview(module_file, root):
    import slidekit as K
    mod = load(module_file)
    prs = K.new_deck()
    mod.build(prs)
    name = os.path.splitext(os.path.basename(module_file))[0]
    out = os.path.join(root, "out")
    os.makedirs(out, exist_ok=True)
    pptx = os.path.join(out, name + ".pptx")
    prs.save(pptx)
    made = render(pptx, os.path.join(out, name))
    print("pptx   :", pptx)
    for m in made:
        print("render :", m)
    return made
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="src")
    ap.add_argument("--out", default="work")
    ap.add_argument("--name", default="replica")
    a = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.abspath(a.src)
    out = os.path.abspath(a.out)
    build = os.path.join(out, "build")
    for d in (os.path.join(out, "src"), os.path.join(out, "assets"),
              build, os.path.join(out, "out")):
        os.makedirs(d, exist_ok=True)

    # reference screenshots
    refs = []
    for pat in ("*.jpg", "*.jpeg", "*.png"):
        refs += glob.glob(os.path.join(src_dir, pat))
    refs = sorted(r for r in refs if "_grid" not in r and "_zoom" not in r and "_poly" not in r)
    if not refs:
        raise SystemExit(f"no reference images in {src_dir}")
    for r in refs:
        base = os.path.basename(r)
        dst = os.path.join(out, "src", base)
        if os.path.abspath(r) != os.path.abspath(dst):
            shutil.copy2(r, dst)

    # shared kit
    shutil.copy2(os.path.join(here, "slidekit.py"), os.path.join(build, "slidekit.py"))
    open(os.path.join(build, "devbox.py"), "w", encoding="utf-8").write(DEVBOX_TMPL)
    open(os.path.join(build, "build.py"), "w", encoding="utf-8").write(
        BUILD_TMPL.replace("{name}", a.name))

    # one runnable stub per page
    from PIL import Image
    for i, r in enumerate(refs, start=1):
        w, h = Image.open(r).size
        stem = os.path.splitext(os.path.basename(r))[0]
        open(os.path.join(build, f"p{i}.py"), "w", encoding="utf-8").write(
            PAGE_TMPL.format(name=f"p{i}", src=os.path.basename(r), stem=stem,
                             w=w, h=h))
        print(f"  p{i}.py  <- {os.path.basename(r)}  ({w}x{h})")

    print(f"\nscaffold ready: {out}")
    print("next: python probe.py grid src/<ref>   # measure, then fill in p1.py")
    print("      cd build && python p1.py          # build + render one page")


if __name__ == "__main__":
    main()
