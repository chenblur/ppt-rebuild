"""Crop a vertical reference image using page boxes measured by the operator."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps


def box(value):
    try:
        x, y, w, h = map(int, value.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected four integers: x,y,width,height")
    return x, y, w, h


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    parser.add_argument("--box", action="append", required=True, type=box,
                        help="x,y,width,height in EXIF-corrected image pixels, top to bottom")
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"output already exists: {args.out}")

    with Image.open(args.image) as opened:
        img = ImageOps.exif_transpose(opened)
        pages = []
        previous_end = 0
        for i, (x, y, w, h) in enumerate(args.box, 1):
            if min(x, y) < 0 or min(w, h) <= 0 or x + w > img.width or y + h > img.height:
                parser.error(f"box {i} is empty or outside image {img.size}: {(x,y,w,h)}")
            if y < previous_end:
                parser.error(f"box {i} overlaps or precedes the previous page")
            previous_end = y + h
            pages.append({"file": f"p{i:03}.png", "box_xywh_px": [x, y, w, h]})
        args.out.mkdir(parents=True, exist_ok=False)
        for page in pages:
            x, y, w, h = page["box_xywh_px"]
            img.crop((x, y, x + w, y + h)).save(args.out / page["file"])
        manifest = {"source": args.image.name, "reference_size_px": list(img.size), "pages": pages}
        (args.out / "SPLIT-MAP.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Split {len(pages)} pages into {args.out}")


if __name__ == "__main__":
    main()
