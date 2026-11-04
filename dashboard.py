"""
One self-contained page to browse the image bank: every company and topic, each shot with its status,
its future file name, a link to its search on Wikimedia Commons and its AI prompt.

    python dashboard.py [output.html]     (default: bank/dashboard.html)

The previews (<ID>/<shot>.thumb.jpg) are referenced by relative path: publish them beside the page
(thumb_files() lists them; at most 255 files per publish, so two publishes for the whole bank).
"""
import json, sys
from pathlib import Path

import image_bank as B

TEMPLATE = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(encoding="utf-8")


def data(cat=None, bank=B.BANK):
    cat = cat or B.load_catalog()
    m = B.load_manifest(bank)
    out = []
    for s in cat["subjects"]:
        shots = []
        for sh in s["shots"]:
            x = m.get(s["id"], {}).get("shots", {}).get(sh["id"], {})
            shots.append({"id": sh["id"], "q": sh["q"], "scene": sh["scene"], "person": bool(sh.get("person")),
                          "historic": bool(sh.get("historic")), "status": x.get("status", "pending"),
                          "credit": x.get("credit"), "page": x.get("page"),
                          "thumb": f"{s['id']}/{sh['id']}.thumb.jpg" if x.get("status") == "ok" else None,
                          "prompt": None if sh.get("person") else f"{sh['scene']}. {cat['style']}"})
        out.append({"id": s["id"], "kind": s["kind"], "name": s["name"], "tickers": s.get("tickers", []),
                    "aliases": s.get("aliases", []), "shots": shots})
    return out


def thumb_files(bank=B.BANK):
    """{published path: local file} of every photo's preview, to publish beside the page (Artifact `files`)."""
    m = B.load_manifest(bank)
    return {f"{sid}/{shid}.thumb.jpg": str(Path(bank) / sid / f"{shid}.thumb.jpg")
            for sid, e in m.items() for shid, x in e.get("shots", {}).items()
            if x.get("status") == "ok" and (Path(bank) / sid / f"{shid}.thumb.jpg").exists()}


def write(path):
    blob = json.dumps(data(), ensure_ascii=False).replace("</", "<\\/")
    Path(path).write_text(TEMPLATE.replace("__DATA__", blob), encoding="utf-8")
    return path


if __name__ == "__main__":
    print("written", write(sys.argv[1] if len(sys.argv) > 1 else B.BANK / "dashboard.html"))
