"""
InvestIQ's image bank for the Claude chat that makes InvestIQ's carousels: up to 10 freely licensed photos for
every S&P 500 company and well-known US-listed company (extras.json), for every market topic and for every
GICS sector (catalog.json). Companies: Wikimedia Commons, the photos graded best by eye (review.py,
bank/review.json), then Unsplash and Pexels photos of their brands (brands.json), then their plain Commons photos
(graded 2, marked plain) for the places left. Topics and sectors: Unsplash and Pexels first (stock.py), Commons when they have nothing
that matches the search. Photos are not copied: bank/index.json and
bank/subjects/<ID>.json give the chat each photo's address, what it shows, its credit line and the
point to crop around, and the chat crops it to 4:5 or 1:1 itself.

    python image_bank.py universe                 (the companies: S&P 500 from Wikipedia + extras.json + catalog,
                                                   with Wikidata id, Commons category, CEO, main image -> bank/universe.json)
    python image_bank.py build                    (photos for every company, topic and sector not done yet)
    python image_bank.py build --only AAPL,gold   (again for some subjects, by id, ticker or alias)
    python image_bank.py build --kind topic,sector (only those kinds: company, topic, sector)
    python image_bank.py build --redo             (again for every subject not fixed by hand)
    python image_bank.py build --no-sa            (no CC BY-SA photos: only CC0, public domain and CC BY)
    python image_bank.py build --kind company --stock-only  (companies: keep their approved Commons photos and
                                                   pick their Unsplash/Pexels brand photos again; brands.json)
    python image_bank.py build --commons-only     (go on without Unsplash/Pexels: otherwise a build of topics,
                                                   sectors or brand photos stops when no stock source answers)
    python image_bank.py index [--base-url URL]   (bank/index.json + bank/subjects/*.json; default: the repo's raw GitHub address)
    python image_bank.py credits                  (bank/CREDITS.md and bank/credits.csv)
    python image_bank.py prompts [--all]          (bank/prompts.jsonl: AI prompts for hand-written shots without a photo)
    python image_bank.py list AAPL                (the photos of a company, topic or sector, with their credit line)
    python image_bank.py check                    (validate catalog.json and extras.json)

Needs Python 3.9+ (no other package) and network access to en.wikipedia.org, www.wikidata.org and
commons.wikimedia.org. The carousel chat needs upload.wikimedia.org (where the photos are). From shared cloud
addresses Wikimedia answers anonymous API calls with HTTP 429 (too many requests): set WIKIMEDIA_TOKEN to the
access token of an owner-only OAuth 2 consumer of a Wikimedia account and the calls go out logged in.
UNSPLASH_ACCESS_KEY and PEXELS_API_KEY add those sources (api/images.unsplash.com, api/images.pexels.com).
After a build, grade the new Commons photos (python review.py sheets, then grade): until then they are not
published.

Which photos: a company gets its hand-written shots from catalog.json first (50 large companies have
them), then its main image on Wikidata, a photo of its CEO, the best photos of its Commons category and
subcategories (at most two per subcategory, no near-duplicates), then Commons searches for its headquarters,
stores, factories and offices whose file name or categories name the company. Topics and sectors have 10
hand-written searches each, run on Unsplash, Pexels and Commons: a stock photo must name every word of the
search (or a 'must' word) in its description, and wins over Commons when it does. A company's places not taken
by approved Commons photos go to Unsplash and Pexels photos of its brands (brands.json: 'iPhone', 'Big Mac'),
which count only when their description names a brand, the full name or an unambiguous short name. A photo is accepted only
with a free licence (CC0, public domain, CC BY, CC BY-SA, Unsplash, Pexels), at least 1600 px on the long side
and 1000 px on the short side, as JPEG or PNG, with a file name that is not a logo, map, chart, diagram or
screenshot (stock: no renders, illustrations or quotes), and not used anywhere else in the bank. Ranking: search relevance,
Commons "featured" / "quality" / "valued" pictures first, proportions that crop well to 4:5 and 1:1, recent
photos (unless the shot is historic), freer licences. A company with fewer than 10 photos of its own is
completed in the index by its GICS sector's photos (generic, marked as such).

Corrections by hand in bank/manifest.json, on a subject: "exclude": ["File:..."] (never use those photos)
with "manual": ["exclude"], then build --only <ID>; "manual": true freezes the subject. In
bank/universe.json, on a company: "commons_category", "ceo", "image" or "name" corrected by hand and listed
in "manual" (e.g. "manual": ["commons_category"]) survive the next `universe`.
"""
import csv, html, json, os, re, sys, threading, time, unicodedata, urllib.error, urllib.parse, urllib.request
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date
from pathlib import Path

import stock

HERE = Path(__file__).resolve().parent
CATALOG, EXTRAS, BRANDS = HERE / "catalog.json", HERE / "extras.json", HERE / "brands.json"
BANK = HERE / "bank"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
ENWIKI_API = "https://en.wikipedia.org/w/api.php"
UA = "InvestIQ-image-bank/2.0 (https://getinvestiq.com; carousel image bank)"
BASE_URL = "https://raw.githubusercontent.com/Pabloballesteros1412/investiq-image-bank/main/bank/"  # public address of bank/

TARGET = 10                           # photos per company
FAMOUS_TARGET = 30                    # photos per well-known company (the companies with a hand-written catalog entry)
TOPIC_TARGET = 50                     # photos per market topic and GICS sector
QUALITY = re.compile(r"\b(featured pictures|quality images|valued images)\b", re.I)
RESERVE_GRADE = 2                     # a company's plain Commons photos fill the places its better ones leave free
HAND = "hand-picked"                  # 'how' of photos found by a hand search and graded by eye: a rebuild keeps them
SEARCH_ROOM = 3                       # places a company's Commons category leaves for photos found by search
MIN_LONG, MIN_SHORT = 1600, 1000      # smallest acceptable photo (px)
MIN_PERSON = 1000, 700                # portraits: a face mostly fills half a slide or an inset
WIDTHS = (1280, 1920)                 # standard Wikimedia thumbnail widths linked for the slides
PREVIEW_W = 500                       # standard width of the preview
SLIDE_H = 1500                        # a 4:5 slide is 1200 x 1500
PERSON_FOCUS = (0.5, 0.33)            # faces sit in the upper third
STOCK = ("unsplash", "pexels", "flickr", "nasa", "pixabay")  # photo sources besides Commons (stock.py)
STOCK_BONUS = 30                      # a stock photo that matches the search beats a Commons one: they look better
STOCK_BAD = re.compile(r"\b(illustrations?|3d|renders?|rendering|vectors?|cartoons?|drawings?|sketch(?:es)?|clip ?art|"
                       r"mock-?ups?|ai[- ]generated|generated by ai|midjourney|typography|quotes?)\b", re.I)
BRAND_QUERIES = 3                     # brands searched on each stock source per company
MIMES = {"image/jpeg", "image/png"}
BAD_WORDS = ["logo", "logotype", "wordmark", "icon", "map", "diagram", "chart", "graph", "plot", "screenshot",
             "infographic", "coat of arms", "flag of", "seal of", "emblem", "drawing", "illustration", "render",
             "rendering", "sketch", "plan", "blueprint", "label", "poster", "banner", "stamp", "signature",
             "bioart", "cover art", "figure", "micrograph"]
SKIP_CATEGORY = re.compile(r"\b(logos?|wordmarks?|icons?|maps?|diagrams?|charts?|graphs?|screenshots?|documents?|advertis\w*|"
                           r"posters?|svg|signatures?|videos?|audio|sounds?|pdf|patents?|drawings?|illustrations?|stamps?|texts?|"
                           r"coats? of arms|flags?|scans?|letters?|annual reports?|share certificates?|people|employees|"
                           r"executives|staff|personnel|alumni|awards?|visits?)\b", re.I)
COMPANY_PARENT = re.compile(r"compan|corporat|conglomerat|brands?\b|business|enterprises|manufactur|banks?\b|retail|insur|"
                            r"utilit|restaurant|real estate|REIT|firms?\b|airlines?\b|operators|chains?\b|S&P|NYSE|Nasdaq", re.I)
# a company's sponsorships, races, teams, shows and events: photos that would pass for the company's own
EVENTS = re.compile(r"\b(sports?|racing|races?|NASCAR|IndyCar|Formula (?:One|1|E)|Grand Prix|Speedway|motorsports?|sponsor\w*|bowl|"
                    r"cup|championships?|tournaments?|stadiums?|arenas?|ballparks?|teams?|players|drivers|concerts?|"
                    r"festivals?|tours|music|albums?|songs?|films?|movies?|television|TV series|episodes?|video games?|seasons?|"
                    r"premieres?|parades?|esports|athletes|matches|leagues?|pride|protests?|protesters|demonstrations?|"
                    r"marches|rall(?:y|ies)|strikes?|pickets?|vigils?)\b|\b[1-9]\d{2}$", re.I)  # races: 'Daytona 500'
