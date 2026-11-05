"""
Unsplash and Pexels: better-looking photos for the bank's topics and sectors (generic scenes: a trading floor,
gold bars, a refinery), next to the Wikimedia Commons photos of real companies.

Needs UNSPLASH_ACCESS_KEY and/or PEXELS_API_KEY in the environment (a source without its key is skipped) and
network access to api.unsplash.com, images.unsplash.com, api.pexels.com and images.pexels.com. Answers are
kept in .cache/stock/ (not in Git) for 30 days, so a rebuild costs no requests. When a source's hourly limit
is reached (Unsplash: 50 requests an hour for a new app, 1,000 once Unsplash approves it for production;
Pexels: 200 an hour) the build waits until it resets.

Licences: Unsplash License (https://unsplash.com/license) and Pexels License (https://www.pexels.com/license/):
free for commercial use without permission; crediting the photographer is asked by both APIs' guidelines.
Not allowed: selling the photos unaltered or building a competing photo service with them. Unsplash+
photos are not under the free licence and are left out. Unsplash's guidelines also ask to hotlink its image
addresses (the bank does) and to tell its API when a photo is chosen (the build does: `track`).
"""
import hashlib, json, os, re, threading, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache" / "stock"
TTL = 30 * 86400
UA = "InvestIQ-image-bank/2.0 (https://getinvestiq.com; carousel image bank)"
UTM = "utm_source=investiq_image_bank&utm_medium=referral"
PER_PAGE = 30
_lock = threading.Lock()


def fetch(url, headers, cache=True, log=print, tries=6):
    """JSON from a stock API (cached on disk); waits out rate limits and server hiccups."""
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

    def __init__(self, key, log=print):
        self.key, self.log = key, log

    def search(self, q):
        url = "https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(
            {"query": q, "per_page": PER_PAGE, "content_filter": "high"})
        d = fetch(url, {"Authorization": "Client-ID " + self.key, "Accept-Version": "v1"}, log=self.log)
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
        """Tell Unsplash a photo was chosen (its API guidelines ask for it)."""
        try:
            fetch(url, {"Authorization": "Client-ID " + self.key, "Accept-Version": "v1"}, cache=False, log=self.log)
        except Exception as e:  # a missed count must not stop the build
            self.log(f"  (Unsplash download count failed: {e})")


class Pexels:
    name = "pexels"

    def __init__(self, key, log=print):
        self.key, self.log = key, log

    def search(self, q):
        url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "per_page": PER_PAGE})
        d = fetch(url, {"Authorization": self.key}, log=self.log)
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
        pass


def sources(log=print):
    """The stock sources whose key is in the environment."""
    out = []
    if os.environ.get("UNSPLASH_ACCESS_KEY", "").strip():
        out.append(Unsplash(os.environ["UNSPLASH_ACCESS_KEY"].strip(), log))
    if os.environ.get("PEXELS_API_KEY", "").strip():
        out.append(Pexels(os.environ["PEXELS_API_KEY"].strip(), log))
    return out


def links(c, slide_h=1500, preview_w=500, max_w=2400):
    """(photo address, preview address, [width, height]) for a stock photo: the width that gives a 4:5 slide its
    1500 px of height (at least 1200 px, at most the original), resized by the source's image server."""
    w, h = c["w"], c["h"]
    width = int(min(w, max_w, max(1200, -(-slide_h * w // h))))
    if c["provider"] == "unsplash":
        sep = "&" if "?" in c["orig"] else "?"
        make = lambda x: f"{c['orig']}{sep}w={x}&q=80&fm=jpg&fit=max"
    else:
        make = lambda x: f"{c['orig']}?auto=compress&cs=tinysrgb&w={x}"
    return make(width), make(preview_w), [width, round(width * h / w)]
