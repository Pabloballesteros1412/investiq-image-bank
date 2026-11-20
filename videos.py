"""
Video clips for InvestIQ's posts (Reels, TikTok and Shorts, and horizontal video): freely licensed footage of the
bank's market topics and GICS sectors, linked, not copied, and checked by eye like the photos (Pablo, 18 Nov 2026:
both orientations, 10 clips per topic and sector to start with).

Sources (all through their official APIs):
- Pixabay videos, the main one: Pixabay Content License (commercial use, no attribution required; the bank
  credits them anyway). Needs PIXABAY_API_KEY in the environment: the key goes in the query string, so a network
  secret (a header added by the proxy) does not work. 100 requests a minute; answers are cached (Pixabay asks for
  at least 24 hours). Pixabay's API documentation lets apps embed its videos directly ("Hotlinking").
- Wikimedia Commons videos: CC0, public domain and CC BY only. CC BY-SA is left out: a reel cut from an SA clip
  would have to be shared under CC BY-SA as a whole. Mostly documentary, so a Commons clip is published only with
  grade 3, like a Commons photo.
- NASA's library: public domain, space subjects only; launch providers' and partners' footage left out.

A clip counts when it is real footage (no animation, 3D, render, CGI, motion graphics or AI), at least 1080p
(long side 1920 px), 4 to 60 s long (Commons and NASA up to 180 s: the chat trims), and its tags or file name
hold every word of the search (or a 'must' word of the shot). Commons clips must not be news, interviews,
speeches, ceremonies or events. A subject takes at most 2 clips from one uploader, and a clip is used once in
the whole bank. Each subject first gets up to VERTICAL_MIN vertical clips (Reels as they are), then the best
clips of any orientation, one per search before a second one. A horizontal clip at least 1920 px tall (4K) is
marked vertical_crop_ok: a 9:16 crop at 1080 x 1920 needs no upscaling.

Searches: the topic's own catalog shots (catalog.json), the ones that already gave published stock photos first.
Companies (Pablo, 20 Nov 2026): those with brand or product terms in brands.json, COMPANY_TARGET clips each
(FAMOUS_TARGET for the famous ones); each term is a search, and a clip counts only if its tags (Commons: its file
name) name one of the company's terms or its full name (not the short name: tags are single words, and 'Arm'
or 'Target' tag arms and archery). A company below its target gets
fill_from = its sector in the index, as with the photos.

Files: bank/video_manifest.json (every pick, graded or not) and what the chat reads, bank/videos/index.json and
bank/videos/<ID>.json (published clips only). Grades go to bank/video_review.json, apart from the photos' so the
photo and video work never edit the same file (3 best, 2 plain, 1 reject, as in RUBRIC.md): Pixabay and NASA clips are published unless graded below 3, Commons clips only with grade 3, and a
clip graded below 3 is never picked again. A rebuild (--redo) keeps a subject's published clips and fills the
free places. Commands:

    python videos.py build [--kind topic,sector,company] [--only id,id] [--redo] [--target N]
                                                    pick clips (default: topics and sectors)
    python videos.py sheets OUT_DIR                 contact sheets of the clips without a grade (3 frames each,
                                                    18 clips a sheet) and OUT_DIR/sheets.json
    python videos.py grade GRADES.json OUT_DIR      same format as review.py; then python videos.py index
    python videos.py index                          bank/videos/ for the chat
"""
import hashlib, io, json, math, os, re, subprocess, sys, tempfile, textwrap, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import image_bank as B
import stock

