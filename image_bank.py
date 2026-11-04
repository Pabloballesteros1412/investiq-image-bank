"""
Image bank for InvestIQ's carousels (made by a Claude chat on claude.ai): 5-6 photos for each large company and each mainstream market topic
(catalog.json), taken from Wikimedia Commons under free licences or in the public domain, with the
author and licence of every photo recorded for the credits, plus ready-made crops for 4:5 and 1:1 slides, and
bank/index.json: what the carousel chat reads to find a photo and its public address.

    python image_bank.py build                    (search and download every shot not in the bank yet)
    python image_bank.py build --only AAPL,gold   (search again some subjects, by id, ticker or alias)
    python image_bank.py build --redo             (search again every shot not fixed by hand)
    python image_bank.py build --no-sa            (no CC BY-SA photos: only CC0, public domain and CC BY)
    python image_bank.py build --formats 4x5,1x1,16x9,9x16   (crops to make; default 4x5,1x1)
    python image_bank.py sheet                    (bank/review.html: every photo at a glance, with credits)
    python image_bank.py credits                  (bank/CREDITS.md and bank/credits.csv)
    python image_bank.py prompts [--all]          (bank/prompts.jsonl: AI image prompts for shots without a photo)
    python image_bank.py list AAPL [--format 1x1]  (the photos of a company or topic, with their credit line)
    python image_bank.py index [--base-url URL]   (bank/index.json for the carousel chat; default: the repo's raw GitHub address)
    python image_bank.py check                    (validate catalog.json)

Needs Python 3.9+ and Pillow, and network access to commons.wikimedia.org and upload.wikimedia.org.

How a photo is chosen: Commons full-text search for the shot's query (then its fallback queries), keeping
only bitmap photos with a free licence (CC0, public domain, CC BY, CC BY-SA), at least 1600 px on the long
side and 1000 px on the short side, whose file name is not a logo, map, chart, diagram or screenshot, and
not already used by another shot. Ranking: search relevance, Commons "featured" / "quality" / "valued"
pictures first, proportions that crop well to 4:5 and 1:1 (no panoramas), recent photos (unless the shot is
historic), freer licences.
The best one is downloaded (long side 2560 px), cropped around the shot's focus point, and the next three
are kept in the manifest as alternates for the review.

Corrections by hand, in bank/manifest.json, on a shot: "exclude": ["File:..."] (photos never to use),
"prefer": "File:..." (the photo to use), "focus": [x, y] (crop centre, 0-1), listed in "manual":
e.g. "manual": ["exclude"]; builds keep those fields. "manual": true freezes the whole shot.
"""
import csv, html, io, json, re, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "catalog.json"
BANK = HERE / "bank"
API = "https://commons.wikimedia.org/w/api.php"
UA = "InvestIQ-image-bank/1.0 (https://getinvestiq.com; carousel image bank)"
BASE_URL = "https://raw.githubusercontent.com/Pabloballesteros1412/investiq-image-bank/main/bank/"  # public address of bank/

MIN_LONG, MIN_SHORT = 1600, 1000      # smallest acceptable photo (px)
MASTER_LONG = 2560                    # long side of the stored photo
FETCH_W = 3840                        # Commons thumbnail width asked for photos wider than this (a standard size)
# 4x5 = Instagram portrait post and LinkedIn document (1200x1500); 1x1 = square post; the others for video
FORMATS = {"4x5": (1200, 1500), "1x1": (1200, 1200), "16x9": (1920, 1080), "9x16": (1080, 1920), "3x4": (1080, 1440)}
DEFAULT_FORMATS = ("4x5", "1x1")
SOFT = 1.25                           # a crop enlarged more than this is flagged as soft
PERSON_FOCUS = (0.5, 0.33)            # faces sit in the upper third
MIMES = {"image/jpeg", "image/png", "image/webp", "image/tiff"}
BAD_WORDS = ["logo", "logotype", "wordmark", "icon", "map", "diagram", "chart", "graph", "plot", "screenshot",
             "infographic", "coat of arms", "flag of", "seal of", "emblem", "drawing", "illustration", "render",
             "rendering", "sketch", "plan", "blueprint", "label", "poster", "banner", "stamp", "signature"]
