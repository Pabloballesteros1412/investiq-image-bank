"""
Unsplash and Pexels: better-looking photos for the bank's topics and sectors (generic scenes: a trading floor,
gold bars, a refinery), next to the Wikimedia Commons photos of real companies.

Needs each API's key, in one of two ways: in the environment (UNSPLASH_ACCESS_KEY, PEXELS_API_KEY), or as a
network secret of the cloud environment that the egress proxy adds to every request to the API's host
(api.unsplash.com: header Authorization, prefix "Client-ID"; api.pexels.com: header Authorization, no prefix).
Without either, the source is skipped. Also needs network access to api.unsplash.com, images.unsplash.com,
api.pexels.com and images.pexels.com. Answers are
kept in .cache/stock/ (not in Git) for 30 days, so a rebuild costs no requests. When a source's hourly limit
is reached (Unsplash: 50 requests an hour for a new app, 1,000 once Unsplash approves it for production;
Pexels: 200 an hour) the build waits until it resets. Unsplash counts each endpoint on its own (searches and
download counts have separate hourly limits, seen 5 Nov 2026), and the build never waits for a download count:
one it cannot send is kept as pending and sent by a later build.

Licences: Unsplash License (https://unsplash.com/license) and Pexels License (https://www.pexels.com/license/):
free for commercial use without permission; crediting the photographer is asked by both APIs' guidelines.
Not allowed: selling the photos unaltered or building a competing photo service with them. Unsplash+
photos are not under the free licence and are left out. Unsplash's guidelines also ask to hotlink its image
addresses (the bank does) and to tell its API when a photo is chosen (the build does: `track`).
"""
import hashlib, html, json, os, re, threading, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache" / "stock"
TTL = 30 * 86400
UA = "InvestIQ-image-bank/2.0 (https://getinvestiq.com; carousel image bank)"
UTM = "utm_source=investiq_image_bank&utm_medium=referral"
PER_PAGE = 30
_lock = threading.Lock()


class RateLimited(RuntimeError):
    """An API's hourly limit is used up (raised at once when the caller does not want to wait for it)."""


def fetch(url, headers, cache=True, log=print, tries=6, wait=True):
    """JSON from a stock API (cached on disk); waits out rate limits (raises RateLimited instead when not wait)
    and server hiccups."""
    path = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if cache and path.exists() and time.time() - path.stat().st_mtime < TTL:
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(tries):
        try:
            with _lock:  # one request at a time per process: both APIs count requests per hour
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, **headers}), timeout=60) as r:
                    data = json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            limited = e.code == 429 or (e.code == 403 and "rate limit" in body.lower())
            if limited and not wait:
                raise RateLimited(f"{urllib.parse.urlsplit(url).netloc}: hourly limit reached")
            if limited:
                reset = e.headers.get("X-Ratelimit-Reset")
                wait = max(60, int(reset) - int(time.time())) if reset and reset.isdigit() else 15 * 60
                log(f"  ({urllib.parse.urlsplit(url).netloc}: hourly limit reached, waiting {wait // 60} min)")
                time.sleep(min(wait, 3700))
                continue
            if e.code in (500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"{urllib.parse.urlsplit(url).netloc}: HTTP {e.code} {body}") from None
        except urllib.error.URLError:
            if attempt == tries - 1:
                raise
            time.sleep(10 * (attempt + 1))
            continue
        if cache:
            CACHE.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, path)
        return data
    raise RuntimeError(f"no answer from {url}")


def words_of_url(url):
    """'https://www.pexels.com/photo/gold-bars-on-black-surface-12345/' -> 'gold bars on black surface'."""
    slug = urllib.parse.urlsplit(url or "").path.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"-?\d+$", "", slug).replace("-", " ")