TARGET = 10                      # clips per topic and sector (Pablo, 18 Nov 2026)
VERTICAL_MIN = 3                 # vertical clips a subject gets first, when the sources have them
MIN_LONG = 1920                  # at least 1080p
DURATION = (4, 60)               # seconds, stock clips
DURATION_LONG = 180              # Commons and NASA clips can be longer: documentary footage, the chat trims
MAX_PER_AUTHOR = 2
COMPANY_TARGET = 5               # clips per company (Pablo, 20 Nov 2026: "mete vídeos para las empresas")
FAMOUS_TARGET = 10               # clips for the famous companies (the ones with 30 photos)
COMPANY_SEARCHES = 8             # brand terms searched per company
MAX_SEARCHES = 25                # searches per subject and source
SEARCH_ROOM = 3                  # searches with candidates beyond the target before a subject stops searching
GAP = 0.7                        # seconds between uncached Pixabay requests (its limit: 100 a minute)
FRAMES = (0.15, 0.5, 0.85)       # where the review frames are taken, as a share of the clip's length
MANIFEST = "video_manifest.json"
# Video-only searches for the subjects the catalog's photo searches left thin (19 Nov 2026). They go before the
# catalog shots and stay out of catalog.json, which belongs to the photos. Each one was tried on Pixabay first and
# kept only if it returned clips whose tags name it; words that bring look-alikes ("electric" -> guitars) are out.
VIDEO_SHOTS = {
    "ev": ["e-scooter", "electric scooter", "charging", "charger", "plug", "battery", "new cars", "car interior"],
    "quantum": ["laser", "physics", "laboratory research", "scientist laboratory", "science experiment", "plasma",
                "server room", "atom", "scientist"],
    "nuclear": ["nuclear power plant", "cooling tower", "cooling towers", "power plant steam", "power station",
                "atomic", "high voltage", "control room"],
    "bonds": ["white house", "government building", "capitol building", "dollar bills", "calculator", "paperwork",
              "accountant", "signature document"],
    "bull-market": ["wall street", "new york skyline", "financial district", "trading", "trader", "stock exchange",
                    "manhattan", "champagne toast"],
    "cybersecurity": ["hacker", "cyber", "password", "surveillance", "server room", "keyboard typing", "login",
                      "coding"],
    "fed": ["dollar bills", "cash counting", "piggy bank", "wallet money", "central bank", "banknotes counting",
            "interest", "mortgage"],
    "gold": ["gold jewelry", "gold ring", "treasure", "gold watch"],
    "politics": ["white house", "american flag", "statue of liberty", "capitol building", "lincoln memorial",
                 "election", "voting"],
    "ai": ["robot", "circuit board", "server room", "coding"],
    "recession": ["unemployed", "empty mall", "abandoned factory", "empty store", "shutter", "worried man"],
    "robotics": ["robot", "factory automation", "conveyor belt", "production line", "assembly line"],
    "sector-energy": ["refinery", "pipeline", "power plant", "gas flame", "solar panels", "wind turbines",
                      "power lines"],
}
REVIEW = "video_review.json"
FRAME_CACHE = B.HERE / ".cache" / "video_frames"

BAD = re.compile(r"\b(animation|animated|anime|cartoons?|cgi|motion ?graphics?|3d|renders?|rendered|rendering|"
                 r"illustrations?|vectors?|abstract|particles?|holograms?|futuristic|digital art|intro|logo|"
                 r"ai[- ]generated|generated|midjourney|text|typography|quotes?|green ?screen|chroma)\b", re.I)
NEWS = re.compile(r"\b(news|interviews?|speech(?:es)?|press conference|briefing|ceremon(?:y|ies)|rall(?:y|ies)|"
                  r"debates?|hearings?|lectures?|webinars?|podcasts?|trailers?|parades?|campaign|documentary|"
                  r"explained|episode|tagesschau|cramer|keynote|panel|summit|conference|award|festival|"
                  r"protests?|vlog|tutorial|how to|minecraft|gameplay|seized?|seizure|blockade|crash(?:es)?|cctv|"
                  r"accidents?|attacks?|explosions?|disasters?|police|voa|actualitatea|newsreel|footage of|"
                  r"discuss(?:es|ing|ion)?|talks?|q ?& ?a|live coverage|countdown|recruit\w*|careers?)\b", re.I)


# ---------------------------------------------------------------------------------------------------- sources

def orientation(w, h):
    return "vertical" if h > w else "horizontal" if w > h else "square"


class PixabayVideo:
    """Pixabay's video search (real footage only: video_type=film)."""
    name = "pixabay"

    def __init__(self, key, log=print):
        self.key, self.log = key, log

    def search(self, q):
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
            {"key": self.key, "q": q[:100], "video_type": "film", "safesearch": "true", "per_page": 200})
        stock._throttle(url, GAP)
        try:
            d = stock.fetch(url, {}, log=self.log)
        except stock.RateLimited:
            raise
        except Exception as e:  # never let the key reach a log
            raise RuntimeError(str(e).replace(self.key, "<key>")) from None
        return [c for c in (self.candidate(h) for h in d.get("hits", [])) if c]

    @staticmethod
    def candidate(h):
        vids = h.get("videos") or {}
        rends = sorted((v for v in vids.values() if v.get("url") and v.get("width") and v.get("height")),
                       key=lambda v: -max(v["width"], v["height"]))
        if not rends:
            return None
        best, small = rends[0], rends[-1]
        hd = next((v for v in rends if max(v["width"], v["height"]) == 1920), best)  # lighter than the 4K file
        tags = h.get("tags") or ""
        user = h.get("user") or ""
        return {"file": f"pixabay-video:{h['id']}", "provider": "pixabay", "w": best["width"], "h": best["height"],
                "duration": float(h.get("duration") or 0), "url": best["url"], "url_1080": hd["url"],
                "preview_mp4": small["url"], "poster": (vids.get("medium") or best).get("thumbnail") or best.get("thumbnail", ""),
                "page": h.get("pageURL", ""), "licence": "Pixabay Content License", "licence_code": "pixabay",
                "licence_url": "https://pixabay.com/service/license-summary/", "author": user,
                "author_url": f"https://pixabay.com/users/{user}-{h.get('user_id', '')}/", "type": h.get("type", "film"),
                "shows": tags[:200], "description": tags[:400]}


