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
- **More keyless free sources** (13 Nov, Pablo: "recórrete toda la web buscando fotos sin copyright"; done only
  through official APIs with clear licences, never by scraping sites): `stock.LoC` (Library of Congress, Carol M.
  Highsmith Archive only: public domain, "no known restrictions"; IIIF full size for older scans, newer scans
  have only a 1024 px `v.jpg` -> `low_res`, used for companies only) and `stock.WordPress` (WordPress Photos, CC0,
  2048 px or full). Both run in topic builds with Unsplash; NASA too (space subjects). Tried and dropped:
  StockSnap (CDN serves 960 px), rawpixel (1024 px, mostly illustrations), nappy (2,200 photos), Openverse's
  museum sources. LoC for companies (`grow_loc.py`, scratchpad) yields little: 25 candidates in 194 companies
  (Google HQ, Intel fab, Pepsi signs, GE Schenectady), the rest name clashes (Circle -> Logan Circle).
  `safe_search()` skips a stock source that fails for one query (a connection reset, Cloudflare 525 from
  loc.gov had cost defense and consumer their rebuild); a used-up hourly limit still stops the build.
- Progress (13 Nov, morning): Commons and Openverse company candidates all graded and merged. Topics grown in
  2-hour pieces (~1-2 topics an hour, Unsplash demo limit): done recession, jobs, bull-market, crash, ai,
  datacenters, chips, crypto, gold, oil, tariffs, china, dollar, bonds, housing, earnings, ipo, ev, nuclear,
  banks, investing (graded); the rest of `topics_a6.txt` (defense and consumer to redo), then `topics_b.txt` (13),
  then the sectors. Unsplash grade 2 hides a stock topic photo, so each grown topic loses ~half; a refill pass
  from the cache at the end (`build --kind topic,sector --redo`, cached answers cost nothing) fills the gaps.
  Unsplash download counts pending grow (~500): they are sent at the start and end of builds, 50 an hour.
- Progress (14 Nov): every topic and sector has had its grow piece (luxury cut short by the Unsplash limit) and
  every pick was graded by eye (sheets in the scratchpad, sector grades by Sonnet subagents with spot checks).
  Refill pass from the cache under way (`build --kind topic,sector --redo`, 2-hour pieces; a container restart
  killed one, nothing lost). After the first refill the sectors had 20-46 published each; tech, financials,
  consumer discretionary and materials ran dry, so each got 8 more short searches in `catalog.json` (piggy bank,
  ATM, motherboard, quarry, department store...). Commons topic picks after the first round keep bringing
  featured pictures that only share a word (birds, butterflies, nebulae, food dishes): ~5% reach grade 3.
- Companies (13-14 Nov): deep Openverse pass (`grow_openverse_deep.py`, brand terms 4-8 + store/factory/office/
  building; 688 candidates, ~13% usable: name clashes, events, sponsorship) and a WordPress Photos pass
  (`grow_wordpress.py`: 32 candidates, only 3 SpaceX launch photos usable; the directory is small and its rules
  keep brands out, so it is not worth another company pass) were graded and merged: +6 best, +70 plain.
  Bank: 4,966 published photos (14 Nov, before the refill). Unsplash download counts pending: ~730.
- Second refill (14 Nov): 170 more short searches in `catalog.json` (8 per thin topic: "finance", "server",
  "atm", "uranium"...; a string already used as a shot id in that topic gets renamed, or `check_catalog` fails).
  `build --kind topic,sector --redo` in 2-hour pieces (5-9 topics a piece, Unsplash demo limit), every pick graded
  after each piece (stock by me, Commons by Sonnet subagents with `grader_brief.md`): Unsplash ~35-40% grade 3,
  Commons in topics now ~3-7% (maps, diagrams, word matches: bells for "bell", wine barrels for "barrel").
  Stopped after europe for the merge; still to refill: quantum, robotics, cybersecurity, india, japan, metals,
  travel, luxury. Unsplash's search for "bell" answers HTTP 410 (skipped by `safe_search`).
- **Merged into main (14 Nov, PR #5)**: 5,454 published photos (main had 2,337): companies 3,969 (183 of 583 at
  target, 120 with none, the 50 famous ones 25 on average), topics 1,034, sectors 451 (none at 50 yet: quantum 8,
  earnings 11, ipo 13, ai 16 ... most 25-45). 3,158 are `plain` (grade 2 or `low_res`).
- **Third round of short searches** (14-15 Nov): the second refill was finished, then the 28 topics and sectors still
  under 40 got new short searches in `catalog.json` and were rebuilt with `--redo` in 2-hour pieces (3-7 topics a
  piece), every pick graded after each piece (stock by me; Commons by Sonnet subagents or by me). Unsplash ~35-40%
  grade 3, Commons in topics ~3-10%. Search words that are also sports or games ("race" -> rally cars and podiums,
  "bell", "barrel") bring word matches: write them with a money or market word next to them.
  `review.py` fix: some Commons PNGs carry metadata chunks bigger than Pillow's limit (`MAX_TEXT_CHUNK` raised).
  Then a third refill of all 48 from the cache (graded: stock 31 of 207 grade 3, Commons 14 of 421).
- **Merged into main (15 Nov, PR #6)**: 5,750 published photos: companies 3,969, topics 1,308, sectors 473 (none at
  50 yet, average 37; thinnest quantum 13, ai 21, nuclear 24, earnings 27, ipo 27). Each refill pass now adds only
  ~70. Under way at the merge: 6-8 more short searches for the 12 thinnest topics (`catalog.json`, build in pieces);
  fed, crash, ai and oil were built but not yet graded (their new picks are in the manifest, not in the index).