class Unsplash:
    name = "unsplash"
    probe = "https://api.unsplash.com/photos?per_page=1"

    def __init__(self, key=None, log=print):
        self.key, self.log = key, log
        # no key: the proxy adds it (network secret)
        self.headers = {"Accept-Version": "v1", **({"Authorization": "Client-ID " + key} if key else {})}

    def search(self, q):
        url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(
            {"query": q, "per_page": PER_PAGE, "content_filter": "high"})
        d = fetch(url, self.headers, log=self.log)
        return [c for c in (self.candidate(r) for r in d.get("results", [])) if c]

    @staticmethod
    def candidate(r):
        raw = (r.get("urls") or {}).get("raw", "")
        if r.get("premium") or r.get("plus") or "plus.unsplash.com" in raw or not raw:
            return None  # Unsplash+ is not under the free licence
        user = r.get("user") or {}
        alt = r.get("alt_description") or r.get("description") or ""
        tags = " ".join(t.get("title", "") for t in r.get("tags") or [])
        return {"file": "unsplash:" + r["id"], "provider": "unsplash", "w": r.get("width", 0), "h": r.get("height", 0),
                "mime": "image/jpeg", "orig": raw, "page": r["links"]["html"] + "?" + UTM,
                "licence": "Unsplash License", "licence_code": "unsplash", "licence_url": "https://unsplash.com/license",
                "author": user.get("name") or user.get("username") or "", "author_url": ((user.get("links") or {}).get("html", "") + "?" + UTM),
                "year": int(r["created_at"][:4]) if r.get("created_at") else None, "categories": [], "restrictions": [],
                "alt": alt[:200], "description": " ".join([alt, r.get("description") or "", tags])[:400],
                "track": (r.get("links") or {}).get("download_location")}

    def track(self, url):
        """Tell Unsplash a photo was chosen (its API guidelines ask for it). Never waits: False when it could not
        be told now (its download counter's hourly limit is used up, or the API failed), so it is sent later."""
        try:
            fetch(url, self.headers, cache=False, log=self.log, tries=2, wait=False)
            return True
        except Exception:  # a missed count must not stop the build
            return False


class Pexels:
    name = "pexels"
    probe = "https://api.pexels.com/v1/curated?per_page=1"

    def __init__(self, key=None, log=print):
        self.key, self.log = key, log
        self.headers = {"Authorization": key} if key else {}  # no key: the proxy adds it (network secret)

    def search(self, q):
        url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "per_page": PER_PAGE})
        d = fetch(url, self.headers, log=self.log)
        return [self.candidate(p) for p in d.get("photos", []) if (p.get("src") or {}).get("original")]

    @staticmethod
    def candidate(p):
        alt = p.get("alt") or words_of_url(p.get("url"))
        return {"file": f"pexels:{p['id']}", "provider": "pexels", "w": p.get("width", 0), "h": p.get("height", 0),
                "mime": "image/jpeg", "orig": p["src"]["original"], "page": p.get("url", ""),
                "licence": "Pexels License", "licence_code": "pexels", "licence_url": "https://www.pexels.com/license/",
                "author": p.get("photographer", ""), "author_url": p.get("photographer_url", ""), "year": None,
                "categories": [], "restrictions": [], "alt": alt[:200],
                "description": " ".join([alt, words_of_url(p.get("url"))])[:400]}

    def track(self, url):
        return True  # Pexels asks for no download count


