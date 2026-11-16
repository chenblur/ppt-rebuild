"""slidekit — build a pixel-faithful PowerPoint slide from a reference screenshot.

THE ONE IDEA
------------
You measure everything in the REFERENCE IMAGE's pixel coordinates, and Canvas
maps those pixels onto the slide. So you never "guess" in slide inches: you read
a number off the screenshot, type that number, done.

    c = K.Canvas(slide, (1338, 798), "ref.jpg", src_dir="src")
    c.rect(56, 7, 1282, 78, fill="#FFFFFF")     # <- these are jpg pixels
    c.text(70, 20, 600, 50, "01 | 示例标题", size=K.Pt(30))

DESIGN RULES THIS LIBRARY ENFORCES FOR YOU
* strips <p:style> from every shape -> no theme shadow/fill surprises
* sets a:latin AND a:ea typefaces -> Chinese renders in the face you asked for
* fills/strokes are always explicit
* pictures placed with pic() are cover-cropped, never stretched
* gradients / outer shadows / glows are injected as raw a: effects

Depends on: python-pptx, Pillow
"""
from __future__ import annotations

import os

from PIL import Image, ImageFilter
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

SLIDE_W = 13.3333          # 16:9 default, override per deck
SLIDE_H = 7.5
FONT = "微软雅黑"           # Microsoft YaHei — change to your reference's face
FONT_LATIN = FONT

_ALIGN = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT,
          "j": PP_ALIGN.JUSTIFY, "d": PP_ALIGN.DISTRIBUTE}
_ANCHOR = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}
_DASH = {None: None, "solid": None, "dash": MSO_LINE_DASH_STYLE.DASH,
         "dot": MSO_LINE_DASH_STYLE.ROUND_DOT,
         "sysdot": MSO_LINE_DASH_STYLE.SQUARE_DOT,
         "lgdash": MSO_LINE_DASH_STYLE.LONG_DASH,
         "dashdot": MSO_LINE_DASH_STYLE.DASH_DOT}


