"""render — export a .pptx to per-slide PNGs so you can LOOK at what you built.

This is the step people skip, and it is the step that decides quality. Reading
your own code tells you nothing; a real renderer tells you everything.

Engines, in order of preference:
  1. Microsoft PowerPoint (Windows, COM)  — matches what the user will see, and
     it is what you must use if the reference was a PowerPoint screenshot.
  2. LibreOffice (soffice --convert-to pdf + pdftoppm) — fallback.

    python render.py deck.pptx outdir [--only 1,2] [--width 1600]

PowerPoint is a single-instance COM server, so concurrent renders from several
agents must be serialised — hence the lock file. The app is never Quit(), so a
PowerPoint window the user already has open is left untouched.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

LOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".render.lock")


class Clock:
    """Cross-process lock; stale locks older than `stale` seconds are stolen."""

    def __init__(self, path, timeout=240.0, stale=300.0):
        self.path, self.timeout, self.stale = path, timeout, stale

    def __enter__(self):
        t0 = time.time()
        while True:
            try:
                if os.path.exists(self.path) and time.time() - os.path.getmtime(self.path) > self.stale:
                    try:
                        os.remove(self.path)
                    except OSError:
                        pass
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                if time.time() - t0 > self.timeout:
                    raise TimeoutError(f"render lock busy: {self.path}")
                time.sleep(.15)

    def __exit__(self, *exc):
        for _ in range(20):
            try:
                os.remove(self.path)
                break
            except FileNotFoundError:
                break
            except OSError:
                time.sleep(.1)
        return False


def render_powerpoint(pptx, outdir, only=None, width=1600):
    import pythoncom
    import win32com.client as win32

    pptx, outdir = os.path.abspath(pptx), os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    made = []
    pythoncom.CoInitialize()
    try:
        app = win32.Dispatch("PowerPoint.Application")
        try:
            app.Visible = True
        except Exception:
            pass
        pres = app.Presentations.Open(pptx, ReadOnly=True, Untitled=False, WithWindow=False)
        try:
            n = pres.Slides.Count
            w_in, h_in = pres.PageSetup.SlideWidth, pres.PageSetup.SlideHeight
            px_w = int(width)
            px_h = int(round(width * h_in / w_in))
            for i in (only or range(1, n + 1)):
                if not (1 <= i <= n):
                    continue
                out = os.path.join(outdir, f"slide-{i:02d}.png")
                pres.Slides(i).Export(out, "PNG", px_w, px_h)
                made.append(out)
        finally:
            pres.Close()
    finally:
        pythoncom.CoUninitialize()
    return made


def render_libreoffice(pptx, outdir, only=None, width=1600):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise SystemExit("no PowerPoint COM and no LibreOffice — cannot render")
    outdir = os.path.abspath(outdir)
    os.makedirs(outdir, exist_ok=True)
    subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                    "--outdir", outdir, os.path.abspath(pptx)], check=True)
    pdf = os.path.join(outdir, os.path.splitext(os.path.basename(pptx))[0] + ".pdf")
    made = []
    for i in range(1, 400):
        if only and i not in only:
            continue
        base = os.path.join(outdir, f"slide-{i:02d}")
        r = subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(i), "-l", str(i),
                            pdf, base], capture_output=True)
        if r.returncode != 0:
            break
        for suffix in ("-1.png", f"-{i:02d}.png", f"-{i}.png"):
            p = base + suffix
            if os.path.exists(p):
                os.replace(p, os.path.join(outdir, f"slide-{i:02d}.png"))
                made.append(os.path.join(outdir, f"slide-{i:02d}.png"))
                break
        else:
            break
    return made


def render(pptx, outdir, only=None, width=1600):
    try:
        import win32com.client  # noqa: F401
        return render_powerpoint(pptx, outdir, only, width)
    except Exception as e:
        print(f"[render] PowerPoint unavailable ({e}); falling back to LibreOffice",
              file=sys.stderr)
        return render_libreoffice(pptx, outdir, only, width)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("outdir")
    ap.add_argument("--only", default="")
    ap.add_argument("--width", type=int, default=1600)
    a = ap.parse_args()
    only = [int(x) for x in a.only.split(",") if x.strip()] or None
    with Clock(LOCK):
        made = render(a.pptx, a.outdir, only, a.width)
    for m in made:
        print("wrote", m, os.path.getsize(m), "bytes")
    if not made:
        print("!! nothing rendered", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