class Flickr:
    """Flickr photos under licences that allow commercial use and cropping (CC BY, CC BY-SA, CC0, public domain
    mark, US government works): never NC or ND. Needs FLICKR_API_KEY (the key goes in the query, so the egress
    proxy cannot add it). Flickr asks to link each photo back to its page, which the bank does ('page')."""
    name = "flickr"
    API = "https://api.flickr.com/services/rest/"

    def __init__(self, key=None, log=print):
        self.key, self.log, self.headers, self._lic = key, log, {}, None

    def _call(self, method, cache=True, **params):
        url = self.API + "?" + urllib.parse.urlencode({"method": method, "api_key": self.key, "format": "json",
                                                       "nojsoncallback": 1, **params})
        d = fetch(url, self.headers, cache=cache, log=self.log)
        if d.get("stat") != "ok":
            raise RuntimeError(f"flickr: {d.get('message') or d}")
        return d

    def licences(self):
        """{licence id: (name, code)} of the licences the bank can use, read from Flickr itself."""
        if self._lic is None:
            self._lic = {}
            for l in self._call("flickr.photos.licenses.getInfo")["licenses"]["license"]:
                u, nm = (l.get("url") or "").lower(), l.get("name", "")
                if "-nc" in u or "-nd" in u or "noncommercial" in nm.lower() or "noderivs" in nm.lower():
                    continue
                v = re.search(r"/(\d\.\d)/", u)
                v = v.group(1) if v else ""
                code = ("cc-by-sa-" + v if "/by-sa/" in u else "cc-by-" + v if "/by/" in u else
                        "cc0" if "zero" in u else "pdm" if "publicdomain/mark" in u else
                        "pd-usgov" if "usgov" in u or "government" in nm.lower() else None)
                if code:
                    self._lic[str(l["id"])] = (nm, code, l.get("url") or "")
        return self._lic

    def search(self, q):
        lic = self.licences()
        d = self._call("flickr.photos.search", text=q, license=",".join(lic), content_type=1, media="photos",
                       safe_search=1, sort="relevance", per_page=PER_PAGE,
                       extras="url_k,url_h,url_z,owner_name,license,tags,description,date_taken")
        return [c for c in (self.candidate(p, lic) for p in d.get("photos", {}).get("photo", [])) if c]

    @staticmethod
    def candidate(p, lic):
        if str(p.get("license")) not in lic:
            return None
        big = next(((p[f"url_{k}"], int(p[f"width_{k}"]), int(p[f"height_{k}"])) for k in ("k", "h")
                     if p.get(f"url_{k}")), None)
        if not big:
            return None  # only 1024 px or less: too small for a full slide
        name, code, lurl = lic[str(p["license"])]
        title = p.get("title") or ""
        desc = re.sub(r"<[^>]+>", " ", (p.get("description") or {}).get("_content", ""))
        y = re.match(r"(\d{4})", p.get("datetaken") or "")
        return {"file": f"flickr:{p['id']}", "provider": "flickr", "w": big[1], "h": big[2], "mime": "image/jpeg",
                "orig": big[0], "big": big[0], "small": p.get("url_z") or big[0],
                "page": f"https://www.flickr.com/photos/{p['owner']}/{p['id']}",
                "licence": name, "licence_code": code, "licence_url": lurl,
                "author": p.get("ownername") or p["owner"], "author_url": f"https://www.flickr.com/people/{p['owner']}",
                "year": int(y.group(1)) if y else None, "categories": [], "restrictions": [],
                "alt": title[:200], "description": " ".join([title, desc, p.get("tags") or ""])[:400]}

    def track(self, url):
        return True  # Flickr asks for no download count