class CommonsVideo:
    """Wikimedia Commons video files (search in the File namespace with filetype:video)."""
    name = "commons"

    def __init__(self, log=print, get_json=None):
        self.log, self.get_json = log, get_json or B.get_json

    def search(self, q):
        d = self.get_json({"action": "query", "generator": "search", "gsrsearch": f"{q} filetype:video", "gsrnamespace": 6,
                           "gsrlimit": 20, "prop": "videoinfo", "viprop": "url|size|mime|extmetadata|derivatives",
                           "viextmetadatafilter": B.EXTMETA, "viextmetadatalanguage": "en", "viurlwidth": 640})
        pages = (d.get("query") or {}).get("pages") or []
        pages = sorted(pages.values() if isinstance(pages, dict) else pages, key=lambda p: p.get("index", 0))
        return [c for c in (self.candidate(p) for p in pages if p.get("videoinfo")) if c]

    @staticmethod
    def candidate(page):
        vi = page["videoinfo"][0]
        c = B.candidate({"title": page["title"], "imageinfo": [vi]})
        ders = [d for d in vi.get("derivatives") or [] if d.get("src") and "webm" in (d.get("type") or "")]
        by_h = sorted(ders, key=lambda d: max(d.get("width") or 0, d.get("height") or 0))
        hd = next((d for d in by_h if max(d.get("width") or 0, d.get("height") or 0) >= 1920), None)
        small = next((d for d in by_h if min(d.get("width") or 0, d.get("height") or 0) >= 360), by_h[0] if by_h else None)
        name = B.clean_title(page["title"])
        c.update(provider="commons", duration=float(vi.get("duration") or 0),
                 url=B.no_query(hd["src"]) if hd else c["orig"], url_1080=B.no_query(hd["src"]) if hd else c["orig"],
                 preview_mp4=B.no_query(small["src"]) if small else c["orig"], poster=B.no_query(vi.get("thumburl") or ""),
                 shows=name[:200], description=name[:400])  # the file name must name the search: categories are too loose
        return c