EXTMETA = "|".join(["LicenseShortName", "License", "LicenseUrl", "Artist", "Credit", "AttributionRequired",
                    "DateTimeOriginal", "Categories", "Restrictions", "ImageDescription", "UsageTerms"])


# ---------- catalog ----------

def load_catalog(path=None):
    cat = json.loads(Path(path or CATALOG).read_text(encoding="utf-8"))
    problems = check_catalog(cat)
    if problems:
        raise ValueError("catalog.json: " + "; ".join(problems))
    return cat


def check_catalog(cat):
    """List of problems in the catalog (empty when it is valid)."""
    out, ids, keys = [], set(), {}
    for s in cat.get("subjects", []):
        sid = s.get("id")
        if not sid or sid in ids:
            out.append(f"missing or repeated subject id {sid!r}")
        ids.add(sid)
        if s.get("kind") not in ("company", "topic"):
            out.append(f"{sid}: kind must be company or topic")
        if not s.get("name"):
            out.append(f"{sid}: no name")
        for k in [sid, *s.get("tickers", []), *s.get("aliases", [])]:
            k = str(k).lower()
            if k in keys and keys[k] != sid:
                out.append(f"{sid}: '{k}' already names {keys[k]}")
            keys[k] = sid
        shots = s.get("shots", [])
        if not 5 <= len(shots) <= 6:
            out.append(f"{sid}: {len(shots)} shots (5 or 6 expected)")
        seen = set()
        for sh in shots:
            if not sh.get("id") or sh["id"] in seen:
                out.append(f"{sid}: missing or repeated shot id {sh.get('id')!r}")
            seen.add(sh.get("id"))
            if not sh.get("q") or not sh.get("scene"):
                out.append(f"{sid}/{sh.get('id')}: needs q and scene")
            if sh.get("orient", "landscape") not in ("landscape", "portrait", "any"):
                out.append(f"{sid}/{sh.get('id')}: orient must be landscape, portrait or any")
            f = sh.get("focus")
            if f is not None and not (len(f) == 2 and all(0 <= v <= 1 for v in f)):
                out.append(f"{sid}/{sh.get('id')}: focus must be [x, y] between 0 and 1")
    return out


def find_subject(cat, key):
    """A subject by id, ticker or alias (any case), or None."""
    k = key.lower()
    for s in cat["subjects"]:
        if k in [str(x).lower() for x in [s["id"], *s.get("tickers", []), *s.get("aliases", [])]]:
            return s
    return None


# ---------- Commons ----------

def get_json(params, url=API):
    full = url + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(full, headers={"User-Agent": UA}), timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(min(60, 5 * 2 ** attempt))
    raise RuntimeError(f"Commons did not answer: {params}")


def fetch(url):
    """Bytes of an image on upload.wikimedia.org, waiting when rate limited."""
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(min(60, 5 * 2 ** attempt))
    raise RuntimeError(f"could not download {url}")


IMAGEINFO = {"prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": FETCH_W, "iiextmetadatafilter": EXTMETA}


def search(q, limit=30):
    """Candidates for a Commons full-text search in the File namespace, most relevant first."""
    d = get_json({"action": "query", "generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6,
                  "gsrlimit": limit, **IMAGEINFO})
    pages = sorted(d.get("query", {}).get("pages", []), key=lambda p: p.get("index", 1e9))
    return [candidate(p) for p in pages if p.get("imageinfo")]


def info(title):
    """The candidate for one Commons file ("File:..."), or None."""
    d = get_json({"action": "query", "titles": title, **IMAGEINFO})
    pages = [p for p in d.get("query", {}).get("pages", []) if p.get("imageinfo")]
    return candidate(pages[0]) if pages else None