class Nasa:
    """NASA's image library: public domain (NASA does not claim copyright; its logos and identifiable people may
    not imply endorsement). No key. Searched only for space subjects: rockets, satellites, the ISS, the Earth seen
    from orbit."""
    name = "nasa"
    SPACE = re.compile(r"\b(space|rocket|launch|satellite|orbit|astronaut|nasa|iss|mars|moon|lunar|telescope|"
                       r"spacecraft|earth from|starship|falcon|shuttle)\b", re.I)

    THIRD = re.compile(r"spacex|rocket ?lab|\bula\b|united launch|boeing|northrop|lockheed|blue origin|\besa\b|jaxa|"
                       r"roscosmos|axiom|sierra space|firefly|relativity|virgin|getty|reuters|\bap\b|associated press", re.I)

    def __init__(self, key=None, log=print):
        self.log, self.headers = log, {}

    def search(self, q):
        if not self.SPACE.search(q):
            return []
        url = "https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": q, "media_type": "image", "page_size": PER_PAGE})
        items = fetch(url, self.headers, log=self.log).get("collection", {}).get("items", [])
        out = []
        for it in items:
            d = (it.get("data") or [{}])[0]
            nid = d.get("nasa_id")
            if not nid:
                continue
            try:
                meta = fetch(f"https://images-assets.nasa.gov/image/{urllib.parse.quote(nid)}/metadata.json", self.headers, log=self.log)
            except Exception:
                continue
            out.append(self.candidate(d, meta))
        return [c for c in out if c]

    @staticmethod
    def candidate(d, meta):
        w, h = int(meta.get("File:ImageWidth") or 0), int(meta.get("File:ImageHeight") or 0)
        if not w or not h:
            return None
        k = min(1.0, 1920 / max(w, h))  # '~large' is the original scaled to 1920 px on its long side
        nid = d["nasa_id"]
        base = f"https://images-assets.nasa.gov/image/{urllib.parse.quote(nid)}/{urllib.parse.quote(nid)}"
        who = d.get("photographer") or d.get("secondary_creator") or ""
        # the library also holds launch providers' and partner agencies' photos: those are theirs, not public domain
        credit = re.search(r"(?:photo|image) credit:?\s*([^.;\n]+)", d.get("description") or "", re.I)
        if Nasa.THIRD.search(" ".join([who, d.get("secondary_creator") or ""])) or (credit and "nasa" not in credit.group(1).lower()):
            return None
        y = re.match(r"(\d{4})", d.get("date_created") or "")
        title = d.get("title") or ""
        return {"file": f"nasa:{nid}", "provider": "nasa", "w": round(w * k), "h": round(h * k), "mime": "image/jpeg",
                "orig": base + "~large.jpg", "big": base + "~large.jpg", "small": base + "~medium.jpg",
                "page": f"https://images.nasa.gov/details/{urllib.parse.quote(nid)}",
                "licence": "Public domain (NASA)", "licence_code": "pd-nasa",
                "licence_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
                "author": who if who.upper().startswith("NASA") else ("NASA/" + who) if who else "NASA",
                "author_url": "https://images.nasa.gov",
                "year": int(y.group(1)) if y else None, "categories": [], "restrictions": [],
                "alt": title[:200], "description": " ".join([title, d.get("description") or "", " ".join(d.get("keywords") or [])])[:400]}

    def track(self, url):
        return True


class Openverse:
    """Openverse (the open media search run by WordPress): Flickr photos under licences that allow commercial use
    and cropping (CC BY, CC BY-SA, CC0, public domain mark; never NC or ND), with no Flickr key. Pablo chose it on
    12 Nov 2026 for companies Commons and Unsplash leave thin. Flickr's sizes above 1024 px need a secret only
    its own API gives, so these photos are 1024 px at most: they carry low_res, the bank uses them only as plain
    photos (never a cover), and the chat is told to use them small. No key: 20 searches a minute and 200 a day
    from one address; answers are cached like the other sources."""
    name = "openverse"
    API = "https://api.openverse.org/v1/images/"

    def __init__(self, log=print):
        self.log, self.headers = log, {}

    def search(self, q, page_size=20, wait=False):
        url = self.API + "?" + urllib.parse.urlencode({"q": q, "license_type": "commercial,modification",
                                                       "source": "flickr", "page_size": page_size, "mature": "false"})
        d = fetch(url, self.headers, log=self.log, wait=wait)
        return [c for c in (self.candidate(r) for r in d.get("results", [])) if c]

    @staticmethod
    def candidate(r):
        lic, ver = (r.get("license") or "").lower(), (r.get("license_version") or "").strip()
        if lic in ("by", "by-sa"):
            code, name = f"cc-{lic}-{ver}".rstrip("-"), f"CC {lic.upper()} {ver}".strip()
        elif lic in ("cc0", "pdm"):
            code, name = lic, "CC0" if lic == "cc0" else "Public Domain Mark"
        else:
            return None  # NC, ND or anything else
        page = r.get("foreign_landing_url") or ""
        m = re.search(r"flickr\.com/photos/([^/]+)/(\d+)", page)
        w, h, url = int(r.get("width") or 0), int(r.get("height") or 0), r.get("url") or ""
        if not m or max(w, h) < 1000 or not url.lower().endswith(".jpg"):
            return None  # not a Flickr photo page, or Flickr's 500 px size
        title = r.get("title") or ""
        tags = " ".join(t.get("name", "") for t in r.get("tags") or [])
        return {"file": f"flickr:{m.group(2)}", "provider": "flickr", "via": "openverse", "w": w, "h": h,
                "mime": "image/jpeg", "orig": url, "big": url, "small": re.sub(r"_b\.jpg$", "_z.jpg", url), "page": page,
                "licence": name, "licence_code": code, "licence_url": r.get("license_url") or "",
                "author": r.get("creator") or m.group(1),
                "author_url": r.get("creator_url") or f"https://www.flickr.com/people/{m.group(1)}",
                "year": None, "categories": [], "restrictions": [], "alt": title[:200],
                "description": f"{title} {tags}"[:400], **({"low_res": True} if max(w, h) < 1500 else {})}

    def track(self, url):
        return True  # no download count


