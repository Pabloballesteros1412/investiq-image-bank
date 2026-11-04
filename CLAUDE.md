# InvestIQ image bank — photos for InvestIQ videos

Separate project from the report generator (`investiq-deep-research`): do not mix them. Guide for humans,
in Spanish: `README.md`.

## What this is
5-6 real, freely licensed photos for each large company (50) and each mainstream market topic (29),
468 shots in all, for InvestIQ's videos. What each shot shows is in `catalog.json`; `image_bank.py` searches
Wikimedia Commons, keeps free licences only (CC0, public domain, CC BY, CC BY-SA), downloads the best photo,
crops it to 16:9 and 9:16, and records author, licence and credit line in `bank/manifest.json`.

## State (4 Nov 2026)
- Catalog, downloader, offline tests (`python -m unittest discover -p "test_*.py"`) and the dashboard are done.
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
4. Update the dashboard artifact **https://claude.ai/artifact/GH9JEo598mzHkmJkjAmc1e** (same URL, Pablo
   has it): `python dashboard.py <scratchpad>/banco-imagenes.html`, publish it with `url` set to that link
   and the previews from `dashboard.thumb_files()` as `files` (max 255 files per publish: two publishes).
5. Photos are not committed (~1 GB, `.gitignore`); commit `bank/manifest.json`, `CREDITS.md`,
   `credits.csv`, `prompts.jsonl`. Ask Pablo where the photos should be stored for the video project.

## Rules
- Free licences only, and every photo keeps its credit line (`credit` in the manifest).
- Shots of real people (`"person": true`) are never generated with AI; `prompts.jsonl` leaves them out.
- CEO names in `catalog.json` name who is in the photo; check the current role before a video uses it.
- Andra Markets' video style (black and white, no blue) is for Andra, not for InvestIQ.