class NasaVideo:
    """NASA's image and video library, video only, for space subjects (stock.Nasa's rules)."""
    name = "nasa"

    def __init__(self, log=print, fetch=None):
        self.log, self.fetch = log, fetch or (lambda u: stock.fetch(u, {}, log=log))

    def search(self, q):
        if not stock.Nasa.SPACE.search(q):
            return []
        url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": "video", "page_size": 20})
        out = []
        tried = 0
        for it in self.fetch(url).get("collection", {}).get("items", []):
            d = (it.get("data") or [{}])[0]
            nid = d.get("nasa_id")
            text = " ".join([d.get("title") or "", d.get("description") or "", " ".join(d.get("keywords") or [])])
            if not nid or self.third(d) or not B.stock_match({"description": text}, {}, q):
                continue  # each clip costs two more requests (its files and its metadata): only likely ones
            if tried >= 6:
                break
            tried += 1
            try:
                hrefs = [x["href"] for x in self.fetch(f"https://images-api.nasa.gov/asset/{urllib.parse.quote(nid)}")
                         .get("collection", {}).get("items", [])]
                meta = next((self.fetch(self.href(h)) for h in hrefs if h.endswith("metadata.json")), {})
            except Exception:
                continue
            out.append(self.candidate(d, hrefs, meta))
        return [c for c in out if c]

    @staticmethod
    def third(d):
        credit = re.search(r"(?:video|footage|image|photo) credit:?\s*([^.;\n]+)", d.get("description") or "", re.I)
        # a launch provider in the title too: its launch footage is usually the provider's own camera feed
        return bool(stock.Nasa.THIRD.search(" ".join([d.get("photographer") or "", d.get("secondary_creator") or "", d.get("title") or ""]))
                    or (credit and "nasa" not in credit.group(1).lower()))

    @staticmethod
    def href(h):
        """An asset address as NASA lists it ('http://', raw spaces in some names) made fetchable."""
        return urllib.parse.quote(h.replace("http://", "https://", 1), safe=":/%~")

    @staticmethod
    def candidate(d, hrefs, meta):
        https = [NasaVideo.href(h) for h in hrefs]
        get = lambda end: next((h for h in https if h.endswith(end)), None)
        orig, w, h = get("~orig.mp4"), int(meta.get("QuickTime:ImageWidth") or 0), int(meta.get("QuickTime:ImageHeight") or 0)
        if not orig or not w or not h:
            return None
        hms = [int(x) for x in re.findall(r"\d+", str(meta.get("QuickTime:Duration") or ""))[-3:]]
        secs = sum(x * 60 ** i for i, x in enumerate(reversed(hms))) if hms else 0
        nid, title = d["nasa_id"], d.get("title") or ""
        who = d.get("photographer") or ""
        return {"file": f"nasa-video:{nid}", "provider": "nasa", "w": w, "h": h, "duration": float(secs),
                "url": orig, "url_1080": get("~large.mp4") or orig, "preview_mp4": get("~small.mp4") or get("~preview.mp4") or orig,
                "poster": get("~medium.jpg") or "", "frames": [f for f in (get("~small_1.jpg"), get("~small_3.jpg"), get("~small_5.jpg")) if f],
                "page": f"https://images.nasa.gov/details/{urllib.parse.quote(nid)}", "licence": "Public domain (NASA)",
                "licence_code": "pd-nasa", "licence_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
                "author": ("NASA/" + who) if who and not who.upper().startswith("NASA") else (who or "NASA"),
                "author_url": "https://images.nasa.gov", "shows": title[:200],
                "description": " ".join([title, d.get("description") or "", " ".join(d.get("keywords") or [])])[:400]}


def sources(env=None, log=print):
    """Pixabay when its key is in the environment, then Commons and NASA (no key)."""
    env = os.environ if env is None else env
    key = (env.get("PIXABAY_API_KEY") or "").strip()
    return ([PixabayVideo(key, log)] if key else []) + [CommonsVideo(log), NasaVideo(log)]


# --------------------------------------------------------------------------------------------------- choosing

def credit_line(c):
    p = c["provider"]
    if p == "pixabay":
        return f"Video by {c.get('author') or 'unknown'} on Pixabay"
    if p == "nasa":
        return f"Video: {c.get('author') or 'NASA'}, public domain"
    lic = "public domain" if B.licence_kind(c) == "pd" else c.get("licence") or "free licence"
    return f"{c.get('author') or 'Unknown author'}, {lic}, via Wikimedia Commons"


def ok(c, shot, q, grades=None, used=()):
    """Whether a candidate clip can be picked for a shot (see the module docstring)."""
    grades = grades or {}
    if c["file"] in used or (grades.get(c["file"]) or 3) < 3:
        return False
    long_ok = c["provider"] != "pixabay"
    if max(c.get("w", 0), c.get("h", 0)) < MIN_LONG:
        return False
    if not DURATION[0] <= c.get("duration", 0) <= (DURATION_LONG if long_ok else DURATION[1]):
        return False
    if BAD.search(c.get("description", "")) or c.get("type", "film") != "film":
        return False
    if c["provider"] == "nasa" and NEWS.search(c.get("shows", "")):
        return False  # NASA's library is full of briefings, interviews and trailers
    if c["provider"] == "commons":
        if B.licence_kind(c) not in ("cc0", "pd", "by") or c.get("restrictions"):
            return False
        hay = " ".join([c["file"], " ".join(c.get("categories", []))])
        if NEWS.search(hay) or B.EVENTS.search(hay) or B.bad_name(c["file"]):
            return False
    if shot.get("keys"):  # a company's clip must name one of its brands, its full name or its short name
        hay = B.flat(c.get("description", ""))
        return any(B.has_name(hay, k) for k in shot["keys"])
    return B.stock_match(c, shot, q)


def score(c, rank):
    s = 100 - 2 * rank
    s += {"pixabay": 30, "nasa": 20}.get(c["provider"], 0)
    s += 15 if max(c["w"], c["h"]) >= 3840 else 0
    d = c.get("duration", 0)
    s += 10 if 6 <= d <= 30 else -10 if d > 60 else 0
    return s


