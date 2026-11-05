# InvestIQ image bank — photos for InvestIQ's carousels

Separate project from the report generator (`investiq-deep-research`): do not mix them. Guide for humans,
in Spanish: `README.md`.

## What this is
InvestIQ's own photo bank for the **Claude chat on claude.ai that makes InvestIQ's carousels** (Pablo,
4 Nov 2026). **10 photos per subject** (Pablo: ~500 photos were far too few): every S&P 500 company (list read
from Wikipedia by `universe`), 86 well-known US-listed companies outside it (`extras.json`), 37 market topics
and 11 GICS sectors (`catalog.json`, 10 hand-written searches each). About 6,500 photos.

Decisions (Pablo, 4 Nov 2026):
- **Photos are linked, not copied**: `bank/subjects/<ID>.json` gives each photo's Wikimedia Commons address
  (standard 1280/1920 px thumbnail), a 500 px preview, what it shows, the focus point, credit and licence.
  The chat crops to **4:5 (1200x1500) or 1:1 (1200x1200)** itself. Nothing heavy in Git.
- **Gaps are filled by sector photos**: a company with fewer than 10 photos of its own gets `fill_from` = its
  GICS sector in the index; those photos are generic and must never be presented as the company's.
- The repo is **public** (Pablo switched it on 4 Nov) so the chat can read
  `https://raw.githubusercontent.com/Pabloballesteros1412/investiq-image-bank/main/bank/index.json`.
  `CAROUSEL_CHAT.md` has the block to paste into the chat's project instructions.

## State (4 Nov 2026, evening): first real build done
- **Built and pushed** on branch `claude/nifty-dijkstra-hpxtiq` (not yet in `main`, which is what the chat reads):
  583 companies (500 S&P 500 + 83 extras; 3 extras were already in the index), 37 topics, 11 sectors,
  3,828 photos (3,355 of companies, 473 of topics and sectors). 248 companies have 10 photos of their own,
  100 have none (Commons has nothing usable under their name: Danaher, EOG, ICE, Intuitive Surgical...): the
  index gives them `fill_from` = their sector. Tests: `python -m unittest discover -p "test_*.py"` (24, offline).