# what a search hit's file name must also say for it to be a company's own place or thing
BUSINESS = re.compile(r"\b(headquarters|HQ|head office|offices?|stores?|shops?|showroom|factory|factories|plants?|mills?|"
                      r"refinery|warehouse|distribution|fulfillment|data cent(?:er|re)|buildings?|towers?|campus|cent(?:er|re)|"
                      r"branch|outlet|restaurants?|caf[eé]|dealership|station|terminal|depot|signs?|signage|trucks?|vans?|"
                      r"aircraft|airplanes?|planes?|ships?|vessels?|products?|booth|lobby|facility|facilities|site|works|"
                      r"laborator(?:y|ies)|lab|hospital|clinic|pharmacy|mine|rig|platform|pipeline|substation|power plant|"
                      r"wind farm|solar|hotel|casino|resort|theme park|campus|corporate|company|inc|corp|plc|ltd|LLC)\b", re.I)
SCREENS = re.compile(r"\b(screenshots?|screen captures?|web ?pages?|user interfaces?)\b", re.I)
OLD_PAPER = re.compile(r"\b(letters|manuscripts|documents|artworks|paintings|engravings|drawings|prints|scans|"
                       r"Historic American (?:Buildings Survey|Engineering Record|Landscapes Survey))\b", re.I)
GENERIC_WORDS = {"inc", "corp", "corporation", "company", "co", "group", "holdings", "holding", "plc", "the", "ltd",
                 "limited", "n.v", "nv", "s.a", "sa", "ag", "se", "incorporated", "&", "and", "class", "a", "b", "c"}
SECTORS = {"Information Technology": "sector-tech", "Health Care": "sector-health", "Financials": "sector-financials",
           "Consumer Discretionary": "sector-consumer-discretionary", "Communication Services": "sector-communication",
           "Industrials": "sector-industrials", "Consumer Staples": "sector-staples", "Energy": "sector-energy",
           "Utilities": "sector-utilities", "Real Estate": "sector-real-estate", "Materials": "sector-materials"}
EXTMETA = "|".join(["LicenseShortName", "License", "LicenseUrl", "Artist", "Credit", "DateTimeOriginal", "Categories",
                    "Restrictions", "ImageDescription"])
IMAGEINFO = {"prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiextmetadatafilter": EXTMETA, "iiextmetadatalanguage": "en"}
RULES = [
    "Use only the photos listed in this bank for InvestIQ carousels; never other images from the web.",
    "Each subject (company, topic or sector) has a file at its 'file' address with its photos: up to 10 for a "
    "company, 30 for a well-known one, 50 for a topic or sector ('target'). For each photo: "
    "'url' is the photo on Wikimedia Commons (about 1280-1920 px wide), 'preview' a 500 px version to look at before "
    "choosing, 'shows' what it shows, 'focus' [x, y] the point to keep when cropping (0-1 from the left and from the top).",
    "Crop the photo to the slide yourself: 4:5 (1200x1500) or 1:1 (1200x1200), centred on 'focus'. In HTML: "
    "object-fit: cover; object-position: x% y% (x and y times 100).",
    "Credit every photo you use with its exact 'credit' line: small text on the slide, or a final credits slide. "
    "Photos from Unsplash, Pexels, Flickr, NASA and Pixabay ('provider') also give 'author_url': link the photographer there when the "
    "carousel has links (a post caption, a web page).",
    "Crop only. Never edit, retouch or redraw what a photo shows, and never generate a lookalike of it.",
    "Photos of real people ('person': true) show who they are; never imply that person endorses InvestIQ. Roles "
    "(CEO, chair...) come from Wikidata or the catalog and can be out of date: check before naming one.",
    "A company with fewer photos than its 'target' has 'fill_from': a GICS sector whose photos are generic. Use them only as "
    "illustration, never presented as that company's own premises, products or people.",
    "Photos with 'plain': true are the company's own but ordinary (a facade with no name, grey light): they come "
    "after its other photos. Prefer the others, and for a cover slide its sector's photos, before a plain one.",
    "Photos with 'low_res': true (Flickr through Openverse) are only 1024 px on their long side and look soft "
    "full-bleed: never use one as a cover; use it smaller (half a slide, an inset or a grid) rather than "
    "stretched over a whole slide.",
]


# ---------- catalog and extras ----------

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "shot"


def norm_shot(x):
    """A shot written as a plain search string -> {id, q, scene}."""
    return {"id": slug(x), "q": x, "scene": x} if isinstance(x, str) else x


def norm_catalog(cat):
    for s in cat.get("subjects", []):
        s["shots"] = [norm_shot(x) for x in s.get("shots", [])]
    return cat


def load_catalog(path=None):
    cat = norm_catalog(json.loads(Path(path or CATALOG).read_text(encoding="utf-8")))
    problems = check_catalog(cat)
    if problems:
        raise ValueError("catalog.json: " + "; ".join(problems))
    return cat


def load_extras(path=None):
    p = Path(path or EXTRAS)
    return json.loads(p.read_text(encoding="utf-8")).get("companies", []) if p.exists() else []


def load_brands(path=None):
    """{ticker: [brand or product names]} from brands.json: what stock photo descriptions name."""
    p = Path(path or BRANDS)
    return json.loads(p.read_text(encoding="utf-8")).get("brands", {}) if p.exists() else {}


def check_catalog(cat, extras=None):
    """List of problems in the catalog (and extras, when given); empty when valid."""
    cat = norm_catalog(cat)
    out, ids, keys = [], set(), {}
    for s in cat.get("subjects", []):
        sid, kind = s.get("id"), s.get("kind")
        if not sid or sid in ids:
            out.append(f"missing or repeated subject id {sid!r}")
        ids.add(sid)
        if kind not in ("company", "topic", "sector"):
            out.append(f"{sid}: kind must be company, topic or sector")
        if kind == "sector" and SECTORS.get(s.get("gics")) != sid:
            out.append(f"{sid}: gics must be the GICS sector whose id is {sid}")
        if not s.get("name"):
            out.append(f"{sid}: no name")
        for k in [sid, *s.get("tickers", []), *s.get("aliases", [])]:
            k = str(k).lower()
            if k in keys and keys[k] != sid:
                out.append(f"{sid}: '{k}' already names {keys[k]}")
            keys[k] = sid
        shots = s.get("shots", [])
        if kind in ("topic", "sector") and not TARGET <= len(shots) <= TOPIC_TARGET:
            out.append(f"{sid}: {len(shots)} shots ({TARGET} to {TOPIC_TARGET} expected)")
        if kind == "company" and not 1 <= len(shots) <= FAMOUS_TARGET:
            out.append(f"{sid}: {len(shots)} shots (1 to {FAMOUS_TARGET})")
        seen = set()
        for sh in shots:
            if not sh.get("id") or sh["id"] in seen:
                out.append(f"{sid}: missing or repeated shot id {sh.get('id')!r}")
            seen.add(sh.get("id"))
            if not sh.get("q") or not sh.get("scene"):
                out.append(f"{sid}/{sh.get('id')}: needs q and scene")
            if sh.get("orient", "any") not in ("landscape", "portrait", "any"):
                out.append(f"{sid}/{sh.get('id')}: orient must be any, landscape or portrait")
            if any(not str(x).startswith("File:") for x in sh.get("exclude", [])):
                out.append(f"{sid}/{sh.get('id')}: exclude lists 'File:...' titles")
            f = sh.get("focus")
            if f is not None and not (len(f) == 2 and all(0 <= v <= 1 for v in f)):
                out.append(f"{sid}/{sh.get('id')}: focus must be [x, y] between 0 and 1")
    missing = set(SECTORS.values()) - ids
    if missing:
        out.append("missing sector subjects: " + ", ".join(sorted(missing)))
    tick = set()
    for x in extras or []:
        if not x.get("ticker") or not x.get("name") or x.get("sector") not in SECTORS:
            out.append(f"extras: {x.get('ticker')}: needs ticker, name and a GICS sector")
        if x.get("ticker") in tick:
            out.append(f"extras: {x['ticker']} repeated")
        tick.add(x.get("ticker"))
    return out


# ---------- network ----------

def headers():
    """User-Agent, plus a Wikimedia access token from WIKIMEDIA_TOKEN when set: anonymous API calls from shared
    cloud addresses are rate-limited (HTTP 429) almost all the time, while a logged-in account has its own limit."""
    h = {"User-Agent": UA}
    token = os.environ.get("WIKIMEDIA_TOKEN", "").strip()
    if token:
        h["Authorization"] = "Bearer " + token
    return h


def wait_for(e, attempt):
    """Seconds to wait after an HTTP error: the server's Retry-After when it gives one, else a growing pause."""
    try:
        return min(120, max(1, int(e.headers.get("Retry-After"))))
    except (TypeError, ValueError, AttributeError):
        return min(60, 5 * 2 ** attempt)


def get_json(params, url=COMMONS_API, tries=8):
    query = urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
    # 50 long file names make an address too long for the servers (HTTP 414): send those as a form instead
    req = (lambda: urllib.request.Request(url + "?" + query, headers=headers())) if len(query) < 4000 else \
          (lambda: urllib.request.Request(url, data=query.encode(), headers={**headers(), "Content-Type": "application/x-www-form-urlencoded"}))
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req(), timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise
            print(f"  (HTTP {e.code} from {urllib.parse.urlsplit(url).netloc}, waiting {wait_for(e, attempt)} s)", file=sys.stderr)
            time.sleep(wait_for(e, attempt))
        except urllib.error.URLError:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"no answer from {url}: {params}")


