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

## Unsplash works (5 Nov 2026, third session)
- Pablo added the Unsplash key as a network secret: `stock.sources()` finds Unsplash by its keyless probe (Pexels:
  no key, skipped). Demo limit confirmed (`X-Ratelimit-Limit: 50`). A real search answer matches `Unsplash.candidate`
  (urls.raw, links.html/download_location, user.links.html; `premium`/`plus` are null on free photos; search results
  carry no tags). images.unsplash.com serves the resized addresses.
- First real stock run: `build --only gold` (7 Unsplash + 3 Commons) and `build --only AAPL --stock-only` (5
  approved Commons + 5 Unsplash brand photos: iPhone, Apple Store). Two gold stock picks pass only through the
  photographer's own description ("gold mine" -> nuggets on a table, "gold panning" -> dirt): grade them in
  `review.py sheets --stock`.
- Screenshots for Unsplash's production application (gold topic, Apple brands; only the Unsplash rows, since
  Commons thumbnails do not load from the cloud container) were sent to Pablo on 5 Nov.
- A session that started from `main` redid this branch's work by mistake (branch `claude/gifted-heisenberg-13n0mr`
  now carries this line instead); nothing of it was needed.
- **Topic/sector pass, part 1** (5 Nov afternoon): done for gold and 7 sectors (tech, health, financials,
  consumer discretionary, communication, industrials, staples); **40 topics and sectors left**. A 2-hour background
  run did only 5 of them, for two reasons now fixed:
  - Unsplash counts each endpoint on its own: searches have 50/h, and the download counts (`track`) have
    another 50/h. When the download counter ran out, `track` waited 15 min per photo. Now it never waits: a count
    it cannot send is kept as `"track_pending": true` on the photo in the manifest (the index does not copy it),
    and the end of every build sends the pending ones (17 pending at the end of this session).
  - The manifest was saved every 5 subjects, so a cut build lost up to 4 subjects of searches. It is now saved
    after every subject that has stock photos.