def plain(s):
    """HTML from Commons metadata -> plain text."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def candidate(page):
    ii = page["imageinfo"][0]
    md = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (ii.get("extmetadata") or {}).items()}
    w, h = ii.get("width", 0), ii.get("height", 0)
    y = re.search(r"\b(1[89]\d\d|20\d\d)\b", plain(str(md.get("DateTimeOriginal", ""))))
    return {"file": page["title"], "w": w, "h": h, "mime": ii.get("mime", ""),
            "url": ii.get("thumburl") if w > FETCH_W and ii.get("thumburl") else ii.get("url"),
            "page": ii.get("descriptionurl", "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_"))),
            "licence": plain(md.get("LicenseShortName")), "licence_code": (md.get("License") or "").lower(),
            "licence_url": md.get("LicenseUrl") or "", "author": plain(md.get("Artist")) or plain(md.get("Credit")),
            "year": int(y.group(1)) if y else None,
            "categories": [c for c in (md.get("Categories") or "").split("|") if c],
            "restrictions": [r for r in (md.get("Restrictions") or "").split("|") if r],
            "description": plain(md.get("ImageDescription"))[:300]}


# ---------- choosing ----------

def licence_kind(c):
    """'cc0', 'pd', 'by' or 'by-sa'; None for licences not used (GFDL only, FAL, unknown, non-free)."""
    code, short = c.get("licence_code", ""), c.get("licence", "").lower()
    if code.startswith("cc0") or "cc0" in short:
        return "cc0"
    if code.startswith("pd") or "public domain" in short:
        return "pd"
    if code.startswith("cc-by-sa") or "cc by-sa" in short:
        return "by-sa"
    if code.startswith("cc-by") or re.match(r"cc by \d", short) or short.startswith("attribution"):
        return "by"
    return None


def bad_name(title, allow=()):
    name = re.sub(r"\.\w+$", "", title.split(":", 1)[-1]).lower()
    return any(re.search(r"\b" + re.escape(w) + r"s?\b", name) for w in BAD_WORDS if w not in allow)


def score(c, rank, shot, used=(), no_sa=False, exclude=()):
    """Ranking score of a candidate for a shot, or None when it cannot be used."""
    if c["file"] in used or c["file"] in exclude or c["mime"] not in MIMES:
        return None
    kind = licence_kind(c)
    if kind is None or (no_sa and kind == "by-sa"):
        return None
    w, h = c["w"], c["h"]
    if max(w, h) < MIN_LONG or min(w, h) < MIN_SHORT or bad_name(c["file"], shot.get("allow", ())):
        return None
    s = 100 - 2 * rank
    cats = " ".join(c["categories"]).lower()
    s += 25 if "featured pictures" in cats else 15 if "quality images" in cats else 8 if "valued images" in cats else 0
    ratio = w / h
    orient = shot.get("orient", "any")
    if orient == "landscape":
        s += 10 if ratio >= 1.3 else 0 if ratio >= 1 else -25
    elif orient == "portrait":
        s += 10 if ratio <= 0.85 else -10
    else:  # 4:5 and 1:1 slides: anything from portrait to 3:2 crops well, panoramas lose too much
        s += 10 if 0.6 <= ratio <= 1.6 else 0 if ratio <= 2.0 else -20
    if max(w, h) >= 3000:
        s += 5
    y = c.get("year")
    if y and not shot.get("historic"):
        s += 8 if y >= 2018 else 3 if y >= 2008 else -30 if y < 1990 else 0
    if kind == "by-sa":
        s -= 4
    return s


def choose(shot, search_fn, used=(), no_sa=False, exclude=()):
    """Acceptable candidates for a shot, best first: [(score, candidate, query)]. The fallback queries are
    tried only while fewer than three photos qualify, and their results rank lower."""
    seen, out = set(), []
    for i, q in enumerate([shot["q"], *shot.get("alt", [])]):
        for rank, c in enumerate(search_fn(q)):
            if c["file"] in seen:
                continue
            seen.add(c["file"])
            s = score(c, rank, shot, used, no_sa, exclude)
            if s is not None:
                out.append((s - 8 * i, c, q))
        if len(out) >= 3:
            break
    return sorted(out, key=lambda x: -x[0])


# ---------- images ----------

def crop(im, size, focus=(0.5, 0.5)):
    """Crop to the aspect of size around focus, then resize to size. (image, enlargement factor)."""
    W, H = im.size
    tw, th = size
    if W / H > tw / th:
        ch, cw = H, round(H * tw / th)
    else:
        cw, ch = W, round(W * th / tw)
    left = min(max(round(focus[0] * W - cw / 2), 0), W - cw)
    top = min(max(round(focus[1] * H - ch / 2), 0), H - ch)
    return im.crop((left, top, left + cw, top + ch)).resize((tw, th), Image.LANCZOS), tw / cw


def save_photo(data, folder, shot_id, formats, focus):
    """Store the photo (master, preview, crops); returns (sizes, flags)."""
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    original = list(im.size)
    if max(im.size) > MASTER_LONG:
        im.thumbnail((MASTER_LONG, MASTER_LONG), Image.LANCZOS)
    folder.mkdir(parents=True, exist_ok=True)
    im.save(folder / f"{shot_id}.jpg", "JPEG", quality=90, optimize=True, progressive=True)
    prev = im.copy()
    prev.thumbnail((640, 640), Image.LANCZOS)
    prev.save(folder / f"{shot_id}.thumb.jpg", "JPEG", quality=80)
    flags = []
    for f in formats:
        out, k = crop(im, FORMATS[f], focus)
        out.save(folder / f"{shot_id}.{f}.jpg", "JPEG", quality=90, optimize=True, progressive=True)
        if k > SOFT:
            flags.append(f"{f} crop enlarged {k:.1f}x (may look soft)")
    return {"downloaded": original, "stored": list(im.size)}, flags


def credit_line(c):
    author = c.get("author") or "Unknown author"
    lic = "public domain" if licence_kind(c) == "pd" else c.get("licence") or "free licence"
    return f"{author}, {lic}, via Wikimedia Commons"


# ---------- manifest ----------

def load_manifest(bank=BANK):
    p = Path(bank) / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_manifest(m, cat, bank=BANK):
    order = {s["id"]: i for i, s in enumerate(cat["subjects"])}
    m = dict(sorted(m.items(), key=lambda kv: order.get(kv[0], 1e9)))
    (Path(bank) / "manifest.json").write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")


def build(catalog=None, bank=BANK, only=None, redo=False, no_sa=False, formats=DEFAULT_FORMATS,
          search_fn=search, info_fn=info, fetch_fn=fetch, pause=0.3, log=print):
    cat = catalog if isinstance(catalog, dict) else load_catalog(catalog)
    bank = Path(bank)
    bank.mkdir(parents=True, exist_ok=True)
    for f in formats:
        if f not in FORMATS:
            raise ValueError(f"unknown format {f}: {', '.join(FORMATS)}")
    m = load_manifest(bank)
    keys = {k.strip().lower() for k in only.split(",")} if only else None
    subjects = [s for s in cat["subjects"] if keys is None or keys & {str(x).lower() for x in [s["id"], *s.get("tickers", []), *s.get("aliases", [])]}]
    if keys and not subjects:
        raise ValueError(f"no subject matches {only}")
    used = {sh["file"] for e in m.values() for sh in e.get("shots", {}).values() if sh.get("status") == "ok" and sh.get("file")}
    total = sum(len(s["shots"]) for s in subjects)
    n = 0
    for s in subjects:
        ms = m.setdefault(s["id"], {})
        ms.update(name=s["name"], kind=s["kind"], tickers=s.get("tickers", []), aliases=s.get("aliases", []))
        shots = ms.setdefault("shots", {})
        for sh in s["shots"]:
            n += 1
            old = shots.get(sh["id"], {})
            if old.get("manual") is True:
                continue
            here = old.get("status") == "ok" and (bank / s["id"] / f"{sh['id']}.jpg").exists()
            if here and not (redo or keys) and all((bank / s["id"] / f"{sh['id']}.{f}.jpg").exists() for f in formats):
                continue
            man = old.get("manual") or []
            fixed = {f: old[f] for f in man if f in old}
            if old.get("file"):
                used.discard(old["file"])
            focus = tuple(fixed.get("focus") or sh.get("focus") or (PERSON_FOCUS if sh.get("person") else (0.5, 0.5)))
            entry = {"scene": sh["scene"], "query": sh["q"], "checked": date.today().isoformat()}
            if sh.get("person"):
                entry["person"] = True
            try:
                if fixed.get("prefer"):
                    c = info_fn(fixed["prefer"])
                    ok = c is not None and licence_kind(c) is not None and not (no_sa and licence_kind(c) == "by-sa")
                    ranked = [(0, c, "prefer")] if ok else []
                    if not ok:
                        entry["note"] = f"preferred file not usable (missing or not a free licence): {fixed['prefer']}"
                else:
                    ranked = choose(sh, search_fn, used, no_sa, set(fixed.get("exclude", [])))
                if not ranked:
                    entry.update(status="missing", note=entry.get("note") or "no free photo found on Commons: see prompts.jsonl")
                else:
                    _, c, q = ranked[0]
                    sizes, flags = save_photo(fetch_fn(c["url"]), bank / s["id"], sh["id"], formats, focus)
                    used.add(c["file"])
                    entry.update(status="ok", file=c["file"], page=c["page"], author=c["author"], licence=c["licence"],
                                 licence_kind=licence_kind(c), licence_url=c["licence_url"], credit=credit_line(c),
                                 year=c["year"], size=sizes["downloaded"], path=f"{s['id']}/{sh['id']}.jpg",
                                 crops={f: f"{s['id']}/{sh['id']}.{f}.jpg" for f in formats}, focus=list(focus), found_with=q)
                    if c["restrictions"]:
                        flags.append("restrictions: " + ", ".join(c["restrictions"]))
                    if flags:
                        entry["flags"] = flags
                    entry["alternates"] = [{"file": a["file"], "page": a["page"], "licence": a["licence"]} for _, a, _ in ranked[1:4]]
            except Exception as e:  # one failing shot must not stop the build; the next run retries it
                entry.update(status="error", note=f"{type(e).__name__}: {e}"[:300])
            if entry["status"] == "error" and here:  # Commons not answering must not cost a good photo
                entry = {**old, "note": "kept the previous photo: " + entry["note"]}
                used.add(old["file"])
            elif entry["status"] != "ok":
                for p in (bank / s["id"]).glob(f"{sh['id']}.*"):
                    p.unlink()
            if man:
                entry.update(fixed, manual=man)
            shots[sh["id"]] = entry
            log(f"  {n}/{total} {s['id']}/{sh['id']:16s} {entry['status']:8s} {entry.get('file', entry.get('note', ''))}")
            if n % 10 == 0:
                save_manifest(m, cat, bank)
            time.sleep(pause)
    save_manifest(m, cat, bank)
    return m


# ---------- outputs ----------

def credits(bank=BANK):
    """bank/CREDITS.md and bank/credits.csv: author, licence and source of every photo."""
    bank = Path(bank)
    m = load_manifest(bank)
    rows = [(sid, shid, sh) for sid, e in m.items() for shid, sh in e.get("shots", {}).items() if sh.get("status") == "ok"]
    md = ["# Image credits", "", "Photos from Wikimedia Commons. Credit them as shown when the licence asks for attribution "
          "(CC BY, CC BY-SA); public-domain and CC0 photos need none, but crediting is good practice.", ""]
    for sid, e in m.items():
        ok = [(shid, sh) for shid, sh in e.get("shots", {}).items() if sh.get("status") == "ok"]
        if not ok:
            continue
        md += [f"## {e['name']} ({sid})", ""]
        md += [f"- `{sh['path']}`: {sh['credit']}. [{sh['file'].split(':', 1)[-1]}]({sh['page']})" for shid, sh in ok]
        md.append("")
    (bank / "CREDITS.md").write_text("\n".join(md), encoding="utf-8")
    with open(bank / "credits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["subject", "shot", "path", "credit", "author", "licence", "licence_url", "source"])
        for sid, shid, sh in rows:
            w.writerow([sid, shid, sh["path"], sh["credit"], sh.get("author", ""), sh.get("licence", ""), sh.get("licence_url", ""), sh["page"]])
    return len(rows)


def prompts(cat=None, bank=BANK, all_shots=False):
    """bank/prompts.jsonl: one AI image prompt per shot without a photo (every shot with --all). Shots of
    real people are left out: their likeness is never generated."""
    cat = cat or load_catalog()
    m = load_manifest(bank)
    lines = []
    for s in cat["subjects"]:
        for sh in s["shots"]:
            st = m.get(s["id"], {}).get("shots", {}).get(sh["id"], {}).get("status")
            if sh.get("person") or (st == "ok" and not all_shots):
                continue
            lines.append(json.dumps({"id": f"{s['id']}/{sh['id']}", "subject": s["name"], "prompt": f"{sh['scene']}. {cat['style']}",
                                     "negative": cat.get("negative", ""), "aspect": "4:5"}, ensure_ascii=False))
    Path(bank).mkdir(parents=True, exist_ok=True)
    (Path(bank) / "prompts.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def lookup(key, fmt="4x5", bank=BANK, cat=None):
    """The photos of a company or topic (id, ticker or alias): [{shot, path, credit, scene}], paths absolute."""
    cat = cat or load_catalog()
    s = find_subject(cat, key)
    if not s:
        return []
    bank = Path(bank)
    e = load_manifest(bank).get(s["id"], {}).get("shots", {})
    out = []
    for sh in s["shots"]:
        x = e.get(sh["id"], {})
        if x.get("status") != "ok":
            continue
        p = bank / x.get("crops", {}).get(fmt, x["path"])
        if p.exists():
            out.append({"shot": sh["id"], "path": str(p), "credit": x["credit"], "scene": sh["scene"]})
    return out


RULES = [
    "Use only the photos listed here for InvestIQ carousels; never other images from the web.",
    "Credit every photo you use with its exact 'credit' line: small text on the slide, or a final credits slide.",
    "Crop only. Never edit, retouch or redraw what a photo shows, and never generate a lookalike of it.",
    "Photos of real people ('person': true) show who they are; never imply that person endorses InvestIQ.",
    "Find photos by subject id, ticker or alias, then choose by 'shows'. '4x5' is 1200x1500 (portrait slide), "
    "'1x1' is 1200x1200 (square slide), 'thumb' is a small preview to look at before choosing.",
]


def index(cat=None, bank=BANK, base_url=BASE_URL):
    """bank/index.json: what the carousel chat reads. Every downloaded photo with what it shows, its credit
    and the public address of each crop (base_url + path inside bank/)."""
    cat = cat or load_catalog()
    bank = Path(bank)
    m = load_manifest(bank)
    base = base_url.rstrip("/") + "/"
    subjects, n = [], 0
    for s in cat["subjects"]:
        e = m.get(s["id"], {}).get("shots", {})
        photos = []
        for sh in s["shots"]:
            x = e.get(sh["id"], {})
            if x.get("status") != "ok":
                continue
            p = {"shot": sh["id"], "shows": sh["scene"]}
            if sh.get("person"):
                p["person"] = True
            if sh.get("historic"):
                p["historic"] = True
            p.update({f: base + path for f, path in x.get("crops", {}).items()})
            p.update(thumb=f"{base}{s['id']}/{sh['id']}.thumb.jpg", credit=x["credit"], licence=x.get("licence"), source=x.get("page"))
            photos.append(p)
        n += len(photos)
        subjects.append({"id": s["id"], "kind": s["kind"], "name": s["name"], "tickers": s.get("tickers", []),
                         "aliases": s.get("aliases", []), "photos": photos})
    out = {"about": "InvestIQ image bank for carousels: freely licensed photos of large companies and market topics, from Wikimedia Commons.",
           "rules": RULES, "updated": date.today().isoformat(), "photos": n, "subjects": subjects}
    bank.mkdir(parents=True, exist_ok=True)
    (bank / "index.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return n


def sheet(cat=None, bank=BANK):
    """bank/review.html: every shot with its photo (or its AI prompt when missing), credit, flags and alternates."""
    cat = cat or load_catalog()
    bank = Path(bank)
    m = load_manifest(bank)
    esc = html.escape
    sections, ok, total = [], 0, 0
    for s in cat["subjects"]:
        cards = []
        for sh in s["shots"]:
            total += 1
            x = m.get(s["id"], {}).get("shots", {}).get(sh["id"], {})
            st = x.get("status", "not built")
            if st == "ok":
                ok += 1
                img = f'<a href="{esc(x["path"])}"><img loading="lazy" src="{esc(s["id"])}/{esc(sh["id"])}.thumb.jpg" alt=""></a>'
                body = f'<span>{esc(x["credit"])}</span><a href="{esc(x["page"])}">Commons page</a>'
                body += "".join(f'<span class="flag">{esc(f)}</span>' for f in x.get("flags", []))
                if x.get("alternates"):
                    body += "<span>Alternates: " + " · ".join(f'<a href="{esc(a["page"])}">{i}</a>' for i, a in enumerate(x["alternates"], 1)) + "</span>"
            else:
                img = '<div class="none">no photo</div>'
                body = f'<span class="flag">{esc(x.get("note", st))}</span>'
                if not sh.get("person"):
                    body += f'<span class="prompt">AI prompt: {esc(sh["scene"])}</span>'
            cards.append(f'<div class="c {esc(st)}">{img}<b>{esc(sh["id"])}</b><span>{esc(sh["scene"])}</span>{body}</div>')
        tick = " · ".join(s.get("tickers", []))
        sections.append(f'<h2>{esc(s["name"])} <small>{esc(s["id"])}{" · " + esc(tick) if tick else ""}</small></h2><div class="g">{"".join(cards)}</div>')
    (bank / "review.html").write_text(f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Image bank</title>
<style>body{{font:13px system-ui;margin:16px;background:#fff;color:#111}}h2{{margin:28px 0 8px;font-size:17px}}small{{color:#777;font-weight:400}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}}.c{{border:1px solid #ddd;border-radius:8px;padding:8px;display:flex;flex-direction:column;gap:4px}}
.c img,.none{{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:5px;background:#eee}}.none{{display:flex;align-items:center;justify-content:center;color:#999}}
.missing,.error,.not.built{{background:#fff6f4}}span{{font-size:11px;color:#555}}.flag{{color:#a35b00}}.prompt{{color:#333;font-style:italic}}a{{font-size:11px;color:#111}}</style>
<h1>Image bank</h1><p>{ok} of {total} shots with a photo. Orange: check it. Click a photo for the full size; alternates are the next best photos on Commons
(to use one: put its file name in "prefer" and add "prefer" to "manual" in manifest.json, then build --only that subject).</p>{"".join(sections)}""", encoding="utf-8")
    return ok, total


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("build", "sheet", "credits", "prompts", "list", "check", "index"):
        sys.exit(__doc__)
    arg = lambda name: a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else None
    if a[0] == "check":
        p = check_catalog(json.loads(CATALOG.read_text(encoding="utf-8")))
        c = json.loads(CATALOG.read_text(encoding="utf-8"))
        print("\n".join(p) or f"catalog OK: {len(c['subjects'])} subjects, {sum(len(s['shots']) for s in c['subjects'])} shots")
        sys.exit(1 if p else 0)
    if a[0] == "list":
        if len(a) < 2:
            sys.exit("python image_bank.py list <id, ticker or alias> [--format 4x5]")
        for r in lookup(a[1], arg("--format") or "4x5"):
            print(f"{r['path']}\t{r['credit']}")
        sys.exit()
    if a[0] == "build":
        fm = tuple((arg("--formats") or ",".join(DEFAULT_FORMATS)).split(","))
        build(only=arg("--only"), redo="--redo" in a, no_sa="--no-sa" in a, formats=fm)
    if a[0] in ("build", "credits"):
        print(f"credits: {credits()} photos")
    if a[0] in ("build", "prompts"):
        print(f"prompts: {prompts(all_shots='--all' in a)} shots")
    if a[0] in ("build", "index"):
        print(f"index.json: {index(base_url=arg('--base-url') or BASE_URL)} photos")
    if a[0] in ("build", "sheet"):
        ok, total = sheet()
        print(f"review.html: {ok} of {total} shots with a photo ({BANK / 'review.html'})")
