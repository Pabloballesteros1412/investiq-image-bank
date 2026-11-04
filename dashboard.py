"""
One self-contained page to browse the image bank: every company, topic and sector with its photos
(previews linked from Wikimedia Commons), what each one shows, its credit and its addresses; subjects not
built yet show their planned searches and AI prompts.

    python dashboard.py                 (docs/index.html: the gallery GitHub Pages serves)
    python dashboard.py out.html --artifact   (the page for a claude.ai artifact, without its own <html> wrapper)

In a claude.ai artifact the previews do not load (artifacts only show images published with the page):
there the page still lists every photo with its links; the gallery with images is the GitHub Pages one.
"""
import json, sys
from pathlib import Path

import image_bank as B

HERE = Path(__file__).resolve().parent
TEMPLATE = (HERE / "dashboard_template.html").read_text(encoding="utf-8")


def data(cat=None, bank=B.BANK):
    cat = cat or B.load_catalog()
    m, uni, rv = B.load_manifest(bank), B.load_universe(bank), B.load_review(bank)
    subjects = B.subjects_of(cat, uni) if uni else [s for s in cat["subjects"]]
    out = []
    for s in subjects:
        e = m.get(s["id"], {})
        photos = [{"shows": p["shows"], "url": p["url"], "preview": p["preview"], "credit": p["credit"], "page": p["page"],
                   "person": bool(p.get("person")), "generic": False} for p in B.published_photos(e, rv)]
        planned = [] if photos else [{"scene": sh["scene"], "q": sh["q"], "person": bool(sh.get("person")),
                                      "prompt": None if sh.get("person") else f"{sh['scene']}. {cat['style']}"} for sh in s.get("shots", [])]
        out.append({"id": s["id"], "kind": s["kind"], "name": s["name"], "tickers": s.get("tickers", []),
                    "aliases": s.get("aliases", []), "sector": s.get("sector") or (B.SECTORS.get(s.get("gics")) if s["kind"] == "sector" else None),
                    "built": bool(e.get("checked")), "photos": photos, "planned": planned})
    return {"subjects": out, "universe": bool(uni), "target": B.TARGET}


def write(path, artifact=False):
    """The page; a full HTML document unless it is for a claude.ai artifact (which wraps it in its own)."""
    blob = json.dumps(data(), ensure_ascii=False).replace("</", "<\\/")
    page = TEMPLATE.replace("__DATA__", blob)
    if not artifact:
        page = ('<!doctype html>\n<html lang="es"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>\n'
                + page + "\n</body></html>\n")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(page, encoding="utf-8")
    return path


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--artifact"]
    print("written", write(a[0] if a else HERE / "docs" / "index.html", artifact="--artifact" in sys.argv))