def video(c, shot):
    """A picked clip as kept in the manifest."""
    o = orientation(c["w"], c["h"])
    e = {"shot": shot, "shows": c.get("shows", ""), "file": c["file"], "provider": c["provider"], "page": c["page"],
         "url": c["url"], "url_1080": c["url_1080"], "preview_mp4": c["preview_mp4"], "poster": c.get("poster", ""),
         "size": [c["w"], c["h"]], "orientation": o, "duration": round(c.get("duration", 0), 1),
         "credit": credit_line(c), "licence": c["licence"], "licence_kind": B.licence_kind(c) or c.get("licence_code"),
         "licence_url": c.get("licence_url", ""), "author": c.get("author", ""), "author_url": c.get("author_url", "")}
    if o == "horizontal" and c["h"] >= 1920:
        e["vertical_crop_ok"] = True
    if c.get("frames"):
        e["frames"] = c["frames"]
    return e


def pick(pool, target=TARGET, vertical_min=VERTICAL_MIN, keep=()):
    """Clips from a pool of (score, shot id, candidate): the kept ones, then up to vertical_min vertical ones, then
    the best of any orientation, one per shot before a second; at most MAX_PER_AUTHOR per uploader."""
    out = list(keep)
    files = {v["file"] for v in out}
    authors, per_shot = {}, {}
    for v in out:
        authors[v.get("author")] = authors.get(v.get("author"), 0) + 1
        per_shot[v["shot"]] = per_shot.get(v["shot"], 0) + 1
    ranked = sorted(pool, key=lambda t: -t[0])

    def take(cands, limit, cap):
        for s, shot, c in cands:
            if len(out) >= limit:
                return
            a = c.get("author")
            if c["file"] in files or authors.get(a, 0) >= MAX_PER_AUTHOR or per_shot.get(shot, 0) >= cap:
                continue
            out.append(video(c, shot))
            files.add(c["file"])
            authors[a] = authors.get(a, 0) + 1
            per_shot[shot] = per_shot.get(shot, 0) + 1

    have_v = sum(1 for v in out if v["orientation"] == "vertical")
    if have_v < vertical_min:
        take([t for t in ranked if orientation(t[2]["w"], t[2]["h"]) == "vertical"], len(out) + vertical_min - have_v, 1)
    for cap in range(1, target + 1):
        take(ranked, target, cap)
        if len(out) >= target:
            break
    return out[:max(target, len(keep))]


def shot_order(s, photo_entry=None, rv=None):
    """The subject's video-only searches (VIDEO_SHOTS) first, then its catalog shots: the ones that gave
    published stock photos first (proven search words), then the rest in catalog order."""
    rv = rv or {"grades": {}}
    good = {}
    for p in (photo_entry or {}).get("photos", []):
        if B.provider_of(p) != "commons" and B.published(p, rv):
            good[p.get("shot")] = good.get(p.get("shot"), 0) + 1
    shots = [B.norm_shot(x) for x in s.get("shots", [])]
    ordered = sorted(shots, key=lambda sh: (-good.get(sh["id"], 0), shots.index(sh)))
    extra = [B.norm_shot(q) for q in s.get("video_shots", VIDEO_SHOTS.get(s.get("id"), []))]
    ids = {sh["id"] for sh in extra}
    return extra + [sh for sh in ordered if sh["id"] not in ids]


def subject_videos(s, srcs, grades=None, used=(), keep=(), target=TARGET, photo_entry=None, rv=None, log=print,
                   max_searches=MAX_SEARCHES):
    """Clips for one topic or sector: search its shots on every source until enough shots have candidates."""
    pool, with_cands, n = [], set(), 0
    keep_files = {v["file"] for v in keep}
    for shot in shot_order(s, photo_entry, rv):
        verticals = sum(1 for t in pool if orientation(t[2]["w"], t[2]["h"]) == "vertical")
        if len(with_cands) >= target - len(keep) + SEARCH_ROOM and verticals >= VERTICAL_MIN:
            break
        if n >= max_searches:
            break
        n += 1
        for src in srcs:
            for rank, c in enumerate(B.safe_search(src)(shot["q"])):
                if c["file"] not in keep_files and ok(c, shot, shot["q"], grades, used):
                    pool.append((score(c, rank), shot["id"], c))
                    with_cands.add(shot["id"])
    log(f"  {n} searches, {len(pool)} candidates from {len(with_cands)} shots")
    return pick(pool, target, keep=keep)