def plain(s):
    """HTML from Commons metadata -> plain text."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def no_query(url):
    return (url or "").split("?", 1)[0]


def candidate(page):
    ii = page["imageinfo"][0]
    md = {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (ii.get("extmetadata") or {}).items()}
    y = re.search(r"\b(1[89]\d\d|20\d\d)\b", plain(str(md.get("DateTimeOriginal", ""))))
    return {"file": page["title"], "w": ii.get("width", 0), "h": ii.get("height", 0), "mime": ii.get("mime", ""),
            "orig": no_query(ii.get("url", "")),  # the API adds ?utm_source=... tracking to its addresses
            "page": no_query(ii.get("descriptionurl")) or "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(page["title"].replace(" ", "_")),
            "licence": plain(md.get("LicenseShortName")), "licence_code": (md.get("License") or "").lower(),
            "licence_url": md.get("LicenseUrl") or "", "author": plain(md.get("Artist")) or plain(md.get("Credit")),
            "year": int(y.group(1)) if y else None,
            "categories": [c for c in (md.get("Categories") or "").split("|") if c],
            "restrictions": [r for r in (md.get("Restrictions") or "").split("|") if r],
            "description": plain(md.get("ImageDescription"))[:300]}


class Live:
    """Wikipedia, Wikidata and Commons over the network: the build's only contact with the outside. Answers are
    kept for a while, so the build can look up the next subjects ahead (workers) while it picks the current one's
    photos: at most 1 + workers requests at a time."""

    def __init__(self, pause=0.05, workers=2, keep=3000, stock_sources=None):
        self.pause, self.workers, self.keep = pause, workers, keep
        self.cache, self.lock = OrderedDict(), threading.Lock()
        self.stock = stock.sources() if stock_sources is None else stock_sources  # Unsplash, Pexels: with their keys

    def track(self, photo):
        """Tell the stock source a photo was chosen (Unsplash asks for it): False when it could not be told now."""
        if not photo.get("track"):
            return True
        for st in self.stock:
            if st.name == photo.get("provider"):
                return st.track(photo["track"]) is not False
        return False  # its source is not available in this run: the count stays pending

    def _get(self, url, params):
        key = url + "?" + json.dumps(params, sort_keys=True)
        with self.lock:
            fut, mine = self.cache.get(key), False
            if fut is None:
                fut, mine = Future(), True
                self.cache[key] = fut
                while len(self.cache) > self.keep:
                    self.cache.popitem(last=False)
        if mine:
            try:
                fut.set_result(get_json(params, url))
            except Exception as e:
                with self.lock:
                    self.cache.pop(key, None)
                fut.set_exception(e)
            time.sleep(self.pause)
        return fut.result()

    def sp500(self):
        d = self._get(ENWIKI_API, {"action": "parse", "page": "List of S&P 500 companies", "prop": "wikitext", "redirects": 1})
        wt = d["parse"]["wikitext"]
        return parse_sp500(wt["*"] if isinstance(wt, dict) else wt)

    def wikidata_ids(self, titles):
        """{Wikipedia title: Wikidata id or None}, following redirects."""
        out = {}
        for i in range(0, len(titles), 50):
            batch = titles[i:i + 50]
            q = self._get(ENWIKI_API, {"action": "query", "titles": "|".join(batch), "prop": "pageprops",
                                       "ppprop": "wikibase_item", "redirects": 1}).get("query", {})
            alias = {r["from"]: r["to"] for k in ("normalized", "redirects") for r in q.get(k, [])}
            final = {p["title"]: p.get("pageprops", {}).get("wikibase_item") for p in q.get("pages", [])}
            for t in batch:
                f = t
                for _ in range(3):
                    f = alias.get(f, f)
                out[t] = final.get(f)
        return out

    def entities(self, qids, props="labels|claims|sitelinks"):
        out = {}
        qids = [q for q in dict.fromkeys(qids) if q]
        for i in range(0, len(qids), 50):
            d = self._get(WIKIDATA_API, {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]), "props": props,
                                         "languages": "en|mul", "sitefilter": "commonswiki"})
            out.update(d.get("entities", {}))
        return out

    def company_categories(self, names):
        """{name: Commons category} for the names that are a Commons category (hard redirects followed, soft
        'Category redirect' pages left out) filed under a category of companies, brands, banks...: the last way
        to find a company's category when Wikidata does not give it ('Circle' is a category of geometry)."""
        out = {}
        names = list(dict.fromkeys(n for n in names if n))
        for i in range(0, len(names), 50):
            batch = names[i:i + 50]
            q = self._get(COMMONS_API, {"action": "query", "titles": "|".join("Category:" + n for n in batch), "redirects": 1,
                                        "prop": "categoryinfo|categories|templates", "cllimit": "max", "clshow": "!hidden",
                                        "tltemplates": "Template:Category redirect", "tllimit": "max"}).get("query", {})
            alias = {r["from"]: r["to"] for k in ("normalized", "redirects") for r in q.get(k, [])}
            pages = {p["title"]: p for p in q.get("pages", [])}
            for n in batch:
                t = "Category:" + n
                for _ in range(3):
                    t = alias.get(t, t)
                pg = pages.get(t, {})
                info = pg.get("categoryinfo") or {}
                parents = " ".join(c["title"] for c in pg.get("categories", []))
                if (not pg.get("missing") and not pg.get("templates") and info.get("files", 0) + info.get("subcats", 0) > 0
                        and COMPANY_PARENT.search(parents)):
                    out[n] = t.split(":", 1)[1]
        return out

    def articles(self, titles):
        """{title: Wikidata id of the article it leads to ('disambiguation' for a disambiguation page, None when
        there is no article)}."""
        out = {}
        titles = list(dict.fromkeys(t for t in titles if t))
        for i in range(0, len(titles), 50):
            batch = titles[i:i + 50]
            q = self._get(ENWIKI_API, {"action": "query", "titles": "|".join(batch), "prop": "pageprops",
                                       "ppprop": "wikibase_item|disambiguation", "redirects": 1}).get("query", {})
            alias = {r["from"]: r["to"] for k in ("normalized", "redirects") for r in q.get(k, [])}
            pages = {p["title"]: p for p in q.get("pages", [])}
            for t in batch:
                f = t
                for _ in range(3):
                    f = alias.get(f, f)
                pp = pages.get(f, {}).get("pageprops", {})
                out[t] = "disambiguation" if "disambiguation" in pp else pp.get("wikibase_item")
        return out

    def search_entity(self, name, ticker):
        """The Wikidata id of the company with that name listed under that ticker, or None."""
        d = self._get(WIKIDATA_API, {"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": 7})
        ids = [x["id"] for x in d.get("search", [])]
        ents = self.entities(ids) if ids else {}
        return next((q for q in ids if has_ticker(ents.get(q, {}), ticker)), None)

    def search(self, q, limit=30):
        """Commons files for a full-text search, most relevant first."""
        d = self._get(COMMONS_API, {"action": "query", "generator": "search", "gsrsearch": f"{q} filetype:bitmap",
                                    "gsrnamespace": 6, "gsrlimit": limit, **IMAGEINFO})
        pages = sorted(d.get("query", {}).get("pages", []), key=lambda p: p.get("index", 1e9))
        return [candidate(p) for p in pages if p.get("imageinfo")]

    def info(self, titles):
        """{file title: candidate} for Commons files (missing files left out)."""
        out = {}
        titles = list(dict.fromkeys(titles))
        for i in range(0, len(titles), 50):
            params = {"action": "query", "titles": "|".join(titles[i:i + 50]), **IMAGEINFO}
            pages, extra = {}, {}
            while True:
                d = self._get(COMMONS_API, {**params, **extra})
                for p in d.get("query", {}).get("pages", []):
                    if p.get("imageinfo") or p["title"] not in pages:
                        pages[p["title"]] = p
                if "continue" not in d:
                    break
                extra = d["continue"]
            out.update({t: candidate(p) for t, p in pages.items() if p.get("imageinfo")})
        return out

    def category_files(self, cat, keys=(), depth=2, max_cats=15, top=80, per_cat=30):
        """[(file title, category)] in a Commons category and its subcategories, breadth first, skipping
        logo, map, document... categories, events and sponsorships, and (when keys are given) subcategories whose
        name does not name the company: a company's category also leads to the firms it owns, the races it
        sponsors and the bands in its song catalogue."""
        seen, queue, out = set(), [(cat, 0)], []
        while queue and len(seen) < max_cats:
            c, d = queue.pop(0)
            if c in seen:
                continue
            seen.add(c)
            r = self._get(COMMONS_API, {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + c,
                                        "cmtype": "file|subcat", "cmlimit": 500})
            files, subs = [], []
            for m in r.get("query", {}).get("categorymembers", []):
                name = m["title"].split(":", 1)[-1]
                if (m.get("ns") == 14 and d < depth and not SKIP_CATEGORY.search(name) and not EVENTS.search(name)
                        and (not keys or any(has_term(name.lower(), k) for k in keys) or (d == 0 and BUSINESS.search(name)))):
                    subs.append(name)
                elif m.get("ns") == 6 and re.search(r"\.(jpe?g|png)$", name, re.I):
                    files.append(m["title"])
            out += [(f, c) for f in files[: top if d == 0 else per_cat]]
            queue += [(s, d + 1) for s in subs]
        return out


# ---------- the companies ----------