- **Topics keep what they have** (15 Nov): new short searches added almost nothing (5,750 -> 5,753; fed even fell
  31 -> 27), because `shot_photos` shares the target over the shots in rounds, so a new shot's ungraded first pick
  pushed a grade-3 photo of an older shot out of a later round. Fixed: a topic or sector rebuild now keeps its
  published photos (`keep`, the build's `kept()`), already-approved candidates go first within a shot (`prefer`),
  and only the free places are filled (test `test_published_photos_are_kept_and_new_shots_only_fill_free_places`).
  Then a fourth refill of all 48 (two 2-hour pieces) graded by eye (stock by me, Commons by Sonnet subagents with a
  check of every grade 3: Commons 8 of 386 grade 3, stock 45 of 161). Word matches fixed in `catalog.json`: chips
  "ram" -> "ram module" (rams), cybersecurity "binary" -> "encryption key" ("nonbinary" blocks, protest signs).
- **Merged into main (15 Nov, PR #7)**: 5,830 published photos: companies 3,969, topics 1,372 (average 37), sectors
  489 (average 44.5; industrials at 50). Thinnest: quantum 15, ai 21, earnings 26, nuclear 27, fed 28, crash 31.
  About 300 Unsplash download counts pending (sent at the start and end of every build, 50 an hour).
- **Round 5 of short searches** (15-16 Nov): the 20 thinnest topics and sectors got ~320 new short searches in
  `catalog.json`. Each is appended while a topic has fewer than 50 shots, else it replaces a "dead" plain-string shot
  (no published photo, oldest first). Built with `--redo` in four 2-hour pieces. Every pick graded by eye:
  Unsplash 51 of 112 grade 3, Commons 26 of 252. Gains were biggest where the topic was thinnest (crash +9, bonds +10,
  earnings +7, crypto +7, quantum +6) and smallest where it was already near 40 (inflation +0, materials +2).
- **Merged into main (16 Nov, PR #8)**: 5,911 published photos: companies 3,969, topics 1,451 (average 39.2),
  sectors 491 (average 44.6). Thinnest: quantum 21, ai 26, nuclear 30, fed 32, earnings 33, dollar 35, ev 35.
  273 Unsplash download counts pending.
- **Refill 5, round 6, refill 6** (16 Nov): refill 5 of all 47 thin topics from the cache (stock 31 of 93 grade 3,
  Commons 12 of 339); round 6 = 84 short searches in 13 thin topics (`replace_shots.py` rules as round 5; stock 7 of
  32 grade 3, Commons 6 of 156); refill 6 of the 46 below 50 (stock 12 of 67, Commons 9 of 297). `review.py` fix: a
  Commons file whose thumbnail Wikimedia cannot render ("failing image" 429) gets a black tile (grade it 1) instead of
  stopping the sheets. Each pass now adds only ~20-45 photos.
- **Merged into main (16 Nov, PR #9)**: 5,994 published photos: companies 3,969, topics 1,520 (average 41.1), sectors
  505 (average 45.9). Thinnest: quantum 24, ai 30, nuclear 30, fed 36, earnings 36, ev 36, banks 37. 310 Unsplash
  download counts pending.
- **Round 7, refill 7** (16-17 Nov): 203 short searches in the 14 thinnest topics (glp1 and metals appended, the rest
  replace dead shots; two 2-hour pieces); graded stock 20 of 62 grade 3, Commons 8 of 130. Then refill 7 of the 45
  below 50 from the cache (stock 9 of 68, Commons 7 of 245; subagent grade 3s with a brand front and centre or a
  person as the subject were lowered to 2). Word matches seen: "chandelier" (IBM's cryostat nickname) brings real
  chandeliers, "eagle" for fed is at most 2.
- **Merged into main (17 Nov, PR #10)**: 6,041 published photos: companies 3,969, topics 1,563 (average 42.2), sectors
  509 (average 46.3); 4 of 48 at 50. Thinnest: quantum 26, nuclear 31, ai 32, chips 38, earnings 38, banks 38.
  320 Unsplash download counts pending.
- **Round 8, refill 8** (17 Nov): 214 short searches in the 15 thinnest topics (three 2-hour pieces); graded stock 9 of
  47 grade 3, Commons 9 of 129. Then refill 8 of the 44 below 50 from the cache (stock 12 of 56, Commons 5 of 238; a
  subagent grade 3 that repeated a board already graded 2 was lowered). Word matches seen: "chandelier" again (banks,
  quantum), "chips" -> Doritos, "nickel" -> an 1884 coin, "copper" -> Copper Mountain, "toast" for IPOs.
- **Merged into main (17 Nov, PR #11)**: 6,081 published photos: companies 3,969, topics 1,599 (average 43.2), sectors
  513 (average 46.6); 4 of 48 at 50. Thinnest: quantum 29, nuclear 31, ai 33, earnings 38, banks 40. Each pass now
  adds only ~20-40. 318 Unsplash download counts pending.
- **Round 9, refill 9** (17 Nov): 241 short searches in the 23 thinnest topics (four container restarts cut pieces;
  nothing lost); graded stock 16 of 60 grade 3, Commons 9 of 148. Then refill 9 of the 44 below 50 from the cache
  (stock 15 of 54, Commons 8 of 202; subagent grade 3s lowered: orange juice for materials, a pasta shelf with one
  brand front and centre, a second view of a tower already graded 2). Word matches seen: mint for "fed", a geyser
  for "steam plume", a Transformers statue, gold coins for crypto, a Botox vial for GLP-1, Old Faithful for nuclear.
- **Merged into main (17 Nov, PR #12)**: 6,135 published photos: companies 3,969, topics 1,647 (average 44.5), sectors
  519 (average 47.2); 5 of 48 at 50. Thinnest: quantum 33, nuclear 34, ai 35, earnings 38, chips 41, datacenters 42.
  324 Unsplash download counts pending. Next: round 10 (212 searches in 18 topics, `new_r10.json` in the scratchpad).
- **Round 10, refill 10** (17 Nov): 212 short searches in 18 thin topics (three 2-hour pieces); graded stock 24 of 47
  grade 3, Commons 9 of 99. Then refill 10 of the other 28 below 50 from the cache (stock 8 of 17, Commons 4 of 71).
  Repeats lowered to 2: another Taj Mahal for india, a second Apollo 11 lander view. Word matches seen: a tsunami sign
  for nuclear, a USB charger for EV, "launch" -> a Soyuz rocket for IPOs, Spider-Man for "night shift".
- **Merged into main (17 Nov, PR #13)**: 6,182 published photos: companies 3,969, topics 1,688 (average 45.6), sectors
  525 (average 47.7); 5 of 48 at 50. Thinnest: ai 35, nuclear 35, quantum 36, earnings 40, chips 44, datacenters 44,
  ipo 44. 335 Unsplash download counts pending. Next: round 11 (168 searches in 15 topics, already in `catalog.json`;
  tariffs had only 20 shots and got 20 more).
- **Rounds 11-13, refills 11-12** (17 Nov): round 11 (168 searches, 15 topics; stock 12 of 34 grade 3, Commons 3 of 77),
  refill 11 (stock 8 of 28, Commons 4 of 144), round 12 (84 searches, 11 topics; stock 12 of 26, Commons 7 of 55),
  round 13 (77 searches, 11 topics; stock 9 of 35, Commons 4 of 33), refill 12 of the 42 below 50 (stock 2 of 27,
  Commons 3 of 100: the cache is nearly spent). Searches tried in earlier rounds are kept in the scratchpad's
  `new_r*.json` and skipped when drafting new ones (a dead search only replays its cached answer). Word matches seen:
  a cat for "python code", a control-tower for "concrete tower", frost for quantum, a beekeeper for "protective suit".
- **Merged into main (17 Nov, PR #14)**: 6,247 published photos: companies 3,969, topics 1,750 (average 47.3), sectors
  528 (average 48.0); 6 of 48 at 50. Thinnest: ai 38, nuclear 41, quantum 42, earnings 45, tariffs 45. 356 Unsplash
  download counts pending.
- **Rounds 14-17** (17-18 Nov): short searches for every topic and sector under 50, drafted with `filter_cands.py`
  (scratchpad: drops any search already in `catalog.json`, for any subject, or in an earlier `new_r*.json`, since a
  repeat only replays its cached answer) and applied with `replace_shots.py`. Round 14 +12 photos, round 15 (33
  searches, plus 10 household goods appended to staples) +18, crash at 50; round 16 (120 searches, 27 subjects, nuclear
  plants written "<plant> nuclear") +17; round 17 (102 searches, 38 subjects, three 2-hour pieces; stock 7 of 11 grade 3,
  Commons 10 of 61) +18. Generic words are nearly used up: most new candidates are already in the catalog, so new
  searches have to be specific (named plants, "lab instruments", "keyhole", "torii"). Word matches seen: James Bond for
  "bond", a farmers' market for "debut", a mask dance for "house", a Sede Vacante relief for "vacant", lobster traps
  for "container stack". Apply a new round only after grading the last one: `replace_shots.py` swaps out shots with no
  published photo, and an ungraded pick is not published yet.
- Index after round 17: 6,312 published photos; topics and sectors 2,343 (13 of 48 at 50, the rest 46-49: sector-tech
  46, ev 47, quantum 47).
- **Round 18** (17-18 Nov): 128 searches in 36 subjects, four 2-hour pieces (a container restart cut one); 57 new picks
  graded, 11 grade 3 (earbuds, a monitor desk, a mouse, the NYSE, a TV studio, a GPU cluster, an EV charger, a jet on a
  runway, pharma vials, a levitating superconductor, a biometric gate). Word matches seen: chocolate-chip cookies for
  "chips", a disco ball in a bar called "Import Export", Domino Sugar for "refinery", a clock warehouse for robotics.
  Index: 6,323 photos; topics and sectors 2,354 (16 of 48 at 50, the rest 47-49).
- **Merged into main (18 Nov, PR #15)**.
- **Round 19** (18 Nov): 217 searches in the 33 under 50 (drafted with `filter_cands.py`: named nuclear plants,
  "hourglass money", "gantry crane", "food scale", "tokyo station"...), five 2-hour pieces. Grade 3: 10 stock (a
  clothing store, butter, cheese, a boarded window, a toolbox, port cranes, bond tables in a newspaper, a timber house
  frame, an EV connector, coin binoculars over the sea) and 1 Commons (a luxury resort pool). Lowered to 2: an 11th
  shopping cart for consumer, a second Cattenom view. Word matches seen: a Qing banknote plate for "dollar", a zipper
  for IPOs, a snowboarder and radio telescopes for quantum, a Christmas bauble for gold, a wall clock for "clock in".
  Index: 6,334 photos; topics and sectors 2,365 (19 of 48 at 50, the rest 48-49).
- **Merged into main (18 Nov, PR #16)**.
- **Round 20** (18-19 Nov): 119 searches in the 29 under 50 (generic words are spent: `filter_cands.py` dropped ~75% of
  the drafted candidates as already tried), three pieces (two container restarts cut them; nothing lost). Grade 3: 3
  stock (a gold pendant on velvet, an oil rig at sunset, roof shingles) and 2 Commons (a copper nugget, a transistor
  die). Word matches seen: a farmers' market for "market open", a race-circuit map for "circuit", a BlackBerry on its
  charging pod, a coal steam plant for "power plant steam", a laser cutter for "lab laser". Index: 6,339 photos; topics
  and sectors 2,370 (21 of 48 at 50, the rest 48-49). A round now adds ~5 photos: topics are as full as Unsplash's
  demo search can make them.
- **Merged into main (19 Nov, PR #20)**.
- **Famous companies, brand pass 2** (19 Nov): the 22 famous companies under 30 got more brand and product terms in
  `brands.json` (old terms kept first, so published photos keep priority; Nike Air Max/Dunk/store, Ryzen, Radeon, Google
  Maps, Chromecast, iShares, Crucial...) and were rebuilt with `build --kind company --stock-only` (up to 9 queries each),
  then a refill from the cache. Graded by eye: 48 of 102 grade 3 (Bank of America branches and towers, a Chase branch, a GE
  jet engine, Netflix screens, Nike shoes and a rooftop swoosh, a Visa card, a Pfizer vial). Hidden: Micron logo renders
  (one photographer uploads many), the Temple of Athena Nike, 3D buttons, repeats. Famous average 25.2 -> 25.6, 32 of 50
  at 30; still thin: MSTR 2, UNH 3, PLTR 7, ASML 8, MU 9 (Unsplash has nothing else of theirs).
- **Companies with no photo** (19 Nov): 120 of 583, all B2B or names Commons and Openverse had nothing for. 67 of them got
  `brands.json` terms (Botox for AbbVie, NAPA for Genuine Parts, Orkin for Rollins, Thermo King for Trane, Fluke and
  Tektronix for Fortive, Behr for Masco, Ryan Homes for NVR, Littmann for Solventum, Omnipod for Insulet, USDC for Circle);
  left out where the short name is a common word that would pass any photo (Southern, Mosaic, Williams, Affirm, Unity,
  Coherent, APA) or the brand is a naming-rights stadium (SoFi). Result: Unsplash has next to nothing of them (0 results
  for Orkin, Fluke, Behr, Ryan Homes, Labcorp, Trane, Taser, USDC); 5 photos kept (two NAPA stores, a Loews hotel, a Botox
  injection, the SoundHound app). Companies with no photo: 120 -> 116. A first run showed brand names matched at the start
  of any word ('Masco' -> ten photos of mascots, 'Nike' -> the Niketan garden): `has_name()` now wants the whole word
  (plural or possessive allowed); none of the 868 brand photos in the bank relied on the old rule.
- Bank (19 Nov): 6,364 published photos: companies 3,994 (186 at target, 116 with none; famous average 25.6, 32 of 50 at
  30), topics 1,823, sectors 547. 343 Unsplash download counts pending.
- **Thin companies, brand pass** (19 Nov): 92 companies with 1-9 photos got `brands.json` terms (Invisalign, Schlage,
  Moody's, FPL, PSE&G, Skippy, Spam, Keytruda, Paramount Pictures, Universal Robots...) and were rebuilt with
  `build --kind company --stock-only` in two pieces (a container restart cut the first). 37 picks, 13 grade 3 (an HPE
  office, Skippy jars, a wall of Spam, Paramount's gate, water tower and sign, Vulcan quarries, a Motorola walkie-talkie,
  Invisalign aligners). Rejected: name clashes (Dupont Circle, BHP = brake horsepower, other "Citizens" banks), Universal
  Robots renders, a strike picket, and Moto phones for Motorola Solutions (Motorola phones are Lenovo's; its Commons
  category "Motorola" is a match key, so such photos can pass: grade them 1). Companies: 3,994 -> 4,007 photos (187 at
  target, 116 with none); bank 6,377.
- **Openverse with the new brand terms** (19 Nov): `grow_openverse_brands.py` (scratchpad) searched Openverse (Flickr,
  low_res) with the first 6 `brands.json` terms of the 180 companies above (zero-photo, thin, famous under 30); a
  candidate's description must name a term, the full name or the short name as a whole word (`has_name`). 582
  candidates, graded (first 146 by me, the rest by 3 Sonnet subagents with `grader_brief.md`, every grade 3 and doubtful
  2 checked by eye): 26 grade 3 (NAPA stores, Behr cans, Delta faucets with "A Masco Company", Orkin trucks, Palo Verde,
  APS tower, NIPSCO's plant, Trane and Thermo King units, an EpiPen, Invisalign, a MiSeq, a Spectrum van, Chase, Oracle
  HQ, TSMC Fab 12, a Broadcom chip, Crucial RAM for Micron), 97 grade 2 (reserve). Rejects: name clashes (a dog called
  Masco, the X-24 lifting body of Martin Marietta the aerospace firm, Hubbell Trading Post, "Avast!", Grainger Street,
  Blackrock Baths, the Rio Tinto river, Colombian police for "Humana"), events and politicians' visits, naming-rights
  arenas, app screens, an Intel chip for Micron. Merged as hand-picked. Bank: 6,495 photos; companies 4,125 (194 at
  target, 101 with none; famous average 26.0, 34 of 50 at 30).
- **B2B companies, places they own** (19 Nov): 22 companies below target with no `brands.json` entry got terms for
  their subsidiaries and the places they own (SO: Georgia Power, Alabama Power, Plant Vogtle; PPL: LG&E, Kentucky
  Utilities; VICI: Caesars Palace, MGM Grand, Mandalay Bay; FRT: Santana Row, Bethesda Row; BXP: Embarcadero Center;
  AEE: Ameren Missouri; MCHP: Atmel; NRG: Reliant/Direct Energy; CNC: Ambetter, WellCare...), then an Unsplash brand
  build and an Openverse pass. Openverse 133 candidates (11 grade 3, 33 grade 2), Unsplash 14 (7 grade 3: Caesars
  Palace, Mandalay Bay, the Alabama Power sign). Rejected: naming-rights venues (Direct Energy Centre; Reliant Energy
  Plaza is CenterPoint's), a local "Ferguson Plumbing" that is not Ferguson Enterprises, events, app screens. Gains:
  SO 0 -> 8, PPL 0 -> 5, BXP 0 -> 4, FRT 1 -> 10, VICI 1 -> 10. Bank: 6,541 photos; companies 4,171 (196 at target, 97
  with none). Still nothing for AJG and WMB. Most of the remaining 97 zero-photo companies are insurers, REITs, payment
  processors and industrial suppliers whose names are common words.
- **Two more B2B rounds** (19 Nov): 17 companies got terms for their mines, plants, utilities and old names (CCJ: Cigar
  Lake; FCX: Morenci, Grasberg; NEM: Boddington; ETR: Grand Gulf, Arkansas Nuclear One; FE: Ohio Edison, JCP&L; ROK:
  Allen-Bradley Clock Tower; TRV: Travelers Tower; DOW: Dow Chemical; SW: WestRock, Smurfit Kappa...): +9 (Travelers
  Tower, a Dow plant, Consumers Energy's Karn plant, Ohio Edison). Then 10 zero-photo companies got better terms (da
  Vinci Surgical System, Comanche Peak, Humana Building, Labcorp, Littmann, Haliade, Fluke and Tektronix; SoFi Stadium
  dropped: naming rights): Unsplash gave only two Intuitive Surgical logo renders (grade 1), Openverse 20 candidates (2
  grade 3: a Haliade-X turbine for GE Vernova, a Littmann stethoscope; 3 grade 2). Bank: 6,555 photos; companies 4,185
  (197 at target, 93 with none). Unsplash and Openverse have next to nothing more for B2B names.
- **Commons with the brand terms** (19 Nov): `grow_commons_brands.py` (scratchpad) searched Commons with the first 8
  `brands.json` terms of the 274 companies below target (up to 4 per term). A hit must hold the term in its file
  name plus a business word or another of the company's names, or sit in a category named after the term that does
  ('Comanche Peak Nuclear Power Plant', not the mountain; "Vistra" alone is a Spanish word); visits, ceremonies,
  protests and events are left out. 195 candidates graded by eye: 34 grade 3 (Palo Verde, Morenci, Arkansas Nuclear
  One, Travelers Tower, Truist Center, Tektronix HQ, Embarcadero Center, a HOKA store, a Spectrum van, NovaSeq, Dexcom
  G7, the GE90), 73 grade 2. Rejected: sponsorship (Fortinet's IMOCA sailboats), naming-rights venues (Truist Field,
  Centene's rink), name clashes (Mount Gilead, Grainger County, Jimmy Dean), AIG's old 70 Pine Street. Merged as
  hand-picked. `build --brand-queries N` searches more brand terms per company on Unsplash (3 by default, times 3
  for the famous ones), but only 7 thin companies have more than 3 terms.
- **Round 21** (19 Nov): 77 searches in 26 topics (two pieces); stock 4 of 6 grade 3 (a warship in fog, gold bangles,
  Dotonbori, a sapphire ring), Commons 2 of 23 (a Bitcoin coin over a laptop, a fibre optic on a lab bench). Bank:
  6,665 photos; companies 4,289 (208 at target, 90 with none; famous average 26.2, 35 of 50 at 30), topics 1,829,
  sectors 547; 23 of 48 still at 48-49. Round 22 drafted (85 searches, 25 subjects, `new_r22.json`): generic words
  are spent, so they name places and things (Himeji, Senso-ji, debt clock, surgical robot, customs officer).
- **Round 22, round 23** (19-20 Nov): round 22 (85 searches) gave 1 photo (a photonics lab bench for quantum); round 23
  (116 searches in the 20 under 50, three pieces, a container restart cut one) gave 5 (a fibre patch panel, hands
  counting dollars, nuclear fuel pellets, a KUKA arm, cherry blossom). Word matches seen: grocery coupons for "bond
  coupon", a boat named SERVER, a rose for bonds, the Uzbek "last bell" for IPOs. 33 of 48 at 50, the other 15 at
  48-49: the demo search has little left for them.
- **More B2B brand terms** (19-20 Nov): SYF, OXY (OxyChem, Anadarko), AWK (state subsidiaries), STLD, MOS (Esterhazy,
  Riverview), APA, COHR (II-VI), EQT (EQT Plaza), GPN (TSYS, Heartland), VLTO (Pantone, Videojet, X-Rite), P (Pure
  Storage: "Everpure" is its new name but the word also names Pentair water filters, so it is not a term), SBAC, BRO,
  CINF, EME, EG, TECH; then UHS (its hospitals: George Washington University Hospital, Henderson, Centennial Hills,
  Texoma...), DOV, ROP, CPAY, TPL, GL, IEX (Hale fire pumps). Commons + Openverse: 9 best, 23 reserve (Pantone swatches,
  EQT Plaza, the TSYS campus, OxyChem plants, UHS hospitals, Hale pump panels); Unsplash: 5 Pantone photos. Rejected:
  union events for American Income Life, a Toowoomba hospital for "Henderson Hospital". VLTO 0 -> 10, UHS 0 -> 10, IEX
  0 -> 4. Nothing for Dover, Roper, Corpay, Texas Pacific Land.
- Bank (20 Nov): 6,705 photos; companies 4,321 (210 at target, 84 with none; famous average 26.2, 35 of 50 at 30),
  topics 1,837, sectors 547. 345 Unsplash download counts pending.
- **Rounds 24-25** (20 Nov): 93 + 92 short searches for the 15, then 12, under 50 (container restarts and the 2-hour limit
  cut three pieces; nothing lost). Grade 3: a residential tower, a water treatment plant from the air, Electrify America
  chargers, hands on a spreadsheet, a champagne toast, a passport with miniature travellers. Commons gave events, charts,
  a fur-auction report for "sales report", the Oval Office for jobs, an AI-generated image of aliens for AI. 38 of 48 at
  50, the other 10 at 49. Round 26 drafted (65 searches, `new_r26.json` in the scratchpad).
- **Commons by exact category** (`grow_commons_cat.py`, scratchpad): the brand collector rejected a category named
  exactly as a 3+ word term when it held no business word (the "Da Vinci Surgical System" category). Now a hit in a
  category equal to the term passes: 4 best (da Vinci robots, HPE's America Center, a carrier under construction at
  Newport News), 10 reserve (FP&L lines, SCE, Pratt & Whitney HQ). ISRG 0 -> 3.
- **HQ, plant and product-line terms** (20 Nov): 19 zero-photo companies (EOG: Heritage Plaza; HWM: Alcoa wheels; VRT:
  Liebert; OMC: BBDO, TBWA; CIEN: Ciena 6500; IQV: Quintiles; J: CH2M Hill; ASTS: BlueWalker 3...) and the 15 famous ones
  under 30 (TSMC Fab 12, 50 Hudson Yards for BlackRock, Adobe towers, Pfizer HQ, VMware campus...). The collectors take
  `TERMS_FROM=<json>` to search only the new terms. 82 candidates: 6 best (a Ciena 6500, 3 TSMC Fab 12 night views,
  50 Hudson Yards, the Adobe towers), 14 reserve. Rejected: Erie Insurance ceremonies, the Burndy Library (not Burndy),
  BBDO talks and office dogs, the CH2M Hill Alumni Center, Blackrock in Dublin, Manila Imperial Motor Sales for Mastercard.
- Bank (20 Nov, evening): 6,743 photos; companies 4,353 (213 at target, 78 with none; famous average 26.5, 38 of 50 at
  30), topics 1,841, sectors 549. 346 Unsplash download counts pending.
- **Rounds 26-27** (20 Nov): 55 + 71 short searches for the 10, then 8, topics at 49 (two pieces cut by the 2-hour
  limit). Grade 3: a Christmas shopping crowd on the Meir in Antwerp (consumer), an open lock on a laptop
  (cybersecurity), a plumber at work (jobs). Commons gave events (GDC registration, OPEC seminars, campaign rallies), a
  rufous hornero's nest for bonds and college linebackers for "bonds". 41 of 48 at 50, the other 7 at 49.
- **B2B terms, subsidiaries and old names** (20 Nov): 19 zero-photo companies (MSCI: 7 World Trade Center, its HQ;
  VRSK: Verisk HQ, 545 Washington Boulevard; Arch, Assurant, Broadridge, Camden, Kimco, Regency, Tyler, Unity, Ventas...)
  and 70 companies with 1-9 photos and no `brands.json` entry got terms (Amcor: Bemis, Parafilm; CRH: Ash Grove Cement,
  Oldcastle, Tarmac quarry; ADI: Maxim, Linear Technology; KKR: 30 Hudson Yards; BX: 345 Park Avenue; Aon: Leadenhall
  Building, Aon Center Chicago; ITW: Hobart mixer, Miller welder; PCA box certificates; Iron Mountain shredding
  trucks...). Commons + Openverse: 207 candidates, 7 best (Parafilm, Ash Grove's Chanute plant and a night view, an Iron
  Mountain truck, the Leadenhall Building, 7 WTC, Verisk HQ), 42 reserve. Rejected: name clashes (snowflakes, xylem
  tissue, "AmCor" blood drives, the Hartford Courant, UK Prudential, Michel-Schlumberger winery, Elizabeth Vale), company
  picnics, interns' rocket launches, political visits, protests, trade-show booths, the old 7 WTC. Still nothing for
  Arch, Assurant, Broadridge, Camden, Kimco, Regency, Tyler, Unity, Ventas and the other REITs and insurers.
- Bank (20 Nov, night): 6,791 photos; companies 4,398 (219 at target, 74 with none; famous average 26.5, 38 of 50 at 30),
  topics 1,844, sectors 549. 345 Unsplash download counts pending.
- **Round 28** (21 Nov): 84 searches for the 7 topics at 49 gave nothing (a Financial Times flat-lay and an Amazon packing
  line, both 2). The demo search has nothing left for them: ai, bonds, earnings, investing, oil, politics, sector-tech.
- **Companies from Wikidata's links** (21 Nov): two collectors (scratchpad) find a company's Commons categories through
  Wikidata instead of its name. `wd_linked.py` lists what the company's own item names (subsidiaries P355, things it
  owns P1830, products P1056, HQ P159); `wd_owned.py` asks the query service (query.wikidata.org; it rate-limits to one
  request a minute under load) for items naming the company as owner P127, operator P137, parent P749 or maker P176.
  The categories were chosen by eye (left out: cities, product classes, shareholdings such as BlackRock's, businesses
  sold since, portfolio companies of KKR and Apollo); `grow_wd_cat.py CATS.json OUT.json` crawls each one level deep
  through the build's own `score()`. 527 candidates graded by eye: 37 best, 192 reserve. Best: the CBOT trading pit
  and building (CME), Willis Tower (BX), Frontier (HPE), Limerick (CEG), Westlake Shopping Center (KIM, its first
  photo), a Twilio SendGrid sign, Waters' Acquity UPLC, Clover Station (Fiserv), the JFK carrier in dry dock and its
  bow section (HII), Honeywell's 757 test aircraft, a Tyco van (JCI), Royal Bank Plaza, a Snapchat Spectacles vending
  machine, a Harris Falcon III radio, Cobra Dane, Moderna and BioNTech vials, the Fermi and Hope Creek plants, Sea
  Hunter (LDOS), a Wolt courier (DASH), an UGG store, a HOKA Bondi, Escondida and Yanacocha, a Vale locomotive.
  Rejected: wrestling and concerts (TKO, Live Nation venues), soldiers with the products (L3Harris, RTX), PMI's
  Parliament packs abroad (Altria sells it only in the US), postcards, trade-show booths, people.
- Bank (21 Nov): 6,955 photos; companies 4,562 (251 at target, 69 with none; famous average 26.6, 39 of 50 at 30),
  topics 1,844, sectors 549. 345 Unsplash download counts pending.
- **More Wikidata routes, B2B Unsplash pass** (21-22 Nov), all collectors in the scratchpad, every candidate graded by eye:
  - Unsplash brand build for 78 thin B2B companies with their new terms: not one new photo in the 68 it reached (stopped
    at the hourly limit before VTR, VRSK, WST, WRB, WAT, WDAY, WTW, XYL, ZBRA, VRSN). Unsplash has nothing for them.
  - Two hops through subsidiaries (`wd_owned2.py`: items a subsidiary owns or operates): 2 best (Plant Vogtle under
    construction, a GE Evolution demonstrator for Wabtec), 20 reserve (HQ buildings for EOG and Williams, Moss Landing,
    the AES Electric Building).
  - HQ street address from Wikidata (P6375) searched on Commons (`grow_address.py`): 2 reserve of 43 (Apollo's "9" at 9
    West 57th, Shopify's 150 Elgin). Commons rarely names photos by address, and Wikidata's are often stale (AIG, BMS
    and T. Rowe Price moved).
  - Main images (P18) of items a company or its subsidiaries own, operate or make (`wd_p18.py`, `wd_p18_cands.py`; the
    query service now answers 429 to the shared egress, so it uses the API's `haswbstatement` search), items chosen by
    eye: 6 best (a Taser X26, BioNTech and Moderna vials, a Dexcom G6, an FPL EVolution charger, Valero's Jean-Gaulin
    refinery from the air), 26 reserve.
  - Commons structured data: files that depict (P180) the company or a linked item chosen before (`grow_depicts.py`):
    4 best of 145 (Thermo Fisher's Vilnius plant, a Tyvek-wrapped house, Georgia Power's tower, Williams Tower's
    entrance: Williams' first photo, the tower bears its name and houses Transco), 43 reserve. Depicts tags are noisy:
    concerts, fighters, soldiers with L3Harris kit, sponsored race cars, Zoom calls, a sex toy filed under DuPont.
- Bank (22 Nov): 7,038 photos; companies 4,645 (263 at target, 67 with none; famous average 26.7, 39 of 50 at 30),
  topics 1,844, sectors 549. 345 Unsplash download counts pending.

## Videos (18 Nov 2026, new)
- Pablo: "vamos a empezar a meter videos tambien en el banco". He chose **both orientations** (vertical for Reels/
  TikTok/Shorts and horizontal), **10 clips per topic and sector** to start (~480; companies later), and **Pixabay** as the
  main source. Pexels still issues no keys, Unsplash has no video, and Commons video is scarce and documentary.
- `videos.py` (tests: `test_videos.py`, 11, offline). Linked, not copied. Sources: `PixabayVideo` (needs
  **`PIXABAY_API_KEY` as an environment variable**: the key goes in the query string, so a network secret cannot carry
  it; Pablo first tried a network secret with host `pixabay.api.com` (wrong host as well) and was told to delete it and
  use an environment variable, then start a new session), `CommonsVideo` (CC0/PD/CC BY only, no BY-SA: a reel cut from
  an SA clip would be SA as a whole; the file name must name the search; no news/speeches/events/seizures/crashes)
  and `NasaVideo` (space shots only, launch providers' footage out). Rules: real footage, >= 1080p, 4-60 s (Commons and
  NASA 180), every search word in tags/file name, 2 per uploader per subject, a clip used once in the bank, up to 3
  vertical clips first, `vertical_crop_ok` for 4K horizontals. Searches: the topic's catalog shots, the ones that gave
  published stock photos first; a subject stops searching at target + 3 shots with candidates and 3 verticals (max 25
  searches per source).
- Files: `bank/video_manifest.json`; for the chat `bank/videos/index.json` + `bank/videos/<ID>.json`. Grades in
  `bank/video_review.json`, apart from the photos' `review.json` so a photo session and a video session never edit the
  same file (Pixabay/NASA published unless graded < 3, Commons only grade 3). Review: `python videos.py sheets
  DIR` (3 frames per clip: NASA's own stills, Commons thumbnails with `seek=`, Pixabay via ffmpeg from the tiny file),
  `python videos.py grade G.json DIR` (same format as review.py; reindexes). A video session touches only `videos.py`,
  `test_videos.py`, `bank/video_manifest.json`, `bank/video_review.json`, `bank/videos/` and its own CLAUDE.md section. `CAROUSEL_CHAT.md` has the chat block.
- Trial without Pixabay (Commons + NASA, oil/tariffs/space, in a scratch copy of the bank): Commons fills places with
  word matches and news (a barrel organ for "oil barrel", seized tankers), hence the stricter rules above; good ones
  exist (Port of Cork aerials, Rotterdam locks). A space trial first hung: NASA lists some asset addresses with raw
  spaces, and each one cost ~150 s of retries (fixed: `NasaVideo.href`); it then took a few minutes and gave 10 clips,
  3 of them good (Artemis II with the Moon, vertical; Webb encapsulation; a Mars panorama). NASA titles with
  trailers, talks, interviews, recruitment or launch providers are now left out. Nothing built in the real bank yet.
- **First real build (18-19 Nov, PR #19)**: `PIXABAY_API_KEY` and `WIKIMEDIA_TOKEN` are environment variables now. Four
  passes (`build`, then `build --redo` three times: a redo keeps the published clips and fills the free places), every
  pick graded by eye on the sheets: 1,189 clips graded, **339 published** (grade 3; 324 plain, 526 rejected): 330 Pixabay,
  7 Commons, 2 NASA; 41 vertical, 298 horizontal. 6 subjects at 10, most at 7-9; thin: nuclear 2, bonds, bull-market,
  cybersecurity, fed, gold and politics 4; **ev and quantum 0** (Pixabay has next to no real footage of EV charging or
  quantum hardware: "electric" brings guitars, trams and light bulbs; quantum brings light trails and microscopes; Commons
  has IBM promos and animations). The chat is told to use the photos for a subject with few or no clips.
- Pixabay's search is loose and its tags are generic, so about 1 pick in 3 is grade 3. Word matches seen: flamingos and
  eagles for "bill", cattle and yaks for "bull", a bear for "bear market" (kept: it reads as the idea), swans and cats for
  "bond"/"nest egg", olive oil and gun barrels for oil, waterfalls for "vault", a red-crowned crane for "crane", electric
  guitars for EVs. Commons still gives news, promos and animations (Trump announcements, IBM shorts): nearly all rejected.
- Pixabay searches now ask for 200 results (`per_page`, its maximum) instead of 30: with 30, a search like "electric car
  charging" held no clip whose tags name the search. A container restart cut one pass; nothing lost (the manifest is saved
  per subject, answers are cached in `.cache/stock/`).
- **Video-only searches** (19 Nov): `VIDEO_SHOTS` in `videos.py` gives the 13 thinnest subjects 4-9 searches of their
  own (tried on Pixabay first, kept only if they returned clips whose tags name them), searched before the catalog
  shots; `catalog.json` stays the photos'. A subject can also carry `video_shots`. Rebuilt with `--redo --only` the 13
  and graded by eye: 83 new picks, 14 grade 3 (cash counting, a money counter, an abandoned mall, shuttered shops, a
  stressed man with bills, an abandoned factory, Empire State aerials, a circuit board, a server room, cooling towers,
  a "vote today" banner, a microscope). Bank: **353 clips**. Now: ev 0, quantum 1, nuclear 3, bonds, cybersecurity and
  gold 4, politics and robotics 5; the rest 6-10. Pixabay brought word matches again: "e-scooter" parks with tiny
  riders, "plug" -> hemp, "charging" -> laptops, "treasure" -> skull maps and the Treasure Coast, "control room" ->
  recording studios, "trader" -> a market seller in Lagos, "atom" -> starfields. Pixabay has little more to give for
  these: EVs and quantum need another source (Pexels, if it issues keys again). Videos never mix into `bank/index.json`.

- **Companies** (20 Nov, Pablo: "ahora mete vídeos para las empresas"): `videos.py build --kind company`. Only the
  companies with `brands.json` terms (457), since stock footage is tagged with brands, not company names; up to 8
  terms searched each on Pixabay and Commons (NASA leaves providers' footage out). A clip counts only if its tags (Commons:
  file name) name a brand term or the full name: not the short name, since tags are single words ("Arm" -> arms).
  Target `COMPANY_TARGET` 5, `FAMOUS_TARGET` 10 for the famous ones (my proposal, not Pablo's: change if he asks). The
  index gives every company `sector` and, below target, `fill_from` = its sector; a rule tells the chat a company clip
  shows its brand as the uploader tagged it, never as the company's own footage or an advert. One build plus a refill
  from the cache, every pick graded by eye: 280 picks (Pixabay 118, Commons 128 in the first pass), **40 published in
  25 companies** (SpaceX 5; Apple, Microsoft, Disney 3; Nvidia, Google, Boeing, Dell, Las Vegas Sands 2; 16 with 1);
  432 companies have none. Pixabay tags brand words loosely: "amazon" -> rainforests, parrots, piranhas; "shell" ->
  snails and turtles; "on" -> anything; "zoom" -> the Moon; "hilton" -> Hilton Head beaches; "napa" -> Napa Valley;
  "ford" -> rivers; "sony" -> any clip shot on a Sony camera. Commons brings news, bodycam footage ("Taser", "Apple
  Watch robbery"), politicians (Biden at Costco, a DoorDash order at the White House), adverts and trailers, unboxings
  with overlays: nearly all rejected. Good ones: Falcon 9 launches, a GeForce RTX card on a turntable, Dell laptops in
  360°, Xbox controllers, MacBooks, Boeing 787/747 in flight, Delta and United jets, a Coca-Cola bottle, Marina Bay
  Sands, Disney castles, Monopoly. Bank: **393 clips** (topics and sectors 353, companies 40).
- **Video-only terms for ambiguous brands** (20-21 Nov): `VIDEO_TERMS` in `videos.py` gives 27 companies whose brand is
  a common word in tags (Amazon, Shell, On, Zoom, Hilton, NAPA, Target, Ford, Sony, Toyota, Nike, IBM, GM, Apple, Meta,
  Google, TKO, SpaceX, Microsoft, Delta, United, Southwest, Norwegian, Constellation, Monster, Yum, Uber) multi-word or
  product searches ("shell gas station", "amazon box", "iphone", "xbox", "falcon 9 rocket", "united airlines"). For them
  these replace the `brands.json` terms in video builds, and a clip counts only if its tags hold every word of one term,
  or the company's full name when that is more than one word ("Shell", "Amazon", "Zoom" and "On" are the bare brand
  word). A one-word term must be a product nobody else uses: "corvette" brought a warship, now "chevrolet corvette".
  Tried on Pixabay and Commons first: nearly all return nothing usable (Pixabay has no Shell, Toyota, Nike, Target,
  Hilton, Starbucks or McDonald's footage; Commons brand clips are mostly CC BY-SA, 720p or over 3 minutes, all
  excluded). Two rounds graded by eye: company clips 40 -> **53 in 26 companies** (Apple 8, SpaceX 7, Sony 3, United 3,
  Microsoft 3; new: MacBooks, iPhones, Sony G Master lenses in 360°, United and Delta jets, a Norwegian cruise ship deck,
  a Falcon 9 twilight launch). The terms stop look-alikes: Shell's snails, Amazon's rainforests and Zoom's Moon are gone.
  Bank: **406 clips** (topics and sectors 353, companies 53).
- **Companies without brand terms** (21 Nov, Pablo: "mete vídeos para las empresas sin marcas en brands.json"): by then
  only 36 companies had no `brands.json` entry (34 in the photo manifest with a name: 3M, Accenture, Air Products,
  Duke Energy, Exelon, Equinix, Linde, Public Storage, regional banks, Williams-Sonoma...). Each got `VIDEO_TERMS`
  (full names, products and subsidiaries: "duke energy", "gorilla glass", "pottery barn", "public storage", "fedex
  freight"; never a bare word: "d-wave" brought sea waves, "eaton" the Eaton wildfire, "cintas" the Indonesian "cinta").
  Pixabay and Commons had **nothing usable for any of them**: one pick (unbranded sticky notes for 3M, graded 2). They
  are now in the video index with no clips and `fill_from` = their sector. Bank: 406 clips; all 491 companies in the
  video index, 26 with clips of their own.
- **Second refill of the thin topics** (22 Nov): `build --redo --only` the 42 topics and sectors under 10 (it keeps the
  published clips and searches the catalog's newer short searches too). 122 new picks graded by eye: **19 grade 3** (a
  container ship on a river, the Great Wall, dollar bills and coins, a military pontoon crossing, the Texas capitol,
  scientists in a lab, a cardboard press and conveyors, an assembly line, a wifi router, a Duisburg steel plant, a copper
  mine, a cruise ship, an airport apron, a wheat field, a wind farm), 39 grade 2. Word matches again: a church for IPOs,
  Chernobyl and windmills for nuclear, sea waves for "vault", a disco laser and a golf disc ("atom") for quantum, an
  Indian flag and a vaccination for US politics, a guitar for EVs. Topics and sectors 353 -> **372 clips** (10 of 48 at
  10); still thin: ev 0, quantum 2, nuclear 3, gold 4, bonds 5, cybersecurity 5. Bank: **425 clips**.
- **Third refill of the thin topics** (23 Nov): the same `--redo --only` pass for the 38 still under 10. 100 new picks
  graded by eye, only **10 grade 3** (the Mexican stock exchange, a coin spinning on red, the Hungarian parliament, an
  office calculator and papers, a man walking in a parking garage, a power-plant pier, a chemistry lab, Portofino's
  harbour, a shopping mall's dome, Rotterdam's port). Word matches as before (Chernobyl and wind farms for nuclear, a
  guitar and a drain for EVs, an Indian flag for US politics). Topics and sectors 372 -> **382 clips**. The cache is
  nearly spent: each refill now adds ~10.
- Next for company videos: another source with brand footage (Pexels, if it issues keys again). Pixabay and Commons
  have little more.

## Next work (in order)
1. Topics, sectors and the brand pass are done. When Unsplash production is approved, a rebuild of the brand
   terms fixed after their first search (Abbott, Cisco, Casey's, Chipotle, McCormick, On, P&G, Qualcomm, Roku)
   would find better photos for them. Then grade; look at everything by eye (`python review.py sheets --stock`: grade 1-2 hides a photo, and
   wrong brand terms get fixed in `brands.json`), fix topic searches in `catalog.json`, grade any new Commons
   photos (`python review.py sheets` + `grade`), `index`, `credits`, `python dashboard.py`, commit and push.
   **Unsplash production**: applied on 5 Nov (in review). Once approved (`X-Ratelimit-Limit: 1000`), the company
   brand pass takes about half an hour.
2. Done: PRs #1 to #5 merged into `main` (#5 on 14 Nov: 5,454 photos, 631 subjects). Later work goes in
   through a new PR. Next for topics: finish the second refill (the 8 above), then more refill passes from the
   cache (`--redo`, free) with grading after each, and new short searches for the thinnest (quantum, earnings, ipo).
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
