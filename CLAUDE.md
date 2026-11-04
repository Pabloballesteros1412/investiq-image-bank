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

## State (4 Nov 2026)
- Catalog (98 subjects, 777 hand-written shots), extras, universe builder, photo picker, index, gallery
  (`docs/index.html`, for GitHub Pages) and offline tests (`python -m unittest discover -p "test_*.py"`) done.
- **Nothing has run against the real APIs yet**: the first session's network denied Wikimedia. Pablo asked
  Carl to allow `en.wikipedia.org`, `www.wikidata.org`, `commons.wikimedia.org` and `upload.wikimedia.org`.
  Expect to fix small things on the first real run: the S&P 500 wikitext table format (`parse_sp500`, the run
  stops if it reads fewer than 400 companies), API answer shapes, rate limits, thumbnail addresses.
- Dashboard artifact for Pablo: **https://claude.ai/artifact/GH9JEo598mzHkmJkjAmc1e** (previews do not load
  inside an artifact; the GitHub Pages gallery shows them).

## Next work (in order)
1. Check the network: `curl -sS -o /dev/null -w "%{http_code}" -A "InvestIQ-image-bank/2.0" "https://commons.wikimedia.org/w/api.php?action=query&meta=siteinfo&format=json"` must give 200 (same for en.wikipedia.org and www.wikidata.org).
2. `python image_bank.py universe`; check `bank/universe.json` (about 590 companies; how many lack a Wikidata
   record or a Commons category; fix by hand with `"manual"`).
3. `python image_bank.py build --only AAPL,MMM,gold,sector-energy` and check the photos by eye (open the
   `preview` links, or `python dashboard.py` and the gallery); then `python image_bank.py build`
   (an hour or more; it resumes if cut). Commit and push in between: that is what the chat reads.
4. Look at weak subjects (few photos, wrong photos): `exclude` in the manifest, better searches in
   `catalog.json`, fixes in `universe.json`.
5. Update the gallery (`python dashboard.py`, commit `docs/`) and the artifact (`python dashboard.py
   <scratchpad>/banco-imagenes.html --artifact`, publish to the URL above). Ask Pablo to switch on GitHub
   Pages (Settings → Pages → main, /docs) if he wants the gallery with images.

## Rules
- Free licences only, and every photo keeps its credit line (`credit`).
- Shots of real people (`"person": true`, CEOs) are never generated with AI; `prompts.jsonl` leaves them out.
- CEOs come from Wikidata and can be stale: the chat is told to check before naming a role.
- Andra Markets' style (black and white, no blue, engraving carousels) is for Andra, not for InvestIQ.