def _throttle(url, gap):
    """Wait before a request that is not in the cache, so free APIs without keys are asked gently."""
    path = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".json")
    if not (path.exists() and time.time() - path.stat().st_mtime < TTL):
        time.sleep(gap)


class LoC:
    """The Library of Congress's Carol M. Highsmith Archive: about 100,000 photos of the United States (cities,
    buildings, factories, ports, farms, stores) that Highsmith gave to the public ('No known restrictions on
    publication'). Pablo asked on 13 Nov 2026 for photos without copyright from anywhere on the web; this is one
    of the few large sets whose rights are clear. No key. Older scans are served at full size through IIIF (asked
    at the width a slide needs); newer ones only at 1024 px, which only companies take (as low_res)."""
    name = "loc"
    API = "https://www.loc.gov/photos/"
    CONTRIBUTOR = "highsmith, carol m."

    def __init__(self, log=print, low_res=False):
        self.log, self.headers, self.low_res = log, {}, low_res

    def search(self, q):
        url = self.API + "?" + urllib.parse.urlencode({"q": q, "fa": f"contributor:{self.CONTRIBUTOR}", "fo": "json",
                                                       "c": PER_PAGE})
        _throttle(url, 1.5)
        d = fetch(url, self.headers, log=self.log)
        out = (self.candidate(r) for r in d.get("results", []))
        return [c for c in out if c and (self.low_res or not c.get("low_res"))]

    @staticmethod
    def candidate(r, slide_h=1500, preview_w=500, max_w=2400):
        if LoC.CONTRIBUTOR not in [x.lower() for x in r.get("contributor") or []]:
            return None
        rights = r.get("rights_advisory") or (r.get("item") or {}).get("rights_advisory") or ""
        rights = " ".join(rights) if isinstance(rights, list) else rights
        if "no known restrictions" not in rights.lower():
            return None
        imgs = r.get("image_url") or []
        m = re.search(r"#h=(\d+)&w=(\d+)", imgs[-1]) if imgs else None
        iiif = next((u.split("/full/")[0] for u in imgs if "/image-services/iiif/" in u), None)
        item = (r.get("id") or "").replace("http://", "https://")
        num = re.search(r"/item/(\w+)/", item)
        if not m or not num:
            return None
        h, w = int(m.group(1)), int(m.group(2))
        pct = re.search(r"/full/pct:(\d+)/", imgs[-1])
        if iiif and not re.search(r"\d[a-z]$", iiif) and pct:
            w, h = w * 100 // int(pct.group(1)), h * 100 // int(pct.group(1))  # the scan's full size
            width = int(min(w, max_w, max(1200, -(-slide_h * w // h))))
            big, small, size, low = (f"{iiif}/full/{width},/0/default.jpg", f"{iiif}/full/{preview_w},/0/default.jpg",
                                     [width, round(width * h / w)], False)
        else:
            v = next((u.split("#")[0] for u in imgs if re.search(r"v\.jpg", u)), None)
            if not v:
                return None
            big, small, size, low = v, v.replace("v.jpg", "r.jpg"), [w, h], True
        if max(size) < 1000:
            return None
        title = r.get("title") or ""
        subjects = " ".join(r.get("subject") or [])
        y = re.match(r"(\d{4})", r.get("date") or "")
        return {"file": f"loc:{num.group(1)}", "provider": "loc", "w": size[0], "h": size[1], "mime": "image/jpeg",
                "orig": big, "big": big, "small": small, "page": item,
                "licence": "Public domain (Carol M. Highsmith Archive, Library of Congress)", "licence_code": "pd",
                "licence_url": "https://www.loc.gov/rr/print/res/482_high.html",
                "author": "Carol M. Highsmith", "author_url": "https://www.loc.gov/collections/carol-m-highsmith/",
                "year": int(y.group(1)) if y else None, "categories": [], "restrictions": [], "alt": title[:200],
                "description": f"{title} {subjects}"[:400], **({"low_res": True} if low else {})}

    def track(self, url):
        return True  # no download count


class WordPress:
    """The WordPress.org Photo Directory: photos given to the public domain (CC0) by their photographers and checked
    by WordPress volunteers before they are listed (Pablo, 13 Nov 2026: photos without copyright). No key.
    Served at full size (pd.w.org) and at 2048 px."""
    name = "wordpress"
    API = "https://wordpress.org/photos/wp-json/wp/v2/photos"

    def __init__(self, log=print):
        self.log, self.headers = log, {}

    def search(self, q):
        url = self.API + "?" + urllib.parse.urlencode({"search": q, "per_page": PER_PAGE, "_embed": 1})
        _throttle(url, 1.0)
        d = fetch(url, self.headers, log=self.log)
        return [c for c in (self.candidate(r) for r in (d if isinstance(d, list) else [])) if c]

    @staticmethod
    def candidate(r):
        e = r.get("_embedded") or {}
        media = (e.get("wp:featuredmedia") or [{}])[0]
        md = media.get("media_details") or {}
        w, h = int(md.get("width") or 0), int(md.get("height") or 0)
        if media.get("mime_type") != "image/jpeg" or min(w, h) < 1200:
            return None
        sizes = md.get("sizes") or {}
        s2 = sizes.get("2048x2048") or {}
        if s2.get("source_url") and int(s2.get("height") or 0) >= 1500:  # enough for a 4:5 slide: the lighter file
            big, bw, bh = s2["source_url"], int(s2["width"]), int(s2["height"])
        else:
            big, bw, bh = media.get("source_url"), w, h
        small = (sizes.get("medium_large") or sizes.get("large") or {}).get("source_url") or big
        author = (e.get("author") or [{}])[0]
        tags = " ".join(t.get("name", "") for grp in e.get("wp:term") or [] for t in grp or [] if isinstance(t, dict))
        text = html.unescape(re.sub(r"<[^>]+>", " ", (r.get("content") or {}).get("rendered", ""))).strip()
        y = re.match(r"(\d{4})", r.get("date") or "")
        return {"file": f"wordpress:{r['id']}", "provider": "wordpress", "w": int(bw), "h": int(bh), "mime": "image/jpeg",
                "orig": big, "big": big, "small": small, "page": r.get("link") or "",
                "licence": "CC0 1.0", "licence_code": "cc0", "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "author": author.get("name") or "unknown", "author_url": author.get("link") or "",
                "year": int(y.group(1)) if y else None, "categories": [], "restrictions": [], "alt": text[:200],
                "description": f"{text} {tags}"[:400]}

    def track(self, url):
        return True  # no download count


class Pixabay:
    """Pixabay photos (Pixabay Content License: commercial use, no attribution required; the bank credits them
    anyway). Needs PIXABAY_API_KEY. Without full API access Pixabay gives at most 1280 px, too small for a full
    slide, so only photos with a full-HD address count."""
    name = "pixabay"

    def __init__(self, key=None, log=print):
        self.key, self.log, self.headers = key, log, {}

    def search(self, q):
        url = "https://pixabay.com/api/?" + urllib.parse.urlencode({"key": self.key, "q": q, "image_type": "photo",
                                                                    "safesearch": "true", "per_page": PER_PAGE})
        return [c for c in (self.candidate(h) for h in fetch(url, self.headers, log=self.log).get("hits", [])) if c]

    @staticmethod
    def candidate(h):
        big = h.get("fullHDURL") or h.get("imageURL")
        if not big:
            return None
        w, hh = h.get("imageWidth", 0), h.get("imageHeight", 0)
        k = min(1.0, 1920 / max(w, hh, 1)) if h.get("fullHDURL") else 1.0
        tags = h.get("tags") or ""
        return {"file": f"pixabay:{h['id']}", "provider": "pixabay", "w": round(w * k), "h": round(hh * k),
                "mime": "image/jpeg", "orig": big, "big": big, "small": h.get("webformatURL") or big,
                "page": h.get("pageURL", ""), "licence": "Pixabay Content License", "licence_code": "pixabay",
                "licence_url": "https://pixabay.com/service/license-summary/", "author": h.get("user", ""),
                "author_url": f"https://pixabay.com/users/{h.get('user', '')}-{h.get('user_id', '')}/",
                "year": None, "categories": [], "restrictions": [], "alt": tags[:200], "description": tags[:400]}

    def track(self, url):
        return True


def answers_without_key(url, opener=None):
    """Whether an API answers a request that carries no key: the egress proxy adds it (network secret). An answer
    that the hourly limit is used up counts too (it carries X-Ratelimit headers; a missing key gets 401): a build
    started at that moment must not drop the source and pick Commons photos only."""
    try:
        with (opener or urllib.request.urlopen)(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return e.code in (403, 429) and any(k.lower().startswith("x-ratelimit") for k in (e.headers or {}).keys())
    except Exception:
        return False


def sources(log=print, env=None, probe=answers_without_key):
    """The stock sources this environment can use: its key in the environment, else one the proxy adds."""
    env = os.environ if env is None else env
    out = []
    for cls, var in ((Unsplash, "UNSPLASH_ACCESS_KEY"), (Pexels, "PEXELS_API_KEY")):
        key = (env.get(var) or "").strip()
        if key:
            out.append(cls(key, log))
        elif probe(cls.probe):
            out.append(cls(None, log))
    for cls, var in ((Flickr, "FLICKR_API_KEY"), (Pixabay, "PIXABAY_API_KEY")):  # keys in the query: env only
        key = (env.get(var) or "").strip()
        if key:
            out.append(cls(key, log))
    if not env.get("NO_NASA"):  # keyless public-domain and CC0 sources (NO_NASA turns them all off, for tests)
        out += [Nasa(None, log), LoC(log), WordPress(log)]
    return out


def links(c, slide_h=1500, preview_w=500, max_w=2400):
    """(photo address, preview address, [width, height]) for a stock photo: the width that gives a 4:5 slide its
    1500 px of height (at least 1200 px, at most the original), resized by the source's image server."""
    w, h = c["w"], c["h"]
    if c.get("big"):  # sources with fixed sizes (Flickr, NASA, Pixabay)
        return c["big"], c.get("small") or c["big"], [w, h]
    width = int(min(w, max_w, max(1200, -(-slide_h * w // h))))
    if c["provider"] == "unsplash":
        sep = "&" if "?" in c["orig"] else "?"
        make = lambda x: f"{c['orig']}{sep}w={x}&q=80&fm=jpg&fit=max"
    else:
        make = lambda x: f"{c['orig']}?auto=compress&cs=tinysrgb&w={x}"
    return make(width), make(preview_w), [width, round(width * h / w)]
