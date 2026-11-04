# InvestIQ image bank — photos for InvestIQ's carousels

Separate project from the report generator (`investiq-deep-research`): do not mix them. Guide for humans,
in Spanish: `README.md`.

## What this is
InvestIQ's own photo bank for the **Claude chat on claude.ai that makes InvestIQ's carousels** (Pablo,
4 Nov 2026). 5-6 real, freely licensed photos for each large company (50) and each mainstream market topic
(29), 468 shots in all. What each shot shows is in `catalog.json`. `image_bank.py` searches Wikimedia
Commons, keeps free licences only (CC0, public domain, CC BY, CC BY-SA), downloads the best photo, crops it
to **4:5 (1200x1500) and 1:1 (1200x1200)** (Pablo's choice; 16x9, 9x16 and 3x4 on request) and records
author, licence and credit line in `bank/manifest.json`.

**How the chat reaches the photos:** `bank/index.json` lists every photo with what it shows, its credit and
the public address of each crop (`BASE_URL` = the repo's raw GitHub address). The crops and previews are
committed; the full-size photos are not. The repo must be **public** for those addresses to work (Pablo
switches it). The block to paste into the chat's project instructions is in `CAROUSEL_CHAT.md`.

## State (4 Nov 2026)
- Catalog, downloader, index, offline tests (`python -m unittest discover -p "test_*.py"`) and the dashboard
  are done.
- **No photo downloaded yet**: the first cloud session's network policy denied `commons.wikimedia.org` and
  `upload.wikimedia.org`. Pablo asked for both to be added to the environment's Allowed domains.
- The downloader has never run against the real Commons API (only against simulated answers): expect to
  fix small things on the first real run (the search answer's format, rate limits, thumbnail sizes).

## Next work (in order)
1. Check the network: `curl -sS -o /dev/null -w "%{http_code}" -A "InvestIQ-image-bank/1.0" "https://commons.wikimedia.org/w/api.php?action=query&meta=siteinfo&format=json"` must give 200.
2. `pip install pillow`, then `python image_bank.py build --only AAPL` first (one subject, check the
   photos by eye), then `python image_bank.py build` for the rest (20-30 min; it resumes if cut).
3. Review `bank/review.html`; fix bad picks in `bank/manifest.json` (`exclude` / `prefer` / `focus`, listed
   in `"manual"`), then `build --only <ID>`. Improve queries in `catalog.json` when a subject is weak.
4. Commit `bank/` (crops, previews, `index.json`, `manifest.json`, credits, prompts) and push: that is what
   the carousel chat reads. Large pushes: commit in batches of a few subjects if the proxy rejects one.
5. Update the dashboard artifact **https://claude.ai/artifact/GH9JEo598mzHkmJkjAmc1e** (same URL, Pablo
   has it): `python dashboard.py <scratchpad>/banco-imagenes.html`, publish it with `url` set to that link
   and the previews from `dashboard.thumb_files()` as `files` (max 255 files per publish: two publishes).

## Rules
- Free licences only, and every photo keeps its credit line (`credit` in the manifest and the index).
- Shots of real people (`"person": true`) are never generated with AI; `prompts.jsonl` leaves them out.
- CEO names in `catalog.json` name who is in the photo; check the current role before a carousel uses it.
- Andra Markets' style (black and white, no blue, engraving carousels) is for Andra, not for InvestIQ.
