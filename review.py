"""
Review of the bank's Wikimedia Commons photos by eye: only the best reach the carousel chat.

Commons photos are documentary and very uneven (an amateur snapshot of a parking garage sits next to a fine
photo of a headquarters), so each one gets a grade in bank/review.json, given by a person or by Claude looking
at contact sheets:

    3  best: would look good full-bleed on a 4:5 slide with a headline over it, and clearly shows the
       company's own place, product, vehicle or person (or the topic)
    2  usable but plain: right subject, dull photo (an ordinary facade, grey sky, clutter, awkward crop)
    1  reject: wrong or unclear subject, poor photo, or anything that does not belong in an investing carousel

The index publishes a Commons photo only when its grade reaches "min_grade" (3), and the build never picks a
photo graded below it again. Photos from Unsplash and Pexels need no grade. Commands (Pillow needed):

    python review.py sheets [OUT_DIR]   contact sheets of the Commons photos without a grade (default review/),
                                        30 numbered 4:5 tiles each, and OUT_DIR/sheets.json (tile -> photo)
    python review.py sheets --stock     the same for Unsplash and Pexels photos without a grade: they are
                                        published unless graded below min_grade, so this is a check, not a gate
    python review.py grade GRADES.json  merge grades: {"sheet-001": {"3": [tile, ...], "2": [...]}, ...};
                                        tiles not listed get 1. Then: python image_bank.py index
    python review.py stats              how many photos have each grade
"""
import hashlib, io, json, os, sys, textwrap, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import image_bank as B

PREVIEWS = B.HERE / ".cache" / "previews"
COLS, ROWS = 6, 5
TW, TH, LABEL = 250, 312, 40


def commons_photos(m, stock=False):
    """[(subject id, photo)] of the Commons photos in the manifest (with stock: the Unsplash and Pexels ones)."""
    return [(sid, p) for sid, e in m.items() for p in e.get("photos", []) if (B.provider_of(p) == "commons") != stock]


def preview(p):
    """The photo's 500 px preview as a PIL image (downloaded once into .cache/previews)."""
    from PIL import Image
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    f = PREVIEWS / (hashlib.sha1(p["file"].encode()).hexdigest() + ".jpg")
    if not f.exists() or not f.stat().st_size:
        for attempt in range(6):
            try:
                # the Wikimedia token goes to Wikimedia only
                h = B.headers() if "wikimedia.org" in p["preview"] else {"User-Agent": B.UA}
                with urllib.request.urlopen(urllib.request.Request(p["preview"], headers=h), timeout=60) as r:
                    f.write_bytes(r.read())
                break
            except urllib.error.HTTPError as e:
                if e.code not in (429, 500, 502, 503, 504) or attempt == 5:
                    raise
                time.sleep(B.wait_for(e, attempt))
    return Image.open(io.BytesIO(f.read_bytes())).convert("RGB")


def tile(im, focus):
    """The part of the photo a 4:5 slide shows, centred on the focus point."""
    from PIL import Image
    w, h = im.size
    cw, ch = (int(h * TW / TH), h) if w / h > TW / TH else (w, int(w * TH / TW))
    x = min(max(0, int(focus[0] * w - cw / 2)), w - cw)
    y = min(max(0, int(focus[1] * h - ch / 2)), h - ch)
    return im.crop((x, y, x + cw, y + ch)).resize((TW, TH), Image.LANCZOS)


def font(size, bold=False):
    from PIL import ImageFont
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)
    except OSError:
        return ImageFont.load_default()


def sheets(out="review", bank=B.BANK, stock=False):
    """Contact sheets of the Commons (or stock) photos without a grade; returns the number of sheets."""
    from PIL import Image, ImageDraw
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    m, rv = B.load_manifest(bank), B.load_review(bank)
    todo = [(sid, p) for sid, p in commons_photos(m, stock) if p["file"] not in rv["grades"]]
    per = COLS * ROWS
    index, f_num, f_bold, f_text = {}, font(22, True), font(13, True), font(12)
    for n in range(0, len(todo), per):
        batch = todo[n:n + per]
        with ThreadPoolExecutor(3) as ex:
            ims = list(ex.map(lambda sp: preview(sp[1]), batch))
        sheet = Image.new("RGB", (COLS * (TW + 6) + 6, ROWS * (TH + LABEL + 6) + 6), "white")
        d = ImageDraw.Draw(sheet)
        name = f"sheet-{n // per + 1:03d}"
        index[name] = {}
        for i, ((sid, p), im) in enumerate(zip(batch, ims), 1):
            x, y = 6 + (i - 1) % COLS * (TW + 6), 6 + (i - 1) // COLS * (TH + LABEL + 6)
            sheet.paste(tile(im, p.get("focus", (0.5, 0.5))), (x, y))
            d.rectangle((x, y, x + 34, y + 28), fill="black")
            d.text((x + 4, y + 2), str(i), font=f_num, fill="white")
            d.text((x, y + TH + 3), textwrap.shorten(m[sid]["name"], 32, placeholder="…"), font=f_bold, fill=(10, 10, 10))
            d.text((x, y + TH + 21), textwrap.shorten(p["shows"], 38, placeholder="…"), font=f_text, fill=(80, 80, 80))
            index[name][str(i)] = {"subject": sid, "file": p["file"]}
        sheet.save(out / f"{name}.jpg", quality=85)
    (out / "sheets.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(index)


def grade(grades_file, sheets_dir="review", bank=B.BANK):
    """Merge grades given per sheet tile into bank/review.json; returns {grade: count} of what was merged."""
    index = json.loads((Path(sheets_dir) / "sheets.json").read_text(encoding="utf-8"))
    given = json.loads(Path(grades_file).read_text(encoding="utf-8"))
    rv = B.load_review(bank)
    count = {1: 0, 2: 0, 3: 0}
    for name, tiles in index.items():
        if name not in given:
            continue  # a sheet nobody graded stays without grades
        g = {str(t): int(k) for k, ts in given[name].items() for t in ts}
        for t, ref in tiles.items():
            rv["grades"][ref["file"]] = g.get(t, 1)
            count[g.get(t, 1)] += 1
    rv["updated"] = date.today().isoformat()
    B.save_review(rv, bank)
    return count


def stats(bank=B.BANK):
    m, rv = B.load_manifest(bank), B.load_review(bank)
    c = {"3": 0, "2": 0, "1": 0, "none": 0}
    for _, p in commons_photos(m):
        g = rv["grades"].get(p["file"])
        c[str(g) if g else "none"] += 1
    return c


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["sheets"]:
        rest = [x for x in a[1:] if x != "--stock"]
        print(sheets(rest[0] if rest else "review", stock="--stock" in a), "sheets")
    elif a[:1] == ["grade"] and len(a) > 1:
        print(grade(a[1], a[2] if len(a) > 2 else "review"))
    elif a[:1] == ["stats"]:
        print(stats())
    else:
        sys.exit(__doc__)