def company_subjects(photos, brands, only=None):
    """The companies to search: those with brand or product terms in brands.json (stock footage is tagged with
    brands, not with company names: 'Starbucks', not 'Starbucks Corporation'). Each term is a search, and a clip
    counts only if its tags name one of the company's terms or its full name."""
    out = []
    for cid, e in photos.items():
        terms = brands.get(cid)
        if e.get("kind") != "company" or not terms or (only and cid not in only):
            continue
        # not the short name: video tags are single words, and 'Arm', 'Ford' or 'Target' tag arms, rivers and archery
        keys = B.brand_keys({"name": e["name"], "commons_category": e.get("commons_category"), "ambiguous": True}, terms)
        shots = [{"id": B.slug(t), "q": t, "keys": keys} for t in list(dict.fromkeys(terms))[:COMPANY_SEARCHES]]
        famous = (e.get("target") or 0) > B.TARGET
        out.append({"id": cid, "kind": "company", "name": e["name"], "sector": e.get("sector"), "shots": shots,
                    "target": FAMOUS_TARGET if famous else COMPANY_TARGET})
    return out


# ------------------------------------------------------------------------------------------- manifest & index

def load(bank=B.BANK):
    p = Path(bank) / MANIFEST
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save(m, bank=B.BANK):
    B.write_atomic(Path(bank) / MANIFEST, json.dumps(m, indent=1, ensure_ascii=False))


def load_review(bank=B.BANK):
    p = Path(bank) / REVIEW
    rv = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    rv.setdefault("grades", {})
    return rv


def save_review(rv, bank=B.BANK):
    rv = {"about": "Grades of the video clips checked by eye (videos.py sheets / grade): 3 best, 2 plain, 1 reject. "
                   "Pixabay and NASA clips are published unless graded below 3, Commons clips only with grade 3; a clip "
                   "graded below 3 is never picked again.",
          "updated": date.today().isoformat(), "grades": dict(sorted(rv.get("grades", {}).items()))}
    B.write_atomic(Path(bank) / REVIEW, json.dumps(rv, indent=1, ensure_ascii=False))


def grade(grades_file, sheets_dir, bank=B.BANK):
    """Merge grades given per sheet tile (review.py's format) into bank/video_review.json; tiles not listed get 1."""
    idx = json.loads((Path(sheets_dir) / "sheets.json").read_text(encoding="utf-8"))
    given = json.loads(Path(grades_file).read_text(encoding="utf-8"))
    rv, count = load_review(bank), {1: 0, 2: 0, 3: 0}
    for name, tiles in idx.items():
        if name not in given:
            continue
        g = {str(t): int(k) for k, ts in given[name].items() for t in ts}
        for t, ref in tiles.items():
            rv["grades"][ref["file"]] = g.get(t, 1)
            count[g.get(t, 1)] += 1
    save_review(rv, bank)
    return count


def published(v, grades):
    """Whether a clip reaches the chat: Commons clips with grade 3, the others unless graded below 3."""
    g = grades.get(v["file"])
    return (g or 0) >= 3 if v["provider"] == "commons" else g is None or g >= 3


def build(bank=B.BANK, catalog=None, srcs=None, only=None, redo=False, target=None, log=print, kinds=("topic", "sector"),
          brands=None):
    """Pick clips for the catalog's topics and sectors and/or the companies; the manifest is saved after every
    subject."""
    cat = catalog or B.load_catalog()
    srcs = sources(log=log) if srcs is None else srcs
    if not any(s.name == "pixabay" for s in srcs):
        log("  (no PIXABAY_API_KEY: Commons and NASA only)")
    m, rv, prv = load(bank), load_review(bank), B.load_review(bank)
    photos = B.load_manifest(bank)
    subjects = [s for s in cat["subjects"] if s.get("kind") in kinds and s.get("kind") != "company" and (not only or s["id"] in only)]
    if "company" in kinds:
        subjects += company_subjects(photos, B.load_brands() if brands is None else brands, only)
    for i, s in enumerate(subjects, 1):
        old = m.get(s["id"])
        if old and not redo:
            continue
        keep = [v for v in (old or {}).get("videos", []) if published(v, rv["grades"])]
        used = {v["file"] for sid, e in m.items() if sid != s["id"] for v in e.get("videos", [])}
        log(f"{i:3}/{len(subjects)} {s['id']}")
        t = target or s.get("target") or TARGET
        src = [x for x in srcs if x.name != "nasa"] if s["kind"] == "company" else srcs  # NASA leaves providers out
        vids = subject_videos(s, src, rv["grades"], used, keep, t, photos.get(s["id"]), prv, log)
        m[s["id"]] = {"kind": s["kind"], "name": s["name"], "target": t, "checked": date.today().isoformat(), "videos": vids}
        if s.get("sector"):
            m[s["id"]]["sector"] = s["sector"]
        save(m, bank)
        nv = sum(1 for v in vids if v["orientation"] == "vertical")
        log(f"      {len(vids)} clips ({nv} vertical)")
    return index(bank)