- **Checked by eye**: all 55 stock photos (`review.py sheets --stock`). Grade 1-2 (hidden, then replaced by
  rebuilding from the cache): a blurry conveyor loop, Cinderella Castle (Disney's own, not a sector photo), a
  close-up of dirt, and a torch over an empty pan for "gold panning". Grade 3: silver bars and the gold necklace
  (the gold topic asks for "silver bars" and "gold jewelry"). The 28 new Commons picks were graded too (4 grade 3).
  Index: 458 photos. Unsplash's alt texts are generic ("red and white train on rail"); the word-match rule
  still finds enough, since the photographer's own description often names the subject.
- **Topic/sector pass, part 2** (5 Nov evening, 2-hour background pieces with `--only` = the subjects still
  `checked` before 5 Nov): 31 of 48 done (each piece does 6-8). Every new photo was graded by eye after each
  piece (stock grade 1-2 hides it; Commons grade 3 publishes it). Index: 522 photos. Rubric rule added: in
  topics and sectors a brand front and centre (Exxon price sign, branded tanker) or a scene already used for
  another subject is at most 2. Fixes:
  - a build cut by its time limit never reached its end, so pending download counts are now also sent at the start;
  - the keyless probe took Unsplash's 403 "Rate Limit Exceeded" for a missing key: a piece started at the limit
    re-picked 6 topics with Commons only and dropped 30 pending counts as sent (undone from Git). Now a
    rate-limited answer counts as the source being there, a build of topics, sectors or brand photos stops when
    no stock source answers (`--commons-only` to go on), and a count whose source is missing stays pending.
- **Unsplash production applied** (Pablo, 5 Nov night, with the gold and Apple gallery screenshots): "In Review",
  5-10 business days. Until then demo mode (50 searches/h; still 50 on 6 Nov morning).
- **Pexels**: still no new API keys (Pablo tried on 6 Nov). Unsplash alone; add Pexels as a network secret
  (Host `api.pexels.com`, Header `Authorization`, no prefix) if it reopens.
- **Topic/sector pass, part 3** (5-6 Nov night): all 48 topics and sectors done with Unsplash and graded by eye;
  no download count pending. Then two rounds for the thin ones (graded after each):
  - refill: the 33 with 5 or fewer published photos rebuilt from the cache (hidden picks are never taken again);
  - new searches: in 21 topics, every shot without a published photo was rewritten in `catalog.json` as a short,
    generic search ("federal reserve", "stock market", "bank vault", "weight loss"; Commons-style shots of named
    buildings, events and people rarely give an Unsplash photo whose description names every word). About 60%
    of the new Unsplash picks were grade 3, against ~10% for Commons.
  Index: 639 photos; topics and sectors 4-10 published each (298 in all, from 242). A container restart killed
  one piece (nothing lost: the manifest is saved per subject and the answers are cached).

## Companies: reserve and brand photos (6 Nov 2026, afternoon)
- Pablo: "hay un huevo de empresas con una o ninguna foto". He chose to (1) publish a company's Commons photos
  graded 2 as a **reserve** and (2) run the Unsplash brand pass now, in demo mode.
- **Reserve** (`RESERVE_GRADE`, `reserve()`, `published_photos`): a company's grade-2 Commons photos fill the places
  its grade-3 and brand photos leave free, marked `"plain": true` in the index; a chat rule says to prefer the
  others and never use one as a cover. They are never picked again, but a rebuild keeps them (the build appends
  the old entry's plain photos). Topics and sectors: no reserve.
- **Brand pass** (`build --kind company --stock-only --only <ids>`, 2-hour pieces, ~16 companies an hour in demo
  mode): done for the 47 big catalog companies and ~55 more (alphabetical up to Garmin); every brand photo graded
  by eye (about 30% grade 3; repeats of the same product are 2). Brand terms fixed after looking: Broadcom and
  Palantir added; ambiguous ones replaced (Abbott -> "Abbott Laboratories", Similac; Cisco -> "Cisco Systems";
  Casey's -> "Casey's General Store"; Chipotle -> "Chipotle Mexican Grill"). Unsplash still finds nothing usable
  for ASML, BlackRock (an Irish castle), UnitedHealth, Church & Dwight, CME.
- Index: 2,165 photos (1,809 Commons, 1,390 of them plain; 356 Unsplash). Companies with 0 / 1 / 2 / 3+ photos:
  141 / 85 / 53 / 304 (before: 362 / 138 / 53 / 30). PR #2 merged (6 Nov night).
- **Brand pass finished** (7 Nov morning): all 238 brands.json companies, in 2-hour pieces (two container
  restarts cut pieces; nothing lost: the manifest is saved per subject and answers are cached). Every brand photo
  graded by eye. More ambiguous terms fixed after looking: McCormick (McCormick Place) -> spices; On ("On
  Running" = any runner) -> shoe models; Gillette (Gillette Stadium) -> "Gillette razor"; Snapdragon (the
  flower) -> "Snapdragon processor"; Roku (Roku gin) -> "Roku TV". Rule of thumb: a brand that is also a
  common word, place or person needs a product word next to it.
- Index: 2,267 photos (1,807 Commons, 1,388 of them plain; 460 Unsplash). Companies with 0 / 1 / 2 / 3+ photos:
  135 / 81 / 58 / 309. 42 Unsplash download counts pending (the next build sends them first).

## Bigger bank: 10 / 30 / 50 (12 Nov 2026)
- Pablo: 10 photos for every company, 30 for the well-known ones, 50 for topics. `TARGET` 10, `FAMOUS_TARGET` 30
  (the 50 companies with a hand-written catalog entry), `TOPIC_TARGET` 50 (sectors too); `target_of(e)` reads the
  manifest entry's `target`; the index gives every subject its `target` and `fill_from` compares against it.
- Topics: 10 more short searches each (20 shots); `shot_photos` shares the target over the shots in rounds
  (best of each shot, then second best...), at most 3 stock photos per photographer, one per file stem, and after
  the first round Commons photos only with a quality mark (`QUALITY`): only ~7% of the others passed review.
- Companies: `grow_companies.py` (scratchpad) collects Commons candidates for every company below target (deeper
  category crawl, searches for HQ/store/plant/sign...) into a JSON file; graded by eye; graded >= 2 merged into the
  manifest as `hand-picked` (a rebuild keeps them) - only while no build runs, since a build rewrites the manifest.
  Yield ~38% (grade 3 ~4%, grade 2 ~34%).
- Grading at scale: parallel subagents with `RUBRIC.md` plus a brief (topics: different photos of the same kind of
  thing are each graded on their merits; only near-identical repeats get 2), spot-checked by eye; Sonnet graders
  agree with the spot checks.
- Pablo asked to "scrape any website": declined (copyright; InvestIQ posts commercially). Added free-licence
  sources instead (stock.py): Flickr (CC BY / BY-SA / CC0 / PDM / US gov only, >= 1600 px; needs FLICKR_API_KEY in
  the environment), NASA (public domain, no key, space subjects only, launch providers' photos excluded), Pixabay
  (needs PIXABAY_API_KEY and full-HD access). Openverse first tested and dropped (flaky, Flickr at 1024 px).
- Flickr API keys now need Flickr Pro (Pablo saw "creación de claves API desactivada para cuentas gratuitas", 12
  Nov); Pablo asked whether to give me his Flickr login to scrape: declined (no passwords in chat, Flickr's terms
  forbid robots outside the API, a free account unlocks nothing). Pro for a month would give the same photos at
  2048 px.
- **Openverse after all** (Pablo, 12 Nov night, after seeing samples: "adelante con openverse"): `stock.Openverse`
  (Flickr photos, `license_type=commercial,modification`, no key: 20 searches/min, 200/day nominal, it let ~700
  through in one night). Flickr's sizes above 1024 px need a secret only its API gives, so every Openverse photo
  carries `low_res` (long side < 1500): `is_plain()` makes the index mark it `plain`, a grade-2 one is held in
  `reserve()` like a Commons grade 2, and the index rules / CAROUSEL_CHAT.md tell the chat never to use one as a
  cover and to use it small (half slide, inset, grid). Collector `grow_openverse.py` (scratchpad): famous
  companies first (brand terms, "<name> headquarters", the name), at most 4 per photographer, the description must
  name the company or a brand. Yield: famous ~41% (grade >= 2), the rest ~20%: name clashes (Snowflake, SAP, Vale,
  Ventas, Iron Mountain...), events, screenshots, naming-rights stadiums and towers, corporate jets (all rejected).
  2,011 candidates graded: 72 grade 3, 526 grade 2.
- Progress (13 Nov, ~01:00 UTC): index 4,227 photos on the branch (main still 2,337). Commons company candidates:
  3,248 graded, 178 grade 3 + 1,175 grade 2, all merged. Topics grown in 2-hour pieces (~1 topic an hour, Unsplash
  demo limit): done recession, jobs, bull-market, crash, ai, datacenters, chips, crypto, gold, oil, tariffs,
  china, dollar, bonds (graded); `topics_a5.txt` (21 topics) running, then `topics_b.txt` (13). Unsplash grade 2
  hides a stock topic photo, so each grown topic loses ~half; a refill pass from the cache at the end (`build
  --kind topic,sector --redo`, cached answers cost nothing) fills the gaps. Unsplash download counts pending grow
  (361): they are sent at the start and end of builds, 50 an hour.

## Next work (in order)
1. Topics, sectors and the brand pass are done. When Unsplash production is approved, a rebuild of the brand
   terms fixed after their first search (Abbott, Cisco, Casey's, Chipotle, McCormick, On, P&G, Qualcomm, Roku)
   would find better photos for them. Then grade; look at everything by eye (`python review.py sheets --stock`: grade 1-2 hides a photo, and
   wrong brand terms get fixed in `brands.json`), fix topic searches in `catalog.json`, grade any new Commons
   photos (`python review.py sheets` + `grade`), `index`, `credits`, `python dashboard.py`, commit and push.
   **Unsplash production**: applied on 5 Nov (in review). Once approved (`X-Ratelimit-Limit: 1000`), the company
   brand pass takes about half an hour.
2. Done: PRs #1 to #4 merged into `main` (6-7 Nov 2026); the raw `main/bank/index.json` the chat reads
   has 2,337 photos and 631 subjects (checked 7 Nov). Later work goes in through a new PR.
3. Done: GitHub Pages is on (main, /docs): https://pabloballesteros1412.github.io/investiq-image-bank/ . Every
   merge into main redeploys it ("pages build and deployment" runs, all green; github.io is not reachable from
   the cloud container, so check it through those runs).
4. Done (7 Nov): hand search on Commons for the 26 catalog companies with 0-3 good photos (5 targeted queries
   each: HQ by address, plants, products, signs), 303 candidates graded by eye: 45 grade 3 (put first), 121 grade 2
   (reserve). They carry `"how": "hand-picked"` (`HAND`) and a rebuild keeps them. Still thin: ASML (Commons has
   one plain photo of Veldhoven), MicroStrategy (nothing), UnitedHealth (one Optum HQ aerial), Palantir and
   Micron (meetings with politicians, protests, Biden at Micron: all rejected). Index: 2,337 photos.

## Rules
- Free licences only, and every photo keeps its credit line (`credit`).
- Shots of real people (`"person": true`, CEOs) are never generated with AI; `prompts.jsonl` leaves them out.
- CEOs come from Wikidata and can be stale: the chat is told to check before naming a role.
- Andra Markets' style (black and white, no blue, engraving carousels) is for Andra, not for InvestIQ.
