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

## Next work (in order)
1. Get this branch into `main` (PR + merge, Pablo's call): until then the chat reads the old empty index.
2. Switch on GitHub Pages (Settings -> Pages -> main, /docs) if Pablo wants the gallery with images.
3. Weak companies: browse the gallery; for a wrong photo add `"exclude"` + `"manual": ["exclude"]` in the
   manifest and `build --only <ID>`. For big names with few photos, a hand-written catalog entry (their
   stores, products, HQ) works better than more rules: e.g. TJX (TJ Maxx, Marshalls), Thermo Fisher, KLA,
   ServiceNow, Shopify, Snowflake, Palo Alto Networks, Robinhood, Intuitive Surgical (da Vinci robot).
4. Re-run `universe` when the S&P 500 changes and `build --redo` every few months (dead links, new photos).

## Rules
- Free licences only, and every photo keeps its credit line (`credit`).
- Shots of real people (`"person": true`, CEOs) are never generated with AI; `prompts.jsonl` leaves them out.
- CEOs come from Wikidata and can be stale: the chat is told to check before naming a role.
- Andra Markets' style (black and white, no blue, engraving carousels) is for Andra, not for InvestIQ.