def parse_sp500(wt):
    """Wikitext of 'List of S&P 500 companies' -> [{ticker, name, wiki, sector}] (first table: the constituents)."""
    start = wt.find('id="constituents"')
    start = wt.rfind("{|", 0, start) if start >= 0 else wt.find("{|")
    end = wt.find("\n|}", start)
    out = []
    for row in wt[start:end].split("\n|-")[1:]:
        row = row.strip()
        if not row or row.startswith("!"):
            continue
        # cells start a line with "|" or "||" (both in use on the page) or follow "||" on the same line
        cells = [c.strip() for c in re.split(r"\n\|\|?(?!\})|\|\|", "\n" + row) if c.strip()]
        if len(cells) < 3:
            continue
        m = re.search(r"\{\{[^{}|]*\|\s*([A-Za-z][A-Za-z.\-]*)\s*\}\}", cells[0])  # {{NyseSymbol|MMM}}, {{BZX link|CBOE}}
        sym = m.group(1) if m else re.sub(r"\[\[[^\]|]*\||[\[\]{}]", "", cells[0]).strip()
        link = re.search(r"\[\[([^\]|#]+)(?:\|([^\]]*))?\]\]", cells[1])
        if not sym or not link:
            continue
        sector = plain(re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", cells[2])).strip("| ")
        out.append({"ticker": sym.upper().replace(".", "-"), "name": (link.group(2) or link.group(1)).strip(),
                    "wiki": link.group(1).strip(), "sector": sector})
    return out


def claims(ent, p):
    return [s for s in ent.get("claims", {}).get(p, []) if s.get("rank") != "deprecated"]


def claim_value(ent, p):
    for s in sorted(claims(ent, p), key=lambda s: s.get("rank") != "preferred"):
        v = s.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, str):
            return v
    return None


def start_of(s):
    """Start time (P580) of a statement as '+2024-10-17T00:00:00Z' ('' when unknown): sorts by date."""
    for q in s.get("qualifiers", {}).get("P580", []):
        v = q.get("datavalue", {}).get("value", {})
        if isinstance(v, dict) and v.get("time"):
            return v["time"]
    return ""


def current_item(ent, p):
    """The item of a statement still in force (no end time), preferred first, then the latest start: e.g. the
    current CEO."""
    cur = [s for s in claims(ent, p) if "P582" not in s.get("qualifiers", {})]
    cur = sorted(cur, key=start_of, reverse=True)
    for s in sorted(cur, key=lambda s: s.get("rank") != "preferred"):
        v = s.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(v, dict) and v.get("id"):
            return v["id"]
    return None


def commons_category(ent):
    """The Commons category of a Wikidata item: its P373, else its Commons sitelink when that is a category."""
    c = claim_value(ent, "P373")
    if c:
        return c
    t = ent.get("sitelinks", {}).get("commonswiki", {}).get("title", "")
    return t.split(":", 1)[1] if t.startswith("Category:") else None


def linked(ent):
    """Items an item is tied to as owner, maker, parent, operator, developer, product or subsidiary."""
    return {s.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            for p in ("P127", "P176", "P749", "P137", "P178", "P1056", "P355", "P1830", "P123")
            for s in claims(ent, p) if isinstance(s.get("mainsnak", {}).get("datavalue", {}).get("value"), dict)}


def label(ent):
    """English label, else the multilingual one ('mul', which Wikidata now uses for many people's names)."""
    labels = ent.get("labels", {})
    return (labels.get("en") or labels.get("mul") or {}).get("value")


def has_ticker(ent, ticker):
    t = ticker.upper().replace("-", ".")
    return any(str(q.get("datavalue", {}).get("value", "")).upper().replace("-", ".") == t
               for s in claims(ent, "P414") for q in s.get("qualifiers", {}).get("P249", []))


def load_universe(bank=BANK):
    p = Path(bank) / "universe.json"
    return json.loads(p.read_text(encoding="utf-8")).get("companies", []) if p.exists() else []


def curated_for(cat, tickers):
    """The catalog's hand-written company sharing a ticker with these, or None."""
    t = set(tickers)
    return next((s for s in cat["subjects"] if s["kind"] == "company" and t & {s["id"], *s.get("tickers", [])}), None)