RULES = [
    "A topic or sector clip is generic footage: never present it as footage of a specific company, person or event. "
    "Never say a person in any clip is anyone in particular.",
    "A company clip shows one of the company's own brands, products, stores or places, as its uploader tagged it "
    "('a Starbucks cup', 'a Tesla on the road'): describe what it shows, never present it as the company's own footage, "
    "an advert or a news event. A company with fewer clips than its target has fill_from = its sector: those clips "
    "are generic and must never be presented as the company's.",
    "Download the file to edit it: 'url' is the best file (often 4K), 'url_1080' a lighter 1080p one. Mute the "
    "clip's own sound, or replace it with cleared music.",
    "orientation 'vertical' fits Reels, TikTok and Shorts as it is. A horizontal clip with vertical_crop_ok is 4K and "
    "can be cropped to 9:16 at 1080 x 1920 without upscaling; other horizontal clips are for 16:9 video or a band "
    "inside a vertical frame.",
    "Credit every clip with its 'credit' line where the post's credits go (caption or end card). Pixabay asks for no "
    "credit but the bank gives one; Commons clips are CC0, public domain or CC BY (CC BY needs the credit).",
    "A subject with few or no clips: use its photos (bank/index.json) instead.",
]


def index(bank=B.BANK, base_url=B.BASE_URL):
    """bank/videos/index.json and bank/videos/<ID>.json: the published clips, for the chat."""
    bank = Path(bank)
    m, rv = load(bank), load_review(bank)
    base = base_url.rstrip("/") + "/videos/"
    out_dir = bank / "videos"
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("*.json"):
        f.unlink()
    keep = ("shows", "url", "url_1080", "poster", "size", "orientation", "vertical_crop_ok", "duration", "credit",
            "licence", "licence_url", "author_url", "provider")
    entries, total = [], 0
    for sid, e in m.items():
        vids = [{**{k: v[k] for k in keep if k in v}, "source": v["page"]} for v in e.get("videos", []) if published(v, rv["grades"])]
        total += len(vids)
        rec = {"id": sid, "kind": e["kind"], "name": e["name"], "videos": len(vids),
               "vertical": sum(1 for v in vids if v["orientation"] == "vertical"), "target": e.get("target", TARGET),
               "file": f"{base}{B.safe(sid)}.json"}
        if e.get("sector"):
            rec["sector"] = e["sector"]
            if len(vids) < rec["target"]:
                rec["fill_from"] = e["sector"]
        entries.append(rec)
        (out_dir / f"{B.safe(sid)}.json").write_text(json.dumps({**{k: rec[k] for k in ("id", "kind", "name", "target", "sector", "fill_from") if k in rec},
                                                                 "videos": vids}, indent=1, ensure_ascii=False), encoding="utf-8")
    B.write_atomic(out_dir / "index.json", json.dumps(
        {"about": "InvestIQ video bank: freely licensed clips of market topics, GICS sectors and companies' brands "
                  "(Pixabay, Wikimedia Commons, NASA), checked by eye, for Reels, TikTok, Shorts and horizontal video.",
         "rules": RULES, "updated": date.today().isoformat(), "videos": total, "subjects": entries}, indent=1, ensure_ascii=False))
    return total


# ------------------------------------------------------------------------------------------------------ review

def download(url, dest):
    h = B.headers() if "wikimedia.org" in url else {"User-Agent": B.UA}  # the Wikimedia token goes to Wikimedia only
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120) as r:
                Path(dest).write_bytes(r.read())
            return
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 5:
                raise
            time.sleep(B.wait_for(e, attempt))


def frame_urls(v):
    """Image addresses of review frames, when the source serves them: NASA's own stills, Commons thumbnails
    taken at a given second."""
    if v.get("frames"):
        return v["frames"]
    if v["provider"] == "commons" and "px--" in (v.get("poster") or ""):
        return [v["poster"].replace("px--", f"px-seek%3D{max(1, int(v['duration'] * f))}-", 1) for f in FRAMES]
    return []