- **Network**: the three APIs answer 200 with `WIKIMEDIA_TOKEN` (`Authorization: Bearer`, owner-only OAuth 2
  consumer of Pablo's account). Without it, the shared cloud egress gets 429 nearly always, and so do anonymous
  downloads from `upload.wikimedia.org` ("robot policy"); with it they work. In a viewer's browser the photos
  load normally. Logged-in calls still get the odd 429 with `Retry-After` (honoured, logged on stderr) when
  more than ~3 requests run at once: the build looks ahead with 2 workers, don't raise it.
- **Fixed on the first real run**: S&P table rows written `|| cell` and `{{BZX link|CBOE}}`; Commons category
  from the Wikidata sitelink / P910 / a company-filed category of the same name (+31 by hand, `"manual"`);
  Wikidata `mul` labels (Apple's CEO); latest-start CEO; the API's `?utm_source=` on file URLs (broke every
  thumbnail); HTTP 414 on 50 long titles (POST); non-atomic manifest writes.
- **Picker rules learnt from looking at the photos** (see the module docstring and README): `shows` is the
  photo's own file name, never the wished scene; CEO photo = the person's Wikidata P18, else a search with the
  full name that also names the company; category photos need a telling file name, JPEG, no events/sports/
  sponsorships/protests (NextEra -> NASCAR), only subcategories named after the company or its sites
  (Blackstone -> Fleetwood Mac); search hits must name the company and a place or thing in the file name;
  ambiguous short names (the Wikipedia article is something else: Blackstone, Target, Ball) are searched in
  full; no letters, paintings, survey drawings, screenshots, or pre-1960 photos outside `historic` shots.
- **Catalog**: every topic and sector photo was checked by eye; ~90 shots rewritten with `must` (words the
  file name or categories must hold) and per-shot `exclude`. AAPL and DIS leaders updated from Wikidata (John
  Ternus since Sep 2026, Josh D'Amaro 2026); Wikidata is behind for Intel and Walmart, the catalog is right.
- Dashboard artifact for Pablo: **https://claude.ai/artifact/GH9JEo598mzHkmJkjAmc1e** (previews do not load
  inside an artifact; the GitHub Pages gallery shows them).

## Pablo's verdict on the first build and the new direction (4 Nov 2026, night)
- Pablo looked at a random sample and was not sure these were the images he wants: Commons is documentary and
  uneven (about 4 in 10 good, 3 dull, 3 wrong). Decision: **keep only the best Commons photos, and use Unsplash
  and Pexels** for topics and sectors.
- **Review gate** (done): `review.py` makes contact sheets of 30 numbered 4:5 tiles; grades go to
  `bank/review.json` (3 best, 2 plain, 1 reject, criteria and calibration in `RUBRIC.md`). The index publishes
  Commons photos only with grade 3; the build never picks a photo graded below 3 again. All 3,828 Commons
  photos were graded (sheet 1 by me, the rest by 5 parallel subagents with the rubric; a random check of 30
  grade-3 and 30 grade-2 photos agreed): 407 (10.6%; 1,618 grade 2, 1,803 grade 1) are grade 3, so the index
  now has 407 photos: 336 of companies (220 of 583 companies have at least one, 25 have three or more; the big
  names keep 1-6 each) and 71 of topics and sectors (0-4 each, until Unsplash/Pexels fill them). After any new
  build, new Commons photos stay unpublished until graded.
- **Unsplash and Pexels** (code done and tested offline, `stock.py`; not run yet): the four hosts
  (`api.unsplash.com`, `images.unsplash.com`, `api.pexels.com`, `images.pexels.com`) answer since the second
  session, but `UNSPLASH_ACCESS_KEY` and `PEXELS_API_KEY` are still not in the environment (Pexels: 401). Pablo
  was asked to add them (a new session picks them up). **Pexels has paused issuing new API keys** (its API page,
  5 Nov 2026): go with Unsplash alone (a source without its key is skipped) and add Pexels if it reopens.
  Pablo's Network secrets dialog takes Host + Header + Prefix + Token and the proxy adds the header itself to
  requests to that host (no environment variable). Unsplash: Host `api.unsplash.com`, Header `Authorization`,
  Prefix `Client-ID`. `stock.sources()` uses an env key if there is one, else probes the API without a key and
  enables the source if it answers 200 (one request per run). Different from `WIKIMEDIA_TOKEN`, a placeholder
  the proxy swaps only inside our own Authorization header (no header: anonymous, 429). Note: `WIKIMEDIA_TOKEN` is now a short placeholder that
  the egress proxy swaps for the real token (network secret): it only works in the Authorization header to the
  Wikimedia hosts, which is where `headers()` sends it. Topics and sectors run each shot on Unsplash, Pexels and Commons; a stock photo must name every word
  of the search (or a `must` word) in its description and then wins (+30). Never for real people; no Unsplash+,
  renders, illustrations or quotes. Answers cached in `.cache/stock/` for 30 days. Unsplash's limit for a new app
  is 50 requests an hour (~480 searches for topics and sectors: about 10 hours; ask Pablo to apply for
  production, 1,000/h), Pexels 200/h.

- **Brands** (Pablo chose it, 4 Nov night; code done and tested offline, not run yet): `brands.json` lists the
  brands and products of 236 consumer-facing companies (as stock descriptions name them: "iPhone", "Big Mac",
  "Tesla Model 3", "Chase bank"). A company keeps its approved Commons photos first and fills the rest of its 10
  with Unsplash/Pexels photos found by searching its first 3 brands; a photo counts only if its description names
  a brand, the full name or an unambiguous short name; at most 2 per photographer. Companies not in brands.json
  get no stock photos. `build --kind company --stock-only` keeps the approved Commons photos and redoes only the
  brand photos (no Commons search, nothing to grade). Stock photos are published unless graded below 3
  (`python review.py sheets --stock` to check them). 394 searches per source.

## Next work (in order)
1. New session with the keys: check `curl -sS -o /dev/null -w "%{http_code}" -H "Authorization: $PEXELS_API_KEY"
   "https://api.pexels.com/v1/search?query=gold"` gives 200 (Unsplash: `-H "Authorization: Client-ID
   $UNSPLASH_ACCESS_KEY" https://api.unsplash.com/search/photos?query=gold`); the answer shapes in `stock.py`
   were written from the APIs' documentation, so check one real answer first. Then
   `python image_bank.py build --kind topic,sector --redo` and `python image_bank.py build --kind company
   --stock-only`; look at everything by eye (`python review.py sheets --stock`: grade 1-2 hides a photo, and
   wrong brand terms get fixed in `brands.json`), fix topic searches in `catalog.json`, grade any new Commons
   photos (`python review.py sheets` + `grade`), `index`, `credits`, `python dashboard.py`, commit and push.
   **Unsplash production**: Pablo created the app (5 Nov 2026) and is in demo mode (50 requests/h). The
   production form asks for screenshots of the photographer + Unsplash credit, both linked. The gallery does it
   ("Photo by <a author_url> on <a unsplash.com?utm...>", checked with Playwright). After the first real run,
   screenshot a topic and a brand page of `docs/index.html` with Unsplash photos (Playwright, deviceScaleFactor 2),
   send them to Pablo to upload with the application; never mock them. Its checklist (hotlink, trigger
   downloads, no Unsplash name or logo, accurate description, attribution) is met by `stock.py` and the gallery.
2. Get this branch into `main` (PR + merge, Pablo's call): until then the chat reads the old empty index.
3. Switch on GitHub Pages (Settings -> Pages -> main, /docs) if Pablo wants the gallery with images.
4. Big companies left with few published photos: a hand-written catalog entry (stores, products, HQ) and a
   rebuild + review round for them.

## Rules
- Free licences only, and every photo keeps its credit line (`credit`).
- Shots of real people (`"person": true`, CEOs) are never generated with AI; `prompts.jsonl` leaves them out.
- CEOs come from Wikidata and can be stale: the chat is told to check before naming a role.
- Andra Markets' style (black and white, no blue, engraving carousels) is for Andra, not for InvestIQ.