def rgb(c) -> RGBColor:
    if isinstance(c, RGBColor):
        return c
    h = str(c).lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class Canvas:
    def __init__(self, slide, src_px, src_name="", src_dir="src",
                 assets_dir="assets", region=None, contain=False,
                 font=FONT, latin=None):
        self.slide = slide
        self.sw, self.sh = float(src_px[0]), float(src_px[1])
        self.src_name = src_name
        self.src_dir = src_dir
        self.assets_dir = assets_dir
        self.font = font
        self.latin = latin or font
        os.makedirs(assets_dir, exist_ok=True)

        # region = the slide rect (inches) that the SOURCE fills.
        # contain=True keeps the source aspect and centres it (use this for a
        # near-square figure on a 16:9 page — letterboxing beats stretching).
        rx, ry, rw, rh = region if region else (0.0, 0.0, SLIDE_W, SLIDE_H)
        if contain:
            ar_src, ar_reg = self.sw / self.sh, rw / rh
            if ar_src >= ar_reg:
                w, h = rw, rw / ar_src
            else:
                h, w = rh, rh * ar_src
            rx += (rw - w) / 2.0
            ry += (rh - h) / 2.0
            rw, rh = w, h
        self.ox, self.oy = rx, ry
        self.sx = rw / self.sw          # inches per source px
        self.sy = rh / self.sh
        self._cache = {}

    # ------------------------------------------------------------ mapping
    def ix(self, px):
        return Inches(self.ox + px * self.sx)

    def iy(self, py):
        return Inches(self.oy + py * self.sy)

    def iw(self, px):
        return Inches(px * self.sx)

    def ih(self, py):
        return Inches(py * self.sy)

    def box(self, x, y, w, h):
        return self.ix(x), self.iy(y), self.iw(w), self.ih(h)

    def fs(self, glyph_px):
        """Starting point size from a measured glyph height in the reference.

        This is only a STARTING GUESS — the em-box / glyph-height ratio differs
        per typeface. Render once and trust your eyes over the formula.
        """
        return Pt(glyph_px * self.sy * 72.0 * 1.05)

    def px2in(self, px, axis="x"):
        return px * (self.sx if axis == "x" else self.sy)

    # ------------------------------------------------------------ shapes
    def _new(self, shape_type, x, y, w, h):
        sp = self.slide.shapes.add_shape(shape_type, self.ix(x), self.iy(y),
                                         self.iw(max(w, 0.4)), self.ih(max(h, 0.4)))
        st = sp._element.find(qn("p:style"))
        if st is not None:
            sp._element.remove(st)          # kill theme fill/line/shadow
        return sp

    def rect(self, x, y, w, h, fill=None, line=None, lw=1.0, dash=None,
             radius=None, shape=None, rot=0.0, adj=None, alpha=None, angle=90):
        if shape is None:
            shape = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
        sp = self._new(shape, x, y, w, h)
        if radius:
            try:
                sp.adjustments[0] = min(0.5, float(radius))
            except Exception:
                pass
        self._adj(sp, adj)
        if rot:
            sp.rotation = rot
        self._fill(sp, fill, alpha, angle)
        self._line(sp, line, lw, dash)
        return sp

    def shape(self, shape_type, x, y, w, h, fill=None, line=None, lw=1.0,
              dash=None, adj=None, rot=0.0, alpha=None, angle=90):
        sp = self._new(shape_type, x, y, w, h)
        self._adj(sp, adj)
        if rot:
            sp.rotation = rot
        self._fill(sp, fill, alpha, angle)
        self._line(sp, line, lw, dash)
        return sp

    @staticmethod
    def _adj(sp, adj):
        if adj is None:
            return
        for i, v in enumerate(adj):
            try:
                sp.adjustments[i] = v
            except Exception:
                pass

    def _fill(self, sp, fill, alpha=None, angle=90):
        if fill is None:
            sp.fill.background()
        elif isinstance(fill, (list, tuple, dict)):
            self._grad(sp, fill, angle)
        else:
            sp.fill.solid()
            sp.fill.fore_color.rgb = rgb(fill)
            if alpha is not None:
                srgb = sp.fill.fore_color._xFill.find(qn("a:srgbClr"))
                el = srgb.makeelement(qn("a:alpha"), {"val": str(int(alpha * 100000))})
                srgb.append(el)
        sp.shadow.inherit = False
        return sp

    def _line(self, sp, line, lw=1.0, dash=None):
        if line is None:
            sp.line.fill.background()
            return
        if isinstance(line, (list, tuple, dict)):
            self._grad(sp, line, target="ln")
            sp.line.width = Pt(lw)
            return
        sp.line.color.rgb = rgb(line)
        sp.line.width = Pt(lw)
        d = _DASH.get(dash)
        if d is not None:
            sp.line.dash_style = d

    def _grad(self, sp, spec, angle=90, target="fill"):
        """spec: ["#A","#B"] | [(pos,"#A"), ...] | {"stops":[...], "angle":deg}

        angle is in the DrawingML convention: 0 = left->right, 90 = top->bottom.
        """
        if isinstance(spec, dict):
            angle = spec.get("angle", angle)
            spec = spec["stops"]
        if not spec:
            raise ValueError("empty gradient")
        if not isinstance(spec[0], (list, tuple)):
            n = len(spec)
            spec = [(i / max(n - 1, 1), c) for i, c in enumerate(spec)]

        spPr = sp._element.spPr
        if target == "ln":
            host = spPr.find(qn("a:ln"))
            if host is None:
                host = spPr.makeelement(qn("a:ln"), {})
                spPr.append(host)
        else:
            host = spPr
        for t in ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
                  "a:pattFill", "a:grpFill"):
            for el in host.findall(qn(t)):
                host.remove(el)
        gf = host.makeelement(qn("a:gradFill"), {"rotWithShape": "1"})
        lst = gf.makeelement(qn("a:gsLst"), {})
        gf.append(lst)
        for pos, col in spec:
            gs = lst.makeelement(qn("a:gs"), {"pos": str(int(pos * 100000))})
            clr = gs.makeelement(qn("a:srgbClr"), {"val": str(col).lstrip("#").upper()})
            gs.append(clr)
            lst.append(gs)
        gf.append(gf.makeelement(qn("a:lin"),
                                 {"ang": str(int((angle % 360) * 60000)), "scaled": "0"}))
        if target == "ln":
            host.append(gf)
        else:
            ln = spPr.find(qn("a:ln"))
            ln.addprevious(gf) if ln is not None else spPr.append(gf)
        return sp

    def shadow(self, sp, blur=6.0, dist=3.0, direction=270.0,
               color="#000000", alpha=0.30):
        """Outer shadow — the single easiest way to stop vector redraws from
        looking flat next to a designed reference."""
        spPr = sp._element.spPr
        for el in spPr.findall(qn("a:effectLst")):
            spPr.remove(el)
        eff = spPr.makeelement(qn("a:effectLst"), {})
        sh = eff.makeelement(qn("a:outerShdw"), {
            "blurRad": str(int(blur * 12700)), "dist": str(int(dist * 12700)),
            "dir": str(int(direction * 60000)), "algn": "ctr", "rotWithShape": "0"})
        clr = sh.makeelement(qn("a:srgbClr"), {"val": str(color).lstrip("#").upper()})
        clr.append(clr.makeelement(qn("a:alpha"),
                                   {"val": str(int(alpha * 100000))}))
        sh.append(clr)
        eff.append(sh)
        self._put_effect(spPr, eff)
        return sp

    def glow(self, sp, radius=4.0, color="#FFFFFF", alpha=0.55):
        spPr = sp._element.spPr
        for el in spPr.findall(qn("a:effectLst")):
            spPr.remove(el)
        eff = spPr.makeelement(qn("a:effectLst"), {})
        gl = eff.makeelement(qn("a:glow"), {"rad": str(int(radius * 12700))})
        clr = gl.makeelement(qn("a:srgbClr"), {"val": str(color).lstrip("#").upper()})
        clr.append(clr.makeelement(qn("a:alpha"),
                                   {"val": str(int(alpha * 100000))}))
        gl.append(clr)
        eff.append(gl)
        self._put_effect(spPr, eff)
        return sp

    @staticmethod
    def _put_effect(spPr, eff):
        ln = spPr.find(qn("a:ln"))
        ln.addprevious(eff) if ln is not None else spPr.append(eff)

    # ------------------------------------------------------------ text
    def text(self, x, y, w, h, content, size=18, bold=False, color="#000000",
             align="l", valign="t", font=None, latin=None, ls=1.0,
             space_before=0, space_after=0, margins=(0, 0, 0, 0), wrap=True,
             rot=0.0, char_space=None, italic=False, underline=False,
             autofit=False, shape=None):
        """content:
             "one line"
             ["para 1", "para 2"]
             [["black ", ("red", {"color": "#C00000", "bold": True})], "p2"]
        run overrides: color, size, bold, italic, font, underline, char_space
        """
        if shape is None:
            tb = self.slide.shapes.add_textbox(self.ix(x), self.iy(y),
                                               self.iw(w), self.ih(h))
            tf = tb.text_frame
        else:
            tb, tf = shape, shape.text_frame
        tf.word_wrap = wrap
        tf.margin_left, tf.margin_right = Inches(margins[0]), Inches(margins[1])
        tf.margin_top, tf.margin_bottom = Inches(margins[2]), Inches(margins[3])
        tf.vertical_anchor = _ANCHOR[valign]
        if not autofit:
            try:
                from pptx.enum.text import MSO_AUTO_SIZE
                tf.auto_size = MSO_AUTO_SIZE.NONE
            except Exception:
                pass
        if rot:
            tb.rotation = rot

        paras = self._normalise(content)
        first = True
        for para in paras:
            p = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            p.alignment = _ALIGN[align]
            if ls:
                p.line_spacing = ls
            p.space_before = Pt(space_before)
            p.space_after = Pt(space_after)
            for txt, opt in (self._run(i) for i in para):
                r = p.add_run()
                r.text = txt
                self._font(r, opt.get("size", size), opt.get("bold", bold),
                           opt.get("color", color), opt.get("font", font),
                           opt.get("italic", italic),
                           opt.get("underline", underline),
                           latin, opt.get("char_space", char_space))
        return tf

    @staticmethod
    def _normalise(content):
        """Accept the shapes people naturally write, unambiguously:

             "text"                                   -> 1 paragraph, 1 run
             ["p1", "p2"]                             -> 2 paragraphs
             ["a ", ("b", {"color": "#C00"}), " c"]   -> 1 paragraph, 3 runs
             [["a", ("b", {})], "p2"]                 -> 2 paragraphs, first mixed

        The rule: if a flat list contains a (text, overrides) tuple, it is one
        paragraph of runs — that is what someone means when they sprinkle styling
        into a sentence. Wrap a paragraph in its own list to mix styles AND break
        the line.
        """
        if isinstance(content, str):
            return [[content]]
        if not isinstance(content, list):
            return [[str(content)]]
        if any(isinstance(x, tuple) for x in content):
            return [content]
        out = []
        for x in content:
            if isinstance(x, str):
                out.append([x])
            elif isinstance(x, list):
                out.append(x)
            else:
                out.append([x])
        return out or [[""]]

    @staticmethod
    def _run(item):
        if isinstance(item, str):
            return item, {}
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], dict):
            return str(item[0]), item[1]
        raise ValueError(
            "text run must be str or (text, {overrides}); got %r — wrap a mixed "
            "paragraph in its own list: [[\"a\", (\"b\", {\"color\": \"#C00\"})]]" % (item,))

    def rtext(self, cx, cy, w, h, content, angle=0, **kw):
        """Text box centred on (cx, cy) in source px and rotated — the workhorse
        for labels that run along a slanted edge (35-45 degrees is everywhere in
        designed decks)."""
        kw.setdefault("align", "c")
        kw.setdefault("valign", "m")
        kw.setdefault("wrap", False)
        return self.text(cx - w / 2.0, cy - h / 2.0, w, h, content,
                         rot=angle, **kw)

    def _font(self, run, size, bold, color, font, italic=False, underline=False,
              latin=None, char_space=None):
        f = run.font
        f.size = size if hasattr(size, "pt") else Pt(size)
        f.bold, f.italic, f.underline = bool(bold), bool(italic), bool(underline)
        f.color.rgb = rgb(color)
        face = font or self.font
        f.name = face                                  # creates a:latin
        rPr = run._r.get_or_add_rPr()
        lat = rPr.find(qn("a:latin"))
        # East-Asian + complex-script faces. Without a:ea, Chinese silently falls
        # back to a different font and your carefully matched metrics break.
        for tag in ("a:ea", "a:cs"):
            el = rPr.find(qn(tag))
            if el is None:
                el = rPr.makeelement(qn(tag), {})
                if tag == "a:ea":
                    lat.addnext(el)
                else:
                    rPr.find(qn("a:ea")).addnext(el)
            el.set("typeface", face if tag == "a:ea" else (latin or self.latin))
        if latin:
            lat.set("typeface", latin)
        if char_space is not None:
            rPr.set("spc", str(int(char_space * 100)))

    # ------------------------------------------------------------ connectors
    def line(self, x1, y1, x2, y2, color="#000000", lw=1.0, dash=None,
             head=None, tail=None, arrow_size="med"):
        cx = self.slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                             self.ix(x1), self.iy(y1),
                                             self.ix(x2), self.iy(y2))
        st = cx._element.find(qn("p:style"))
        if st is not None:
            cx._element.remove(st)
        cx.line.color.rgb = rgb(color)
        cx.line.width = Pt(lw)
        d = _DASH.get(dash)
        if d is not None:
            cx.line.dash_style = d
        ln = cx._element.spPr.find(qn("a:ln"))
        if head:
            ln.append(ln.makeelement(qn("a:headEnd"),
                                     {"type": head, "w": arrow_size, "len": arrow_size}))
        if tail:
            ln.append(ln.makeelement(qn("a:tailEnd"),
                                     {"type": tail, "w": arrow_size, "len": arrow_size}))
        return cx

    # ------------------------------------------------------------ polygons
    def poly(self, pts, fill=None, line="#141414", lw=1.0, close=True,
             pic=None, alpha=None):
        """Arbitrary polygon from (x, y) in SOURCE PIXELS.

        pic=<image path> paints it with that image, stretched to the polygon's
        bounding box — exact for parallelograms with vertical sides, which is
        how almost every "3D slab" in a designed figure is drawn.
        """
        emu = [(int(round(self.ix(x))), int(round(self.iy(y)))) for x, y in pts]
        b = self.slide.shapes.build_freeform(emu[0][0], emu[0][1], scale=1.0)
        b.add_line_segments(emu[1:], close=close)
        sp = b.convert_to_shape()
        st = sp._element.find(qn("p:style"))
        if st is not None:
            sp._element.remove(st)
        if pic:
            self.fill_pic(sp, pic)
        else:
            self._fill(sp, fill, alpha)
        self._line(sp, line, lw)
        return sp

    def fill_pic(self, sp, image_path):
        """Shape filled with an image (stretched to the shape's bbox)."""
        spPr = sp._element.spPr
        for t in ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
                  "a:pattFill", "a:grpFill"):
            for el in spPr.findall(qn(t)):
                spPr.remove(el)
        _, rId = self.slide.part.get_or_add_image_part(image_path)
        bf = spPr.makeelement(qn("a:blipFill"), {"rotWithShape": "1"})
        blip = bf.makeelement(qn("a:blip"), {})
        blip.set(qn("r:embed"), rId)
        bf.append(blip)
        stretch = bf.makeelement(qn("a:stretch"), {})
        stretch.append(bf.makeelement(qn("a:fillRect"), {}))
        bf.append(stretch)
        ln = spPr.find(qn("a:ln"))
        ln.addprevious(bf) if ln is not None else spPr.append(bf)
        return sp

    def slab(self, x, y, w, h, sx, pic=None, back="#CBD5EC", fill="#DDE5F5",
             line="#141414", lw=1.5, thick=(-9, -7), back_edges_only=True):
        """A thin 3D plate: front face parallelogram + a thickness sliver.

        Front face corners: TL(x,y) TR(x+w, y-sx) BR(x+w, y-sx+h) BL(x, y+h).
        Only the back plate's TOP and LEFT edges are stroked — stroking its whole
        outline reads as a ghost second plate behind the face.
        """
        dx, dy = thick
        bp = [(x + dx, y + dy), (x + w + dx, y - sx + dy),
              (x + w + dx, y - sx + h + dy), (x + dx, y + h + dy)]
        self.poly(bp, fill=back, line=None if back_edges_only else line, lw=lw)
        if back_edges_only:
            self.line(bp[0][0], bp[0][1], bp[1][0], bp[1][1], color=line, lw=lw)
            self.line(bp[0][0], bp[0][1], bp[3][0], bp[3][1], color=line, lw=lw)
        fp = [(x, y), (x + w, y - sx), (x + w, y - sx + h), (x, y + h)]
        return self.poly(fp, fill=fill if pic is None else None, line=line,
                         lw=lw, pic=pic)

    def slab_bbox(self, x, y, w, h, sx):
        """Pixel bbox of a slab's front face — crop the texture with exactly this
        box and the picture fill lines up pixel-for-pixel."""
        return (x, y - sx, x + w, y + h)

    # ------------------------------------------------------------ images
    def src_path(self, name=None):
        n = name or self.src_name
        return n if os.path.isabs(n) else os.path.join(self.src_dir, n)

    def crop(self, name, x0, y0, x1, y1, scale=1.0, sharpen=0.0, pad=0,
             out_name=None):
        """Cut a px rect out of a reference image and save it as a PNG asset.

        Use this ONLY for content that is genuinely a picture (photo, someone
        else's figure, texture, logo). Everything else should be native shapes.
        """
        key = (name, x0, y0, x1, y1, scale, sharpen, pad)
        if key in self._cache:
            return self._cache[key]
        img = Image.open(self.src_path(name)).convert("RGB")
        x0, y0 = max(0, int(round(x0 - pad))), max(0, int(round(y0 - pad)))
        x1, y1 = min(img.width, int(round(x1 + pad))), min(img.height, int(round(y1 + pad)))
        c = img.crop((x0, y0, x1, y1))
        if scale and scale != 1.0:
            c = c.resize((int(round(c.width * scale)), int(round(c.height * scale))),
                         Image.LANCZOS)
        if sharpen:
            c = c.filter(ImageFilter.UnsharpMask(radius=1.4,
                                                 percent=int(sharpen * 100), threshold=2))
        base = os.path.splitext(os.path.basename(str(name)))[0]
        out_name = out_name or f"{base}_{x0}_{y0}_{x1}_{y1}_{scale}.png"
        path = os.path.join(self.assets_dir, out_name)
        c.save(path)
        self._cache[key] = path
        return path

    def pic(self, path, x, y, w=None, h=None, cover=True):
        """Place a picture in the px box. cover=True crops to fill (never stretch).

        Stretched photos are the single biggest tell that a deck was rebuilt by a
        machine — always cover.
        """
        kw = {}
        if w is not None:
            kw["width"] = self.iw(w)
        if h is not None:
            kw["height"] = self.ih(h)
        p = self.slide.shapes.add_picture(path, self.ix(x), self.iy(y), **kw)
        if cover and w is not None and h is not None:
            try:
                pw, ph = Image.open(path).size
                box_ar, img_ar = w / float(h), pw / float(ph)
                if abs(box_ar - img_ar) > 1e-3:
                    if img_ar > box_ar:
                        cut = (1.0 - box_ar / img_ar) / 2.0
                        p.crop_left = p.crop_right = cut
                    else:
                        cut = (1.0 - img_ar / box_ar) / 2.0
                        p.crop_top = p.crop_bottom = cut
            except Exception:
                pass
        return p

    def pic_fit(self, path, x, y, w, h, align="c", valign="m"):
        """Letterbox a picture inside the px box (keeps the whole image)."""
        pw, ph = Image.open(path).size
        bw, bh = w * self.sx, h * self.sy
        ap, ab = pw / float(ph), bw / bh
        if ap > ab:
            ow, oh = bw, bw / ap
        else:
            oh, ow = bh, bh * ap
        ox = x + (w - ow / self.sx) * {"l": 0.0, "c": .5, "r": 1.0}[align]
        oy = y + (h - oh / self.sy) * {"t": 0.0, "m": .5, "b": 1.0}[valign]
        return self.slide.shapes.add_picture(path, self.ix(ox), self.iy(oy),
                                             self.iw(ow / self.sx), self.ih(oh / self.sy))

    def bg(self, color="#FFFFFF"):
        return self.rect(0, 0, self.sw, self.sh, fill=color)


# ---------------------------------------------------------------- deck helpers
def new_deck(w=SLIDE_W, h=SLIDE_H):
    from pptx import Presentation
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(w), Inches(h)
    return prs


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def page(prs, src_name, src_px=None, src_dir="src", **kw):
    """Blank slide wired to a reference image (size read from the file)."""
    if src_px is None:
        src_px = Image.open(os.path.join(src_dir, src_name)).size
    return Canvas(blank(prs), src_px, src_name, src_dir=src_dir, **kw)