def frames(v):
    """Three PIL frames of a clip (cached in .cache/video_frames): stills from the source, else taken from its
    smallest file with ffmpeg (the file is deleted afterwards)."""
    from PIL import Image
    FRAME_CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(v["file"].encode()).hexdigest()
    paths = [FRAME_CACHE / f"{key}-{i}.jpg" for i in range(len(FRAMES))]
    if not all(p.exists() and p.stat().st_size for p in paths):
        urls = frame_urls(v)
        if urls:
            for u, p in zip(urls, paths):
                download(u, p)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                clip = Path(tmp) / "clip"
                download(v["preview_mp4"], clip)
                for f, p in zip(FRAMES, paths):
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{v['duration'] * f:.2f}", "-i", str(clip),
                                    "-frames:v", "1", "-q:v", "3", str(p)], check=True, timeout=120)
    out = []
    for p in paths:
        try:
            out.append(Image.open(p).convert("RGB"))
        except Exception:
            out.append(Image.new("RGB", (16, 9), "black"))
    return out


def sheets(out, bank=B.BANK, cols=3, rows=6, box=200):
    """Contact sheets of the clips without a grade: 3 frames a clip, numbered; out/sheets.json maps tiles to clips."""
    from PIL import Image, ImageDraw
    import review
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    m, rv = load(bank), load_review(bank)
    todo = [(sid, v) for sid, e in m.items() for v in e.get("videos", []) if v["file"] not in rv["grades"]]
    per, tw, label = cols * rows, 3 * box + 8, 44
    idx, f_num, f_bold, f_text = {}, review.font(22, True), review.font(13, True), review.font(12)
    for n in range(0, len(todo), per):
        batch = todo[n:n + per]
        with ThreadPoolExecutor(3) as ex:
            ims = list(ex.map(lambda sv: frames(sv[1]), batch))
        sheet = Image.new("RGB", (cols * (tw + 10) + 10, rows * (box + label + 10) + 10), "white")
        d = ImageDraw.Draw(sheet)
        name = f"sheet-{n // per + 1:03d}"
        idx[name] = {}
        for i, ((sid, v), fr) in enumerate(zip(batch, ims), 1):
            x, y = 10 + (i - 1) % cols * (tw + 10), 10 + (i - 1) // cols * (box + label + 10)
            for k, im in enumerate(fr):
                im.thumbnail((box, box))
                cell = Image.new("RGB", (box, box), (40, 40, 40))
                cell.paste(im, ((box - im.width) // 2, (box - im.height) // 2))
                sheet.paste(cell, (x + k * (box + 4), y))
            d.rectangle((x, y, x + 34, y + 28), fill="black")
            d.text((x + 4, y + 2), str(i), font=f_num, fill="white")
            w, h = v["size"]
            meta = f"{m[sid]['name']} | {v['duration']:.0f}s {w}x{h} {v['orientation'][0].upper()}{' crop' if v.get('vertical_crop_ok') else ''} | {v['provider']}"
            d.text((x, y + box + 3), textwrap.shorten(meta, 80, placeholder="…"), font=f_bold, fill=(10, 10, 10))
            d.text((x, y + box + 22), textwrap.shorten(v.get("shows", ""), 90, placeholder="…"), font=f_text, fill=(80, 80, 80))
            idx[name][str(i)] = {"subject": sid, "file": v["file"]}
        sheet.save(out / f"{name}.jpg", quality=85)
    (out / "sheets.json").write_text(json.dumps(idx, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(idx)


if __name__ == "__main__":
    a = sys.argv[1:]
    opt = lambda k: a[a.index(k) + 1] if k in a and a.index(k) + 1 < len(a) else None
    if a[:1] == ["build"]:
        only = set(opt("--only").split(",")) if opt("--only") else None
        log = lambda *x: print(*x, flush=True)
        kinds = tuple((opt("--kind") or "topic,sector").split(","))
        tgt = int(opt("--target")) if opt("--target") else None
        print("videos.json:", build(only=only, redo="--redo" in a, target=tgt, log=log, kinds=kinds), "clips published")
    elif a[:1] == ["sheets"] and len(a) > 1:
        print(sheets(a[1]), "sheets")
    elif a[:1] == ["grade"] and len(a) > 2:
        print(grade(a[1], a[2]))
        print("videos:", index(), "clips published")
    elif a[:1] == ["index"]:
        print("videos:", index(), "clips published")
    else:
        sys.exit(__doc__)