def build_universe(cat=None, src=None, bank=BANK, extras=None, log=print):
    """bank/universe.json: every company of the bank with its Wikidata id, Commons category, CEO and main image."""
    cat = cat or load_catalog()
    src = src or Live()
    extras = load_extras() if extras is None else extras
    merged = {}
    for r in src.sp500():
        e = merged.setdefault(r["wiki"], {"name": re.sub(r"\s*\((?:Class|Series) [A-Z]\)", "", r["name"]), "tickers": [],
                                          "sector": r["sector"], "wiki": r["wiki"], "source": "S&P 500"})
        e["tickers"].append(r["ticker"])
    if len(merged) < 400:
        raise RuntimeError(f"only {len(merged)} S&P 500 companies read from Wikipedia: its table format may have changed")
    have = {t for e in merged.values() for t in e["tickers"]}
    for x in extras:
        if x["ticker"] not in have:
            merged[x.get("wiki") or x["name"]] = {"name": x["name"], "tickers": [x["ticker"]], "sector": x["sector"],
                                                   "wiki": x.get("wiki"), "source": "extra"}
            have.add(x["ticker"])
    comps = list(merged.values())
    for s in cat["subjects"]:
        if s["kind"] == "company" and not ({s["id"], *s.get("tickers", [])} & have):
            comps.append({"name": s["name"], "tickers": s.get("tickers") or [s["id"]], "sector": None, "wiki": None, "source": "catalog"})
    log(f"  {len(comps)} companies; finding their Wikidata records")
    qids = src.wikidata_ids([e["wiki"] for e in comps if e.get("wiki")])
    for e in comps:
        e["wikidata"] = qids.get(e.get("wiki")) or src.search_entity(e["name"], e["tickers"][0])
    ents = src.entities([e["wikidata"] for e in comps])
    ceo, topic = {}, {}
    for e in comps:
        ent = ents.get(e["wikidata"] or "", {})
        e["commons_category"] = commons_category(ent)
        e["image"] = claim_value(ent, "P18")
        if current_item(ent, "P169"):
            ceo[e["wikidata"]] = current_item(ent, "P169")
        if not e["commons_category"] and current_item(ent, "P910"):
            topic[e["wikidata"]] = current_item(ent, "P910")
    cats = src.entities(list(topic.values()), props="claims|sitelinks")  # the company's main category (P910)
    for e in comps:
        if not e["commons_category"] and topic.get(e["wikidata"]):
            e["commons_category"] = commons_category(cats.get(topic[e["wikidata"]], {}))
    guess = {e["name"]: [e.get("wiki"), e["name"]] for e in comps if not e["commons_category"]}
    found = src.company_categories([n for g in guess.values() for n in g])
    for e in comps:
        if not e["commons_category"]:
            e["commons_category"] = next((found[n] for n in guess[e["name"]] if n in found), None)
    names = src.entities(list(ceo.values()), props="labels|claims")
    # a short name whose Wikipedia article is something else ('Blackstone', 'Target', 'Ball') is searched in full
    art = src.articles([short_name(e["name"]) for e in comps])
    other = src.entities([a for a in art.values() if a and a != "disambiguation"], props="claims")
    for e in comps:
        a = art.get(short_name(e["name"]))
        own = a == e["wikidata"] or e["wikidata"] in linked(other.get(a, {})) or a in linked(ents.get(e["wikidata"] or "", {}))
        e["ambiguous"] = bool(a) and not own  # the article is the company, or its brand or product ('Netflix', 'Coca-Cola')
    old = {e["id"]: e for e in load_universe(bank)}
    out = []
    for e in comps:
        boss = names.get(ceo.get(e["wikidata"]), {}) if ceo.get(e["wikidata"]) else {}
        e["ceo"], e["ceo_image"] = label(boss), claim_value(boss, "P18")
        cur = curated_for(cat, e["tickers"])
        e["id"] = cur["id"] if cur else e["tickers"][0]
        o, man = old.get(e["id"], {}), old.get(e["id"], {}).get("manual")
        if man is True:
            out.append(o)
            continue
        if man:
            e.update({f: o[f] for f in man if f in o}, manual=man)
        out.append(e)
    out.sort(key=lambda e: e["name"].lower())
    Path(bank).mkdir(parents=True, exist_ok=True)
    (Path(bank) / "universe.json").write_text(json.dumps({"updated": date.today().isoformat(), "companies": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"  universe.json: {len(out)} companies, {sum(1 for e in out if e.get('commons_category'))} with a Commons category, "
        f"{sum(1 for e in out if not e.get('wikidata'))} without a Wikidata record")
    return out


# ---------- choosing photos ----------

def provider_of(p):
    """Where a photo comes from: 'commons', 'unsplash' or 'pexels'."""
    return p.get("provider") or ("commons" if p["file"].startswith("File:") else p["file"].split(":", 1)[0])


def licence_kind(c):
    """'cc0', 'pd', 'by', 'by-sa', 'unsplash' or 'pexels'; None for licences not used (GFDL only, FAL, unknown,
    non-free)."""
    code, short = c.get("licence_code", ""), c.get("licence", "").lower()
    if code in ("unsplash", "pexels", "pixabay"):
        return code
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


def has_term(hay, term):
    """Whether a lower-case text holds a term at the start of a word ('gold pour' in 'gold pouring'); a short
    term (3M, GE) must be a whole word ('3m' is not in 'TEX,22-CAST,3M-' nor in '3mm')."""
    t = re.escape(term.lower())
    if len(term) <= 3:  # nor inside a model code: 'Fokker F.VIIb-3m', missile '3M-54E'
        return bool(re.search(r"(?<![a-z0-9.\-])" + t + r"(?![a-z0-9]|-[a-z0-9])", hay))
    return bool(re.search(r"(?<![a-z0-9])" + t, hay))


def score(c, rank, shot, used=(), no_sa=False, exclude=()):
    """Ranking score of a candidate for a shot, or None when it cannot be used."""
    if c["file"] in used or c["file"] in exclude or c["file"] in shot.get("exclude", ()) or c["mime"] not in MIMES or not c.get("orig"):
        return None
    if len(c["file"].encode()) > 160:  # Commons shortens long names in thumbnail addresses
        return None
    if c.get("provider") in STOCK and STOCK_BAD.search(c.get("description", "")):  # renders, illustrations, quotes
        return None
    kind = licence_kind(c)
    if kind is None or (no_sa and kind == "by-sa"):
        return None
    w, h = c["w"], c["h"]
    lo, sh = MIN_PERSON if shot.get("person") else (MIN_LONG, MIN_SHORT)
    if not w or not h or max(w, h) < lo or min(w, h) < sh or bad_name(c["file"], shot.get("allow", ())):
        return None
    if not shot.get("historic") and OLD_PAPER.search(" ".join(c["categories"])):  # letters, paintings, survey drawings
        return None
    if SCREENS.search(" ".join(c["categories"])):  # screenshots named like photos ('HTTP 1009 error - Access denied')
        return None
    if not shot.get("historic") and c.get("year") and c["year"] < 1960:  # wartime banknotes for 'yen banknotes'
        return None
    must = shot.get("must") or ([shot["q"].strip('"').lower()] if shot.get("person") and shot.get("q") else None)  # a person: their name
    if must:
        hay = (c["file"] + " " + " ".join(c["categories"])).lower().replace("_", " ")
        if not any(has_term(hay, m) for m in must):
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


def stock_match(c, shot, q):
    """Whether a stock photo's description holds the shot's 'must' words, else every word of the search
    ('gold bars' needs gold and bar or bars): stock searches return loosely related photos."""
    hay = c.get("description", "").lower()
    if shot.get("must"):
        return any(has_term(hay, m) for m in shot["must"])
    words = [w for w in re.findall(r"[a-z0-9]+", q.lower()) if w not in GENERIC_WORDS and len(w) > 1]
    stems = [re.sub(r"(?<=[a-z]{3})(es|s)$", "", w) for w in words]
    return bool(words) and all(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?:s|es)?(?![a-z0-9])", hay) for w in stems)


def choose(shot, search_fn, used=(), no_sa=False, exclude=(), stock_sources=(), enough=3):
    """Acceptable candidates for a shot, best first: [(score, candidate, query)], from the stock sources (when
    given; never for real people) and Commons. The fallback queries are tried only while fewer than enough photos
    qualify (three; more when a topic takes several photos per shot), and their results rank lower."""
    seen, out = set(), []
    fns = [] if shot.get("person") else [(st.search, True) for st in stock_sources]
    for i, q in enumerate([shot["q"], *shot.get("alt", [])]):
        for fn, is_stock in [*fns, (search_fn, False)]:
            for rank, c in enumerate(fn(q)):
                if c["file"] in seen:
                    continue
                seen.add(c["file"])
                if is_stock and not stock_match(c, shot, q):
                    continue
                s = score(c, rank, shot, used, no_sa, exclude)
                if s is not None:
                    out.append((s - 8 * i + (STOCK_BONUS if is_stock else 0), c, q))
        if len(out) >= enough:
            break
    return sorted(out, key=lambda x: -x[0])


def thumb(orig, width):
    """Address of a standard-width Commons thumbnail of a file (its original address when it is not on Commons)."""
    m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons/)([0-9a-f]/[0-9a-f]{2}/)([^/]+)$", orig or "")
    return f"{m.group(1)}thumb/{m.group(2)}{m.group(3)}/{width}px-{m.group(3)}" if m else orig


def links(c):
    """(photo address, preview address, [width, height] of the linked photo): the narrowest standard width that
    still gives a 4:5 slide its 1500 px of height, else the widest, else the original."""
    if c.get("provider") in STOCK:
        return stock.links(c, SLIDE_H, PREVIEW_W)
    w, h = c["w"], c["h"]
    width = next((x for x in WIDTHS if x < w and x * h / w >= SLIDE_H), WIDTHS[-1] if w > WIDTHS[-1] else w)
    url = thumb(c["orig"], width) if width < w else c["orig"]
    return url, thumb(c["orig"], PREVIEW_W) if w > PREVIEW_W else c["orig"], [width, round(width * h / w)]


def clean_title(title):
    t = re.sub(r"\.\w+$", "", title.split(":", 1)[-1]).replace("_", " ")
    t = re.sub(r"\b(?:IMG|DSC|DSCF|DSCN|PXL|MVIMG|P\d{6,})[\w-]*", " ", t, flags=re.I)
    t = re.sub(r"\b\d{4}[-.]\d{2}[-.]\d{2}\b|\b\d{5,}\b|\(\d+\)|\bcropped\b|\(\s*\)", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" -,.")


def describe(c, fallback):
    """What a photo shows, from its file name, else its English description, else the fallback."""
    if c.get("provider") in STOCK:
        a = c.get("alt", "").strip()
        return a[:1].upper() + a[1:160] if len(re.findall(r"[A-Za-z]{3,}", a)) >= 2 else fallback
    t = clean_title(c["file"])
    if len(re.findall(r"[A-Za-z]{3,}", t)) >= 2:
        return t
    d = c.get("description", "")
    return d[:160] if len(re.findall(r"[A-Za-z]{3,}", d)) >= 3 else fallback


def stem(title):
    """Near-duplicate key: the first words of the file name without numbers ('Apple Park 03' = 'Apple Park 07')."""
    words = re.findall(r"[a-z]+", clean_title(title).lower())
    return " ".join(words[:4])


def credit_line(c):
    if c.get("provider") == "flickr":
        return f"Photo by {c.get('author') or 'unknown'} on Flickr, {c.get('licence')}"
    if c.get("provider") == "nasa":
        return f"Photo: {c.get('author') or 'NASA'}, public domain"
    if c.get("provider") in STOCK:
        return f"Photo by {c.get('author') or 'unknown'} on {c['provider'].capitalize()}"
    author = c.get("author") or "Unknown author"
    lic = "public domain" if licence_kind(c) == "pd" else c.get("licence") or "free licence"
    return f"{author}, {lic}, via Wikimedia Commons"


def photo(c, shot, shows, how, focus, person=False, category=None):
    url, preview, size = links(c)
    e = {"shot": shot, "shows": shows, "file": c["file"], "page": c["page"], "url": url, "preview": preview, "size": size,
         "focus": list(focus), "credit": credit_line(c), "licence": c["licence"], "licence_kind": licence_kind(c),
         "licence_url": c["licence_url"], "author": c["author"], "year": c["year"], "how": how}
    if c.get("provider") in STOCK:
        e.update(provider=c["provider"], author_url=c.get("author_url", ""))
        if c.get("track"):
            e["track"] = c["track"]
        if c.get("via"):
            e["via"] = c["via"]
    if c.get("low_res"):
        e["low_res"] = True  # under 1500 px: a plain photo only (never a cover)
    if person:
        e["person"] = True
    if category:
        e["category"] = category
    if c["restrictions"]:
        e["flags"] = ["restrictions: " + ", ".join(c["restrictions"])]
    return e


def telling(cand, c):
    """Whether a photo from a company's Commons category says what it shows: a file name of words (not
    'P20210825AS-1824' or 'IMG_0412'), or a description naming the company. Categories also hold photos of
    events and visitors that would pass for the company's own."""
    t = clean_title(cand["file"])
    if len(re.findall(r"[A-Za-z]{3,}", t)) >= 2:
        return True
    hay = (t + " " + cand.get("description", "")).lower()
    return any(k and re.search(r"(?<!\w)" + re.escape(k.lower()) + r"(?!\w)", hay)
               for k in (short_name(c["name"]), c["name"], c.get("commons_category")))


def names_company(cand, keys):
    """Whether a photo's file name, categories or description name the company (a CEO found by search: the
    'David Joyner' at a building site is not CVS's)."""
    hay = " ".join([cand["file"], *cand["categories"], cand.get("description", "")]).lower().replace("_", " ")
    return any(has_term(hay, k) for k in keys)


def about(cand, shot, keys):
    """A hand-written company shot's hit: it names the company, or every word of the search that found it
    ('iPhone 16 Pro', 'server rack'), so 'Eli Lilly laboratory' does not bring another drugmaker's lab."""
    if shot.get("must") or names_company(cand, keys):
        return True
    hay = " ".join([cand["file"], *cand["categories"], cand.get("description", "")]).lower().replace("_", " ")
    words = [w for w in re.findall(r"[a-z0-9]+", shot["q"].lower()) if w not in GENERIC_WORDS and len(w) > 1]
    return all(has_term(hay, w) for w in words)


def own_place(cand, keys, strict=None, core=None):
    """A search hit that is a company's own place or thing: its file name names a building, store, plant,
    product... and the company: in full (strict names), by a name that is not ambiguous (keys), or by its first
    word ('Abbott Hangzhou Factory') when its categories or description then name the company in full
    ('Elm Street, East Blackstone MA' and 'Blackstone Building, Fort Wayne' are not Blackstone's)."""
    strict = keys if strict is None else strict
    t = clean_title(cand["file"]).lower()
    if not BUSINESS.search(t):
        return False
    if any(has_term(t, k) for k in strict):
        return True
    rest = " ".join([*cand["categories"], cand.get("description", "")]).lower().replace("_", " ")
    confirmed = any(has_term(rest, k) for k in strict)
    if any(has_term(t, k) for k in keys):
        return keys == strict or confirmed
    return bool(core) and has_term(t, core) and confirmed


def short_name(name):
    words = [w for w in re.sub(r"\(.*?\)", " ", name).split() if w.lower().strip(",.") not in GENERIC_WORDS]
    return " ".join(words).strip(" ,.") or name


def company_photos(c, curated, src, used, no_sa=False, exclude=(), target=TARGET):
    """Up to target photos of one company (see the module's docstring for the order)."""
    name, short = c["name"], short_name(c["name"])
    keys = [k for k in dict.fromkeys([short, name, c.get("commons_category"), *c.get("aliases", [])]) if k]
    # inside the company's own category its short name is enough; in a search 'Blackstone' alone is also a town,
    # a building and a river, so an ambiguous name must be found in full
    strict = ([k for k in keys if k != short] or [name]) if c.get("ambiguous") else keys
    first = short.split()[0].strip(",.")
    core = first if len(first) >= 4 and first.lower() not in GENERIC_WORDS and first != short else None
    picks, stems = [], set()

    def take(cand, shot, shows, how, person=False, category=None, focus=None):
        f = focus or (PERSON_FOCUS if person else (0.5, 0.5))
        picks.append(photo(cand, shot, shows, how, f, person, category))
        used.add(cand["file"])
        stems.add(stem(cand["file"]))

    def fresh(cand):
        return cand["file"] not in used and stem(cand["file"]) not in stems

    for sh in curated:
        if len(picks) >= target:
            break
        r = [x for x in choose(sh, src.search, used, no_sa, exclude) if fresh(x[1]) and (sh.get("person") or about(x[1], sh, keys))]
        if r:
            take(r[0][1], sh["id"], describe(r[0][1], sh["scene"]), "catalog", sh.get("person"), focus=sh.get("focus"))
    if c.get("image") and len(picks) < target:
        t = "File:" + c["image"]
        cand = src.info([t]).get(t)
        if cand and fresh(cand) and score(cand, 0, {"id": "main"}, used, no_sa, exclude) is not None:
            take(cand, "main", describe(cand, name), "Wikidata main image")
    if c.get("ceo") and len(picks) < target and not any(p["shot"] == "leader" for p in picks):
        # the person's own image on Wikidata; else a search whose file names or categories give the full name
        # ('William M. Brown', not a painter called William Mason Brown)
        t = "File:" + c["ceo_image"] if c.get("ceo_image") else None
        cand = src.info([t]).get(t) if t else None
        if not (cand and fresh(cand) and score(cand, 0, {"id": "leader", "person": True}, used, no_sa, exclude) is not None):
            r = [x for x in choose({"id": "leader", "q": f'"{c["ceo"]}"', "person": True, "must": [c["ceo"].lower()]},
                                   src.search, used, no_sa, exclude) if fresh(x[1]) and names_company(x[1], strict)]
            cand = r[0][1] if r else None
        if cand:
            take(cand, "leader", f"{c['ceo']}, {name} CEO (per Wikidata)", "Wikidata CEO", person=True)
    if c.get("commons_category") and len(picks) < target:
        # inside its own category, 'Hilton Hotels & Resorts' and 'Wynn Las Vegas' are Hilton Worldwide's and Wynn Resorts'
        files = src.category_files(c["commons_category"], keys + ([core] if core else []))
        infos = src.info([f for f, _ in files])
        ranked = []
        for f, where in files:
            cand = infos.get(f)
            ok = cand and cand["mime"] == "image/jpeg" and telling(cand, c) and not EVENTS.search(" ".join(cand["categories"]))
            s = score(cand, 0, {"id": "category"}, used, no_sa, exclude) if ok else None
            if s is not None:
                ranked.append((s - (0 if where == c["commons_category"] else 3), cand, where))
        ranked.sort(key=lambda x: -x[0])
    else:
        ranked = []
    per = {}

    def from_category(upto):
        for _, cand, where in ranked:
            if len(picks) >= upto:
                break
            if (where != c["commons_category"] and per.get(where, 0) >= 2) or not fresh(cand):  # two per subcategory
                continue
            per[where] = per.get(where, 0) + 1
            take(cand, f"c{len(picks) + 1}", describe(cand, f"{name} ({where})"), "Commons category", category=where)

    per_term = 3 * max(1, target // TARGET)  # photos taken from one search ('Nike store'): 3, or 9 for a 30-photo company
    from_category(target - max(SEARCH_ROOM, target // 3))  # leave room for its headquarters, stores, factories... found by search
    for what in ("headquarters", "store", "factory", "office", "building", ""):
        if len(picks) >= target:
            break
        n = 0
        term = f'"{name}"' if c.get("ambiguous") else short
        for _, cand, _ in choose({"id": "search", "q": f"{term} {what}".strip(), "must": strict}, src.search, used, no_sa, exclude):
            if len(picks) >= target or n >= per_term:
                break
            # PNGs found this way are mostly renders, screenshots and scans: photos are JPEG
            if fresh(cand) and cand["mime"] == "image/jpeg" and own_place(cand, keys, strict, core) and not EVENTS.search(" ".join(cand["categories"])):
                take(cand, f"s{len(picks) + 1}", describe(cand, f"{name} {what}".strip()), "Commons search")
                n += 1
    from_category(target)
    return picks


def flat(t):
    """Lower case, hyphens and underscores as spaces: 'Coca-Cola' and 'coca cola' meet."""
    return re.sub(r"[-_]+", " ", (t or "").lower())


def brand_keys(c, brands=()):
    """Names a stock photo must give to count as the company's: its brands and products, its full name and
    Commons category, and its short name unless that is ambiguous ('Apple' is also a fruit)."""
    short = short_name(c["name"])
    keys = [*brands, c["name"], c.get("commons_category"), *([] if c.get("ambiguous") else [short])]
    return [k for k in dict.fromkeys(flat(k) for k in keys if k) if len(k) >= 2]


def brand_photos(c, brands, src, used, n, exclude=(), n_queries=BRAND_QUERIES):
    """Up to n Unsplash and Pexels photos whose description names the company or one of its brands, best
    first, at most two by the same photographer (one shoot is many near-identical photos). Only for companies
    listed in brands.json: a stock search for 'Ametek' or 'Aon' finds nothing of theirs."""
    stock_sources = getattr(src, "stock", ())
    if n <= 0 or not stock_sources or not brands:  # only companies with consumer brands (brands.json)
        return []
    keys = brand_keys(c, brands)
    queries = list(dict.fromkeys(brands[:n_queries]))
    found, seen = [], set()
    for qi, q in enumerate(queries):
        for st in stock_sources:
            for rank, cand in enumerate(st.search(q)):
                if cand["file"] in seen:
                    continue
                seen.add(cand["file"])
                if not any(has_term(flat(cand.get("description")), k) for k in keys):
                    continue
                s = score(cand, rank, {"id": "brand"}, used, False, exclude)
                if s is not None:
                    found.append((s - 4 * qi, cand, q))
    picks, per_author = [], {}
    for _, cand, q in sorted(found, key=lambda x: -x[0]):
        if len(picks) >= n:
            break
        a = cand.get("author") or cand["file"]
        if per_author.get(a, 0) >= 2:
            continue
        per_author[a] = per_author.get(a, 0) + 1
        picks.append(photo(cand, f"b{len(picks) + 1}", describe(cand, f"{c['name']} ({q})"), f"{cand['provider']} search: {q}", (0.5, 0.5)))
        used.add(cand["file"])
    return picks


def shot_photos(s, src, used, no_sa=False, exclude=(), target=None):
    """The photos of a topic or sector: (photos, ids of shots without a photo). Its target (50) is shared out
    over its hand-written shots: the best photo of each shot first, then the second best of each, and so on, at
    most three stock photos by the same photographer and none twice from one shoot (same file stem). After the
    first round a Commons photo needs a quality mark (featured, quality or valued image): only about 7% of the
    others pass the review."""
    target = target or s.get("target") or TOPIC_TARGET
    per_shot = -(-target // max(1, len(s["shots"])))
    ranked = []
    for sh in s["shots"]:
        ranked.append((sh, [c for _, c, _ in choose(sh, src.search, used, no_sa, exclude, getattr(src, "stock", ()),
                                                     enough=2 * per_shot)]))
    picks, per_author, stems, taken = [], {}, set(), {}
    for rnd in range(per_shot * 3):  # later rounds let a shot with photos to spare cover one that ran dry
        for sh, cands in ranked:
            if len(picks) >= target or taken.get(sh["id"], 0) > rnd:
                continue
            for c in cands:
                a = c.get("author") if c.get("provider") in STOCK else None  # one Unsplash shoot: many look-alikes
                if c["file"] in used or stem(c["file"]) in stems or (a and per_author.get(a, 0) >= 3):
                    continue
                if rnd and c.get("provider") not in STOCK and not QUALITY.search(" ".join(c["categories"])):
                    continue
                focus = sh.get("focus") or (PERSON_FOCUS if sh.get("person") else (0.5, 0.5))
                picks.append(photo(c, sh["id"], describe(c, sh["scene"]), "catalog", focus, sh.get("person")))
                used.add(c["file"])
                stems.add(stem(c["file"]))
                per_author[a] = per_author.get(a, 0) + 1
                taken[sh["id"]] = taken.get(sh["id"], 0) + 1
                break
    return picks, [sh["id"] for sh, _ in ranked if not taken.get(sh["id"])]


# ---------- build ----------

def load_manifest(bank=BANK):
    p = Path(bank) / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def write_atomic(path, text):
    """Write a file whole or not at all: a build cut mid-write must not leave half a manifest."""
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def load_review(bank=BANK):
    """bank/review.json: the grade (3 best, 2 plain, 1 reject) of each Commons photo checked by eye. Without
    the file nothing is gated (min_grade 0)."""
    p = Path(bank) / "review.json"
    rv = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"min_grade": 0}
    rv.setdefault("grades", {})
    return rv


def save_review(rv, bank=BANK):
    rv = {"about": "Grades of the photos checked by eye (review.py): 3 best, 2 usable but plain, 1 reject. Commons "
                   "photos graded min_grade or more reach the index, and a company's Commons photos graded 2 fill the "
                   "places its better photos leave free (marked plain). Unsplash and Pexels photos are published "
                   "unless graded below min_grade. The build never picks a photo graded below min_grade again.",
          "min_grade": rv.get("min_grade") or 3, **{k: v for k, v in rv.items() if k not in ("about", "min_grade")}}
    rv["grades"] = dict(sorted(rv["grades"].items()))
    write_atomic(Path(bank) / "review.json", json.dumps(rv, indent=1, ensure_ascii=False))


def published(p, rv):
    """Whether a photo reaches the chat: Commons photos with a grade of min_grade or more (any while there is no
    review); Unsplash and Pexels photos unless they were graded below it."""
    if not rv.get("min_grade"):
        return True
    g = rv["grades"].get(p["file"])
    if provider_of(p) != "commons":
        return g is None or g >= rv["min_grade"]
    return (g or 0) >= rv["min_grade"]


def reserve(p, rv):
    """Whether a photo is a plain one held in reserve: graded RESERVE_GRADE (right subject, ordinary photo) and
    from Commons or too small for a full slide (low_res: Flickr photos found through Openverse)."""
    return (bool(rv.get("min_grade")) and (provider_of(p) == "commons" or bool(p.get("low_res")))
            and rv["grades"].get(p["file"]) == RESERVE_GRADE)


def is_plain(p, rv):
    """Whether the chat gets a photo as plain (prefer others, never a cover): a reserve photo or a low_res one."""
    return reserve(p, rv) or bool(p.get("low_res"))


def target_of(e):
    """How many photos a subject should have: 'target' in its manifest entry (30 for a well-known company), else
    50 for a topic or sector and 10 for a company."""
    return e.get("target") or (TOPIC_TARGET if e.get("kind") in ("topic", "sector") else TARGET)


def published_photos(e, rv):
    """The photos of a subject that reach the chat, at most its target: the published ones (Commons first, they
    are in that order), then, for a company with places left, its plain ones (reserve)."""
    t = target_of(e)
    out = [p for p in e.get("photos", []) if published(p, rv)][:t]
    if e.get("kind") == "company" and len(out) < t:
        out += [p for p in e.get("photos", []) if reserve(p, rv)][:t - len(out)]
    return out


def save_manifest(m, order, bank=BANK):
    rank = {k: i for i, k in enumerate(order)}
    m = dict(sorted(m.items(), key=lambda kv: rank.get(kv[0], 1e9)))
    write_atomic(Path(bank) / "manifest.json", json.dumps(m, indent=1, ensure_ascii=False))


def subjects_of(cat, uni, brands=None):
    """Every subject of the bank in build order: companies (from the universe), then sectors, then topics."""
    brands = load_brands() if brands is None else brands
    out = []
    for c in uni:
        cur = curated_for(cat, c["tickers"])
        out.append({"id": c["id"], "kind": "company", "name": c["name"], "tickers": c["tickers"],
                    "aliases": (cur or {}).get("aliases", []), "sector": SECTORS.get(c.get("sector")),
                    "company": c, "shots": (cur or {}).get("shots", []), "target": FAMOUS_TARGET if cur else TARGET,
                    "brands": next((brands[t] for t in [c["id"], *c["tickers"]] if t in brands), [])})
    out += [{**s, "target": TOPIC_TARGET} for k in ("sector", "topic") for s in cat["subjects"] if s["kind"] == k]
    return out


def matches(s, keys):
    return bool(keys & {str(x).lower() for x in [s["id"], *s.get("tickers", []), *s.get("aliases", [])]})


def pick(s, src, used, no_sa=False, exclude=(), rv=None, keep=None):
    """The photos of a subject: (photos, ids of hand-written shots without a photo). A company gets its Commons
    photos, then brand photos from Unsplash and Pexels for the places its approved Commons photos leave free.
    With keep (a list of photos), its Commons photos are those and Commons is not searched again."""
    t = s.get("target") or (TARGET if s["kind"] == "company" else TOPIC_TARGET)
    if s["kind"] == "company":
        commons = keep if keep is not None else company_photos(s["company"], s["shots"], src, used, no_sa, exclude, t)
        rv = rv or {"min_grade": 0, "grades": {}}
        approved = sum(1 for p in commons if published(p, rv))
        return commons + brand_photos(s["company"], s.get("brands", []), src, used, t - approved, exclude,
                                      BRAND_QUERIES * max(1, t // TARGET)), []
    return shot_photos(s, src, used, no_sa, exclude, t)


def look_ahead(s, src, used, no_sa, exclude, rv=None, keep=None):
    """A dry run of a subject's photo picking (thrown away) that fills src's cache with the answers the real run
    will ask for."""
    try:
        pick(s, src, used, no_sa, exclude, rv, keep)
    except Exception:
        pass


def send_pending_tracks(m, src, log=print):
    """Send the download counts a build could not send when it chose the photos (Unsplash's counter was at its
    hourly limit), stopping at the first refusal. Returns how many are still pending."""
    track, refused, left = getattr(src, "track", None), False, 0
    for e in m.values():
        for p in e.get("photos", []):
            if not p.get("track_pending"):
                continue
            if track and not refused and track(p) is not False:
                p.pop("track_pending")
            else:
                refused, left = True, left + 1
    if left:
        log(f"  {left} Unsplash download counts still pending: the next build sends them")
    return left


def build(catalog=None, bank=BANK, src=None, only=None, redo=False, no_sa=False, kinds=("company", "topic", "sector"), log=print,
          save_every=5, stock_only=False, brands=None, commons_only=False):
    """Pick the photos of every subject due (all with redo or only). stock_only: companies keep their approved
    Commons photos and only their Unsplash/Pexels brand photos are picked again (no Commons search, nothing new
    to review)."""
    cat = catalog if isinstance(catalog, dict) else load_catalog(catalog)
    live = src is None
    src = src or Live()
    if live and not src.stock and not commons_only and ({"topic", "sector"} & set(kinds) or stock_only):
        raise SystemExit("No stock source answers (Unsplash, Pexels): topics, sectors and brand photos would get "
                         "Commons photos only. Check the key or network secret, or pass --commons-only.")
    bank = Path(bank)
    bank.mkdir(parents=True, exist_ok=True)
    uni = load_universe(bank)
    if "company" in kinds and not uni:
        raise SystemExit("No companies yet: run `python image_bank.py universe` first.")
    subjects = subjects_of(cat, uni, brands)
    keys = {k.strip().lower() for k in only.split(",")} if only else None
    todo = [s for s in subjects if s["kind"] in kinds and (keys is None or matches(s, keys))]
    if keys and not todo:
        raise ValueError(f"no subject matches {only}")
    m = load_manifest(bank)
    if any(p.get("track_pending") for e in m.values() for p in e.get("photos", [])):
        send_pending_tracks(m, src, log)  # first too: a build cut by a time limit never reaches its end
    used = {p["file"] for e in m.values() for p in e.get("photos", [])}
    rv = load_review(bank)
    graded_out = {f for f, g in rv["grades"].items() if g < rv.get("min_grade", 0)}

    def due(s):
        old = m.get(s["id"], {})
        return not (old.get("manual") is True or (old.get("checked") and not (redo or keys)))

    def excluded(s):
        old = m.get(s["id"], {})
        return graded_out | (set(old.get("exclude", [])) if "exclude" in (old.get("manual") or []) else set())

    def kept(s):
        """With stock_only, a company's approved Commons photos (kept as they are)."""
        if not (stock_only and s["kind"] == "company"):
            return None
        return [p for p in m.get(s["id"], {}).get("photos", []) if provider_of(p) == "commons" and published(p, rv)]

    work = [s for s in todo if due(s)]
    ahead = ThreadPoolExecutor(src.workers) if getattr(src, "workers", 0) else None
    sent = 0
    for n, s in enumerate(todo, 1):
        if not due(s):
            continue
        if ahead:  # look up the next few subjects while this one is picked
            k = work.index(s)
            while sent < min(len(work), k + 1 + 2 * src.workers):
                if sent > k:
                    ahead.submit(look_ahead, work[sent], src, set(used), no_sa, excluded(work[sent]), rv, kept(work[sent]))
                sent += 1
        old = m.get(s["id"], {})
        man = old.get("manual") or []
        fixed = {f: old[f] for f in man if f in old}
        exclude = graded_out | set(fixed.get("exclude", []))
        for p in old.get("photos", []):
            used.discard(p["file"])
        e = {"name": s["name"], "kind": s["kind"], "tickers": s.get("tickers", []), "aliases": s.get("aliases", []),
             "target": s.get("target") or (TARGET if s["kind"] == "company" else TOPIC_TARGET)}
        if s["kind"] == "company":
            e["sector"] = s.get("sector")
        try:
            keep = kept(s)
            # photos found by hand (review round of hand searches) are never dropped by a rebuild
            hand = [p for p in old.get("photos", []) if p.get("how") == HAND and published(p, rv)]
            used.update(p["file"] for p in [*(keep or []), *hand])
            e["photos"], missing = pick(s, src, used, no_sa, exclude, rv, keep)
            have = {p["file"] for p in e["photos"]}
            e["photos"] = [p for p in hand if p["file"] not in have] + e["photos"]
            if s["kind"] == "company":  # its plain photos stay as a reserve (never picked again, never dropped)
                have = {p["file"] for p in e["photos"]}
                plain = [p for p in old.get("photos", []) if reserve(p, rv) and p["file"] not in have]
                e["photos"] += plain
                used.update(p["file"] for p in plain)
            if missing:
                e["missing"] = missing
            e["checked"] = date.today().isoformat()
            before = {p["file"] for p in old.get("photos", []) if not p.get("track_pending")}
            for p in e["photos"]:  # a new stock photo: tell its source (now, or in a later build)
                if p.get("track") and p["file"] not in before and hasattr(src, "track") and src.track(p) is False:
                    p["track_pending"] = True
        except Exception as ex:  # one failing subject must not stop the build; the next run retries it
            note = f"{type(ex).__name__}: {ex}"[:300]
            e = {**old, "error": note} if old.get("photos") else {**e, "photos": [], "error": note}
            e.pop("checked", None)
            used.update(p["file"] for p in e["photos"])
        if man:
            e.update(fixed, manual=man)
        m[s["id"]] = e
        log(f"  {n}/{len(todo)} {s['id']:12s} {len(e['photos']):2d} photos {e.get('error', '')}")
        # stock answers cost an hourly quota: save every subject that has stock photos, so a cut build keeps them
        if n % save_every == 0 or any(provider_of(p) in STOCK for p in e["photos"]):
            save_manifest(m, [x["id"] for x in subjects], bank)
    send_pending_tracks(m, src, log)
    save_manifest(m, [x["id"] for x in subjects], bank)
    if ahead:
        ahead.shutdown(wait=False, cancel_futures=True)
    return m


# ---------- outputs ----------

def safe(sid):
    return re.sub(r"[^A-Za-z0-9._-]", "_", sid)


def index(bank=BANK, base_url=BASE_URL):
    """bank/index.json (every subject, its photo count and the address of its file) and bank/subjects/<ID>.json
    (its photos): what the carousel chat reads."""
    bank = Path(bank)
    m, rv = load_manifest(bank), load_review(bank)
    base = base_url.rstrip("/") + "/"
    sub = bank / "subjects"
    sub.mkdir(parents=True, exist_ok=True)
    for f in sub.glob("*.json"):
        f.unlink()
    entries, total = [], 0
    keep = ("shows", "url", "preview", "size", "focus", "person", "credit", "licence", "author_url", "low_res")
    for sid, e in m.items():
        photos = [{**{k: p[k] for k in keep if k in p}, "provider": provider_of(p), "source": p["page"],
                    **({"plain": True} if is_plain(p, rv) else {})} for p in published_photos(e, rv)]
        total += len(photos)
        rec = {"id": sid, "kind": e["kind"], "name": e["name"], "tickers": e.get("tickers", []), "aliases": e.get("aliases", []),
               "photos": len(photos), "target": target_of(e), "file": f"{base}subjects/{safe(sid)}.json"}
        if e["kind"] == "company" and e.get("sector"):
            rec["sector"] = e["sector"]
            if len(photos) < target_of(e):
                rec["fill_from"] = e["sector"]
        entries.append(rec)
        body = {k: rec[k] for k in ("id", "kind", "name", "tickers", "sector", "target", "fill_from") if k in rec}
        (sub / f"{safe(sid)}.json").write_text(json.dumps({**body, "photos": photos}, indent=1, ensure_ascii=False), encoding="utf-8")
    out = {"about": "InvestIQ image bank for carousels: freely licensed photos of S&P 500 and well-known US-listed companies "
                    "(Wikimedia Commons, only the best, checked by eye), market topics and GICS sectors (Unsplash, "
                    "Pexels and Wikimedia Commons).",
           "rules": RULES, "updated": date.today().isoformat(), "photos": total, "subjects": entries}
    write_atomic(bank / "index.json", json.dumps(out, indent=1, ensure_ascii=False))
    return total


def credits(bank=BANK):
    """bank/CREDITS.md and bank/credits.csv: author, licence and source of every photo."""
    bank = Path(bank)
    m, rv = load_manifest(bank), load_review(bank)
    md = ["# Image credits", "", "Photos from Wikimedia Commons, Unsplash and Pexels, linked from there. Credit them as shown: "
          "CC BY and CC BY-SA ask for it; public-domain, CC0, Unsplash and Pexels photos do not, but crediting is good "
          "practice and the Unsplash and Pexels guidelines ask for it.", ""]
    n = 0
    with open(bank / "credits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["subject", "shot", "credit", "author", "licence", "licence_url", "source", "url"])
        for sid, e in m.items():
            photos = published_photos(e, rv)
            if not photos:
                continue
            md += [f"## {e['name']} ({sid})", ""]
            for p in photos:
                md.append(f"- {p['shows']}: {p['credit']}. [{p['file'].split(':', 1)[-1]}]({p['page']})")
                w.writerow([sid, p["shot"], p["credit"], p.get("author", ""), p.get("licence", ""), p.get("licence_url", ""), p["page"], p["url"]])
                n += 1
            md.append("")
    (bank / "CREDITS.md").write_text("\n".join(md), encoding="utf-8")
    return n


def prompts(cat=None, bank=BANK, all_shots=False):
    """bank/prompts.jsonl: an AI image prompt for each topic, sector or hand-written company shot without a photo
    (every one with --all). Shots of real people are left out: their likeness is never generated."""
    cat = cat or load_catalog()
    m, rv = load_manifest(bank), load_review(bank)
    lines = []
    for s in cat["subjects"]:
        done = {p["shot"] for p in published_photos(m.get(s["id"], {}), rv)}
        for sh in s["shots"]:
            if sh.get("person") or (sh["id"] in done and not all_shots):
                continue
            lines.append(json.dumps({"id": f"{s['id']}/{sh['id']}", "subject": s["name"], "prompt": f"{sh['scene']}. {cat['style']}",
                                     "negative": cat.get("negative", ""), "aspect": "4:5"}, ensure_ascii=False))
    Path(bank).mkdir(parents=True, exist_ok=True)
    (Path(bank) / "prompts.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def lookup(key, bank=BANK):
    """The photos of a subject (id, ticker or alias): [{shows, url, credit}]."""
    k, rv = key.lower(), load_review(bank)
    for sid, e in load_manifest(bank).items():
        if k in [str(x).lower() for x in [sid, *e.get("tickers", []), *e.get("aliases", [])]]:
            return [{"shows": p["shows"], "url": p["url"], "credit": p["credit"]} for p in published_photos(e, rv)]
    return []


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("universe", "build", "index", "credits", "prompts", "list", "check"):
        sys.exit(__doc__)
    arg = lambda name: a[a.index(name) + 1] if name in a and a.index(name) + 1 < len(a) else None
    if a[0] == "check":
        raw = json.loads(CATALOG.read_text(encoding="utf-8"))
        p = check_catalog(raw, load_extras())
        ids = {t for e in load_universe() for t in [e["id"], *e["tickers"]]}
        p += [f"brands.json: {t} is not a company of the bank" for t in load_brands() if ids and t not in ids]
        print("\n".join(p) or f"catalog OK: {len(raw['subjects'])} subjects, {sum(len(s['shots']) for s in raw['subjects'])} "
                               f"hand-written shots; extras OK: {len(load_extras())} companies; brands OK: {len(load_brands())} companies")
        sys.exit(1 if p else 0)
    if a[0] == "list":
        if len(a) < 2:
            sys.exit("python image_bank.py list <id, ticker or alias>")
        for r in lookup(a[1]):
            print(f"{r['url']}\t{r['shows']}\t{r['credit']}")
        sys.exit()
    if a[0] == "universe":
        build_universe()
        sys.exit()
    if a[0] == "build":
        kinds = tuple((arg("--kind") or "company,topic,sector").split(","))
        build(only=arg("--only"), redo="--redo" in a or "--stock-only" in a, no_sa="--no-sa" in a, kinds=kinds,
              stock_only="--stock-only" in a, commons_only="--commons-only" in a)
    if a[0] in ("build", "index"):
        print(f"index.json: {index(base_url=arg('--base-url') or BASE_URL)} photos")
    if a[0] in ("build", "credits"):
        print(f"credits: {credits()} photos")
    if a[0] in ("build", "prompts"):
        print(f"prompts: {prompts(all_shots='--all' in a)} shots")
