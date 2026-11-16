"""List verified page templates by use and style from a local workbench."""
import argparse
import json
from pathlib import Path


def normalize_role(value):
    return value.strip().removesuffix("页")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path, help="library folder containing catalog.json")
    parser.add_argument("--role", help="page role, or one of its aliases")
    parser.add_argument("--style", action="append", default=[], help="required tag; repeat for AND")
    args = parser.parse_args()

    catalog = json.loads((args.library / "catalog.json").read_text(encoding="utf-8"))
    matches = []
    for deck in catalog["decks"]:
        for page in deck["pages"]:
            roles = [page["role"], *page.get("aliases", [])]
            style = sorted(set([*deck.get("tags", []), *page.get("tags", [])]))
            if page.get("status") != "verified":
                continue
            if args.role and normalize_role(args.role) not in map(normalize_role, roles):
                continue
            if not set(args.style).issubset(style):
                continue
            if not all((args.library / part).is_file() for part in
                       (deck["pptx"], page["preview"], page["spec"])):
                continue
            matches.append({
                "id": page["id"], "role": page["role"], "aliases": page.get("aliases", []),
                "tags": style, "ratio": deck["ratio"], "deck": deck["id"],
                "pptx": deck["pptx"], "slide": page["slide"], "preview": page["preview"],
                "spec": page["spec"], "logic": page["logic"],
            })
    print(json.dumps(matches, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
