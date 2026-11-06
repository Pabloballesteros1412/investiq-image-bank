"""Offline tests of the image bank (no network): python -m unittest discover -p "test_*.py" """
import json, tempfile, unittest
from pathlib import Path

import image_bank as B

UP = "https://upload.wikimedia.org/wikipedia/commons/a/ab/"


def cand(file, w=4000, h=3000, lic="cc-by-sa-4.0", short="CC BY-SA 4.0", year=2021, cats=(), mime="image/jpeg", restr=()):
    name = file.split(":", 1)[-1].replace(" ", "_")
    return {"file": file, "w": w, "h": h, "mime": mime, "orig": UP + name, "page": "https://commons.wikimedia.org/wiki/" + name,
            "licence": short, "licence_code": lic, "licence_url": "https://creativecommons.org/licenses/by-sa/4.0", "author": "Jane Doe",
            "year": year, "categories": list(cats), "restrictions": list(restr), "description": ""}


SP500_WIKITEXT = """Intro text.
{| class="wikitable sortable" id="constituents"
! Symbol !! Security !! GICS Sector !! GICS Sub-Industry
|-
|{{NyseSymbol|MMM}}
|[[3M]]
|Industrials
|Industrial Conglomerates
|-
| {{NasdaqSymbol|GOOGL}} || [[Alphabet Inc.|Alphabet Inc. (Class A)]] || Communication Services || Interactive Media
|-
| {{NasdaqSymbol|GOOG}} || [[Alphabet Inc.|Alphabet Inc. (Class C)]] || Communication Services || Interactive Media
|-
|{{NyseSymbol|BRK.B}}
|[[Berkshire Hathaway]]
|[[Financials]]
|Multi-Sector Holdings
|-
|| {{BZX link|CBOE}}
|| [[Cboe Global Markets]]
|| Financials 
|| Financial Exchanges & Data 
|}
{| class="wikitable" id="changes"
|-
| not a constituent || [[Old Co]] || x
|}"""


class Fake:
    """Wikipedia, Wikidata and Commons answers for the tests."""

    def __init__(self, n_sp=3):
        self.calls = []
        self.n_sp = n_sp

    def sp500(self):
        rows = B.parse_sp500(SP500_WIKITEXT)
        return rows + [{"ticker": f"X{i}", "name": f"Filler {i}", "wiki": f"Filler {i}", "sector": "Utilities"} for i in range(self.n_sp)]

    def wikidata_ids(self, titles):
        return {t: {"3M": "Q1", "Alphabet Inc.": "Q2", "Berkshire Hathaway": "Q3", "Cboe Global Markets": "Q4"}.get(t) for t in titles}

    def company_categories(self, names):
        return {n: "Cboe" for n in names if n == "Cboe Global Markets"}

    def search_entity(self, name, ticker):
        return "Q9" if ticker == "TSM" else None

    def articles(self, titles):
        return {t: {"3M": "Q1", "Alphabet": "disambiguation"}.get(t) for t in titles}

    def entities(self, qids, props="labels|claims|sitelinks"):
        ents = {"Q2": {"sitelinks": {"commonswiki": {"title": "Category:Alphabet Inc."}}},
                "Q3": {"claims": {"P910": [{"mainsnak": {"datavalue": {"value": {"id": "Q30"}}}}]}},
                "Q30": {"claims": {"P373": [{"mainsnak": {"datavalue": {"value": "Berkshire Hathaway"}}}]}},
                "Q1": {"claims": {"P373": [{"mainsnak": {"datavalue": {"value": "3M"}}}],
                                  "P18": [{"mainsnak": {"datavalue": {"value": "3M HQ Maplewood.jpg"}}}],
                                  "P169": [{"mainsnak": {"datavalue": {"value": {"id": "Q100"}}}, "qualifiers": {"P582": [{}]}},
                                           {"mainsnak": {"datavalue": {"value": {"id": "Q101"}}}}]}},
                "Q101": {"labels": {"mul": {"value": "William Brown"}}},
                "Q100": {"labels": {"en": {"value": "Old Boss"}}}}
        return {q: ents.get(q, {}) for q in qids if q}

    def search(self, q):
        self.calls.append(q)
        if q == '"William Brown"':
            return [cand("File:Someone else.jpg"), cand("File:William Brown at the Wedding 2023.jpg", w=2000, h=3000),
                    cand("File:William Brown 2023.jpg", w=2000, h=3000, cats=["3M people"], restr=["personality"])]
        if q.startswith("3M"):
            return [cand(f"File:{q} view {i}.jpg") for i in range(3)] + [cand("File:Unrelated tower.jpg")]
        return [cand(f"File:{q} photo {i}.jpg") for i in range(4)]

    def info(self, titles):
        return {t: cand(t) for t in titles if "missing" not in t}

    def category_files(self, cat, keys=()):
        files = [(f"File:3M building {i}.jpg", "3M") for i in range(1, 4)]            # near-duplicates: one kept
        files += [(f"File:3M plant {c} site.jpg", "3M factories") for c in "abc"]       # same subcategory: two kept
        files += [("File:3M logo.png", "3M"), ("File:Post-it notes macro.jpg", "Post-it"), ("File:Scotch tape roll.jpg", "Scotch tape")]
        return files


MINI = {"style": "Photo.", "negative": "text", "subjects": [
    {"id": "MMM", "kind": "company", "name": "3M", "tickers": ["MMM"], "shots": [{"id": "hq", "q": "3M Center", "scene": "3M Center campus"}]},
    {"id": "gold", "kind": "topic", "name": "Gold", "aliases": ["bullion"], "shots": ["gold bars", "gold coins"] + [f"gold thing {i}" for i in range(8)]},
] + [{"id": sid, "kind": "sector", "name": g, "gics": g, "shots": [f"{g} view {i}" for i in range(10)]} for g, sid in B.SECTORS.items()]}
B.norm_catalog(MINI)


class Catalog(unittest.TestCase):
    def test_real_catalog_and_extras_are_valid(self):
        cat = json.loads(B.CATALOG.read_text(encoding="utf-8"))
        self.assertEqual(B.check_catalog(cat, B.load_extras()), [])
        kinds = [s["kind"] for s in cat["subjects"]]
        self.assertGreaterEqual(kinds.count("topic"), 35)
        self.assertEqual(kinds.count("sector"), 11)
        self.assertGreaterEqual(len(B.load_extras()), 80)

    def test_problems_are_reported(self):
        bad = {"subjects": [{"id": "x", "kind": "topic", "name": "X", "shots": ["a", "a"]}]}
        p = B.check_catalog(bad, [{"ticker": "Z", "name": "Z", "sector": "Nope"}])
        for words in ("2 shots", "repeated shot", "missing sector subjects", "GICS sector"):
            self.assertTrue(any(words in x for x in p), words)

    def test_plain_string_shots(self):
        self.assertEqual(B.norm_shot("Gold bars, London"), {"id": "gold-bars-london", "q": "Gold bars, London", "scene": "Gold bars, London"})


class Universe(unittest.TestCase):
    def test_sp500_table(self):
        rows = B.parse_sp500(SP500_WIKITEXT)
        self.assertEqual([r["ticker"] for r in rows], ["MMM", "GOOGL", "GOOG", "BRK-B", "CBOE"])
        self.assertEqual((rows[1]["wiki"], rows[1]["name"], rows[1]["sector"]), ("Alphabet Inc.", "Alphabet Inc. (Class A)", "Communication Services"))
        self.assertEqual(rows[3]["sector"], "Financials")
        self.assertEqual((rows[4]["wiki"], rows[4]["sector"]), ("Cboe Global Markets", "Financials"))  # rows written "|| cell"

    def test_universe(self):
        with tempfile.TemporaryDirectory() as d:
            src = Fake(n_sp=400)
            extras = [{"ticker": "TSM", "name": "TSMC", "wiki": None, "sector": "Information Technology"},
                      {"ticker": "MMM", "name": "3M again", "wiki": "3M", "sector": "Industrials"}]
            uni = {e["id"]: e for e in B.build_universe(MINI, src, d, extras, log=lambda *_: None)}
            self.assertEqual(uni["GOOGL"]["tickers"], ["GOOGL", "GOOG"])          # two share classes, one company
            self.assertEqual(uni["GOOGL"]["name"], "Alphabet Inc.")
            self.assertEqual(uni["BRK-B"]["wikidata"], "Q3")
            self.assertEqual(uni["GOOGL"]["commons_category"], "Alphabet Inc.")      # from the Commons sitelink
            self.assertEqual(uni["BRK-B"]["commons_category"], "Berkshire Hathaway") # from the main category (P910)
            self.assertEqual(uni["CBOE"]["commons_category"], "Cboe")                # a Commons category named after it
            self.assertEqual((uni["MMM"]["ambiguous"], uni["GOOGL"]["ambiguous"]), (False, True))
            self.assertEqual((uni["MMM"]["commons_category"], uni["MMM"]["ceo"]), ("3M", "William Brown"))  # current CEO only
            self.assertEqual(uni["TSM"]["wikidata"], "Q9")                           # found by name and ticker
            self.assertEqual(sum(1 for e in uni.values() if "MMM" in e["tickers"]), 1)  # an extra already in the S&P 500
            # a hand correction survives the next run
            u = json.loads((Path(d) / "universe.json").read_text())
            next(e for e in u["companies"] if e["id"] == "MMM").update(commons_category="3M Company", manual=["commons_category"])
            (Path(d) / "universe.json").write_text(json.dumps(u))
            uni = {e["id"]: e for e in B.build_universe(MINI, src, d, extras, log=lambda *_: None)}
            self.assertEqual(uni["MMM"]["commons_category"], "3M Company")

    def test_a_broken_wikipedia_table_stops_the_run(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(RuntimeError):
            B.build_universe(MINI, Fake(n_sp=0), d, [], log=lambda *_: None)

    def test_wikidata_helpers(self):
        ent = {"claims": {"P414": [{"qualifiers": {"P249": [{"datavalue": {"value": "BRK.B"}}]}}]}}
        self.assertTrue(B.has_ticker(ent, "BRK-B"))
        self.assertFalse(B.has_ticker(ent, "BRK-A"))


class Choosing(unittest.TestCase):
    SHOT = {"id": "hq", "q": "Apple Park", "scene": "Apple Park"}

    def test_licences(self):
        self.assertEqual(B.licence_kind(cand("a", lic="cc-by-sa-4.0")), "by-sa")
        self.assertEqual(B.licence_kind(cand("a", lic="cc-by-2.0", short="CC BY 2.0")), "by")
        self.assertEqual(B.licence_kind(cand("a", lic="cc0", short="CC0")), "cc0")
        self.assertEqual(B.licence_kind(cand("a", lic="pd", short="Public domain")), "pd")
        self.assertIsNone(B.licence_kind(cand("a", lic="gfdl", short="GFDL")))

    def test_rejections(self):
        S = self.SHOT
        self.assertIsNone(B.score(cand("File:Small.jpg", w=1200, h=800), 0, S))
        self.assertIsNone(B.score(cand("File:Apple logo.png", mime="image/png"), 0, S))
        self.assertIsNone(B.score(cand("File:Map of Cupertino.jpg"), 0, S))
        self.assertIsNone(B.score(cand("File:A.jpg", lic="gfdl", short="GFDL"), 0, S))
        self.assertIsNone(B.score(cand("File:A.jpg"), 0, S, used={"File:A.jpg"}))
        self.assertIsNone(B.score(cand("File:A.jpg"), 0, S, no_sa=True))
        self.assertIsNone(B.score(cand("File:A.tif", mime="image/tiff"), 0, S))      # thumbnails named differently
        self.assertIsNone(B.score(cand("File:" + "x" * 170 + ".jpg"), 0, S))
        self.assertIsNone(B.score(cand("File:Some tower.jpg"), 0, {**S, "must": ["3m"]}))
        self.assertIsNotNone(B.score(cand("File:Tower.jpg", cats=["3M buildings"]), 0, {**S, "must": ["3m"]}))
        self.assertIsNotNone(B.score(cand("File:Apple Park plant.jpg"), 0, S))     # "plan" is not "plant"

    def test_ranking(self):
        S = self.SHOT
        plain = B.score(cand("File:A.jpg"), 0, S)
        self.assertGreater(B.score(cand("File:B.jpg", cats=["Featured pictures on Wikimedia Commons"]), 3, S), plain)
        self.assertEqual(B.score(cand("File:C.jpg", w=3000, h=4000), 0, S), plain)       # portrait crops well to 4:5
        self.assertLess(B.score(cand("File:P.jpg", w=6000, h=2000), 0, S), plain)        # a panorama does not
        self.assertLess(B.score(cand("File:D.jpg", year=1975), 0, S), plain)
        self.assertGreater(B.score(cand("File:F.jpg", lic="cc-by-4.0", short="CC BY 4.0"), 0, S), plain)

    def test_links_and_sizes(self):
        url, prev, size = B.links(cand("File:Big photo.jpg", w=4000, h=3000))
        self.assertEqual(url, UP.replace("commons/", "commons/thumb/") + "Big_photo.jpg/1920px-Big_photo.jpg")
        self.assertEqual((prev.endswith("/500px-Big_photo.jpg"), size), (True, [1920, 1440]))
        url, _, size = B.links(cand("File:Tall.jpg", w=3000, h=4000))
        self.assertEqual((url.endswith("/1280px-Tall.jpg"), size), (True, [1280, 1707]))  # narrowest that keeps 1500 px of height
        url, _, size = B.links(cand("File:Mid.jpg", w=1800, h=1200))
        self.assertEqual((url, size), (UP + "Mid.jpg", [1800, 1200]))                    # smaller than 1920: the original

    def test_descriptions(self):
        self.assertEqual(B.describe(cand("File:Apple_Park_aerial_2019-05-03.jpg"), "x"), "Apple Park aerial")
        self.assertEqual(B.describe(cand("File:IMG_4521.JPG"), "fallback"), "fallback")
        self.assertEqual(B.stem("File:Apple Park 03.jpg"), B.stem("File:Apple Park 7.jpg"))


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bank = Path(self.tmp.name)
        self.src = Fake()
        uni = [{"id": "MMM", "name": "3M", "tickers": ["MMM"], "sector": "Industrials", "commons_category": "3M",
                "image": "3M HQ Maplewood.jpg", "ceo": "William Brown", "wikidata": "Q1"},
               {"id": "ZZZ", "name": "Zeta Corp", "tickers": ["ZZZ"], "sector": "Utilities", "wikidata": None}]
        (self.bank / "universe.json").write_text(json.dumps({"companies": uni}))

    def tearDown(self):
        self.tmp.cleanup()

    def run_build(self, **kw):
        return B.build(MINI, self.bank, self.src, log=lambda *_: None, **kw)

    def test_company_photos(self):
        m = self.run_build(only="MMM")
        ph = m["MMM"]["photos"]
        self.assertEqual(len(ph), B.TARGET)
        self.assertEqual([p["how"] for p in ph[:3]], ["catalog", "Wikidata main image", "Wikidata CEO"])
        self.assertEqual((ph[2]["shows"], ph[2]["person"], ph[2]["focus"]), ("William Brown, 3M CEO (per Wikidata)", True, [0.5, 0.33]))
        self.assertIn("restrictions: personality", ph[2]["flags"])
        files = [p["file"] for p in ph]
        self.assertEqual(len(files), len(set(files)))
        self.assertEqual(sum("3M building" in f for f in files), 1)                     # near-duplicates
        self.assertLessEqual(sum(p.get("category") == "3M factories" for p in ph), 2)   # two per subcategory
        self.assertNotIn("File:3M logo.png", files)
        self.assertNotIn("File:Unrelated tower.jpg", files)                             # searches must name the company
        self.assertEqual(ph[0]["shows"], "3M Center view 0")                            # what the photo is, not the wish

    def test_ceo_image_and_telling_category_photos(self):
        c = {"name": "3M", "tickers": ["MMM"], "commons_category": "3M", "ceo": "William Brown", "ceo_image": "WB portrait.jpg"}
        src = Fake()
        src.category_files = lambda cat, keys=(): [("File:P20210825AS-1824 (51645285729).jpg", "Products of 3M"),
                                          ("File:3M plant site.jpg", "3M")]
        ph = B.company_photos(c, [], src, set())
        self.assertEqual((ph[0]["file"], ph[0]["how"]), ("File:WB portrait.jpg", "Wikidata CEO"))  # the CEO's own image
        files = [p["file"] for p in ph]
        self.assertIn("File:3M plant site.jpg", files)
        self.assertNotIn("File:P20210825AS-1824 (51645285729).jpg", files)              # a name that says nothing
        self.assertNotIn('"William Brown"', src.calls)                                  # no search needed

    def test_letters_paintings_and_short_names(self):
        letter = cand("File:Letter from William M. Brown.jpg", cats=["1865 letters"], year=1865)
        self.assertIsNone(B.score(letter, 0, {"id": "x"}))                            # old paper is not a photo
        self.assertIsNotNone(B.score(letter, 0, {"id": "x", "historic": True}))
        self.assertTrue(B.has_term("3m world headquarters", "3m"))
        self.assertFalse(B.has_term("3mm screws", "3m"))
        self.assertFalse(B.has_term("fokker f.viib-3m van de spaanse", "3m"))
        self.assertFalse(B.has_term("3m-54e submarine launched anti-ship missile", "3m"))
        self.assertTrue(B.has_term("3m's new plant", "3m"))
        self.assertTrue(B.has_term("laronde gold pouring", "gold pour"))

    def test_own_places_and_events(self):
        keys = ["Blackstone", "Blackstone Inc."]
        self.assertTrue(B.own_place(cand("File:Blackstone headquarters 345 Park Avenue.jpg"), keys))
        self.assertFalse(B.own_place(cand("File:Elm Street, East Blackstone MA.jpg"), keys))   # a town, not the firm
        abbott = ["Abbott Laboratories"]
        hz = cand("File:201407 Abbott Hangzhou Factory in HEDA.jpg", cats=["Abbott Laboratories"])
        self.assertTrue(B.own_place(hz, abbott, abbott, core="Abbott"))                # first word + its category
        self.assertFalse(B.own_place(cand("File:Abbott Hangzhou Factory.jpg"), abbott, abbott, core="Abbott"))
        bb = cand("File:Fort Wayne - Blackstone Building.jpg", cats=["Blackstone Building (Fort Wayne)"])
        self.assertFalse(B.own_place(bb, keys, ["Blackstone Inc."]))                    # ambiguous: needs the full name
        self.assertFalse(B.EVENTS.search("Infant formula"))
        self.assertTrue(B.EVENTS.search("NextEra Energy Resources 250 NASCAR races"))
        self.assertFalse(B.EVENTS.search("Apple Park"))
        self.assertTrue(B.EVENTS.search("2019 NextEra Energy 250"))                               # a race

    def test_ceo_search_needs_the_full_name(self):
        src = Fake()
        src.search = lambda q: [cand("File:William Mason Brown - Mound of Cherries.jpg"), cand("File:Brown bear.jpg")]
        ph = B.company_photos({"name": "3M", "tickers": ["MMM"], "ceo": "William M. Brown"}, [], src, set())
        self.assertFalse(any(p.get("person") for p in ph))

    def test_index_for_the_chat(self):
        self.run_build(kinds=("company", "topic"))
        self.assertGreater(B.index(self.bank, "https://example.org/bank"), 10)
        ix = json.loads((self.bank / "index.json").read_text())
        rec = {s["id"]: s for s in ix["subjects"]}
        self.assertEqual(rec["MMM"]["file"], "https://example.org/bank/subjects/MMM.json")
        self.assertNotIn("fill_from", rec["MMM"])                                       # 10 photos of its own
        self.assertEqual(rec["ZZZ"]["fill_from"], "sector-utilities")                  # fewer than 10: its sector fills in
        self.assertEqual(B.lookup("bullion", self.bank)[0]["credit"], "Jane Doe, CC BY-SA 4.0, via Wikimedia Commons")
        mmm = json.loads((self.bank / "subjects" / "MMM.json").read_text())
        p = mmm["photos"][0]
        self.assertEqual(set(p) >= {"shows", "url", "preview", "size", "focus", "credit", "licence", "source"}, True)
        self.assertTrue(any("fill_from" in r for r in ix["rules"]))
        self.assertEqual(B.credits(self.bank), 25)                          # MMM 10, ZZZ 5 (one per search naming a place: same name stem), gold 10
        self.assertIn("Jane Doe", (self.bank / "CREDITS.md").read_text())

    def test_topics_sectors_and_prompts(self):
        m = self.run_build(kinds=("topic", "sector"))
        self.assertEqual(len(m["gold"]["photos"]), 10)
        self.assertEqual(len(m["sector-energy"]["photos"]), 10)
        self.assertTrue(m["gold"]["photos"][0]["shows"].startswith("gold bars"))
        self.assertEqual(B.prompts(MINI, self.bank), 1)                                 # the company's hand-written shot
        self.assertEqual(B.prompts(MINI, self.bank, all_shots=True), 121)

    def test_incremental_exclusions_and_frozen(self):
        m = self.run_build(only="MMM")
        first = m["MMM"]["photos"][0]["file"]
        self.src.calls.clear()
        self.run_build(kinds=("company",))                                              # MMM is done: only ZZZ is searched
        self.assertTrue(all("Zeta" in q for q in self.src.calls))
        m = B.load_manifest(self.bank)
        m["MMM"].update(exclude=[first], manual=["exclude"])
        m["ZZZ"]["manual"] = True
        m["ZZZ"]["note"] = "frozen"
        (self.bank / "manifest.json").write_text(json.dumps(m))
        m = self.run_build(redo=True, kinds=("company",))
        self.assertNotIn(first, [p["file"] for p in m["MMM"]["photos"]])
        self.assertEqual(m["MMM"]["exclude"], [first])
        self.assertEqual(m["ZZZ"]["note"], "frozen")

    def test_errors_keep_previous_photos(self):
        self.run_build(only="gold", kinds=("topic",))
        def boom(q): raise OSError("network down")
        self.src.search = boom
        m = self.run_build(only="gold", kinds=("topic",))
        self.assertEqual(len(m["gold"]["photos"]), 10)
        self.assertIn("network down", m["gold"]["error"])
        self.assertNotIn("checked", m["gold"])                                          # retried on the next run

    def test_companies_need_the_universe(self):
        (self.bank / "universe.json").unlink()
        with self.assertRaises(SystemExit):
            self.run_build()

    def test_commons_answer_parsing(self):
        page = {"title": "File:Apple Park.jpg", "index": 1, "imageinfo": [{"width": 6000, "height": 4000, "mime": "image/jpeg",
                "url": UP + "Apple_Park.jpg", "descriptionurl": "https://commons.wikimedia.org/wiki/File:Apple_Park.jpg",
                "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "License": {"value": "cc-by-sa-4.0"},
                                "Artist": {"value": '<a href="//x">Daniel L. Lu</a>'}, "DateTimeOriginal": {"value": "2018-05-03 10:00"},
                                "Categories": {"value": "Apple Park|Quality images"}, "Restrictions": {"value": ""}}}]}
        c = B.candidate(page)
        self.assertEqual((c["author"], c["year"], c["orig"]), ("Daniel L. Lu", 2018, UP + "Apple_Park.jpg"))
        self.assertEqual(c["categories"], ["Apple Park", "Quality images"])

    def test_token_and_retry_after(self):
        import os
        from email.message import Message
        old = os.environ.pop("WIKIMEDIA_TOKEN", None)
        try:
            self.assertNotIn("Authorization", B.headers())
            os.environ["WIKIMEDIA_TOKEN"] = " abc \n"
            self.assertEqual(B.headers()["Authorization"], "Bearer abc")
        finally:
            os.environ.pop("WIKIMEDIA_TOKEN", None)
            if old is not None:
                os.environ["WIKIMEDIA_TOKEN"] = old
        class E:
            def __init__(self, ra):
                self.headers = Message()
                if ra is not None:
                    self.headers["Retry-After"] = ra
        self.assertEqual(B.wait_for(E("39"), 0), 39)
        self.assertEqual(B.wait_for(E("0"), 0), 1)
        self.assertEqual(B.wait_for(E("9999"), 0), 120)
        self.assertEqual(B.wait_for(E(None), 2), 20)
        self.assertEqual(B.wait_for(E("Wed, 21 Oct 2026 07:28:00 GMT"), 9), 60)


if __name__ == "__main__":
    unittest.main()


class FakeStock:
    """An Unsplash-like source for the tests."""
    name = "unsplash"

    def __init__(self):
        self.tracked = []

    def search(self, q):
        rows = [{"id": "a1", "width": 6000, "height": 4000, "alt_description": "gold bar on black table",
                 "urls": {"raw": "https://images.unsplash.com/photo-a1?ixid=x"}, "links": {"html": "https://unsplash.com/photos/a1",
                 "download_location": "https://api.unsplash.com/photos/a1/download"}, "user": {"name": "Ann Lee", "links": {"html": "https://unsplash.com/@ann"}}},
                {"id": "a2", "width": 6000, "height": 4000, "alt_description": "3d render of gold bars",
                 "urls": {"raw": "https://images.unsplash.com/photo-a2"}, "links": {"html": "https://unsplash.com/photos/a2"}, "user": {"name": "Bo"}},
                {"id": "a3", "width": 6000, "height": 4000, "alt_description": "gold bars", "premium": True,
                 "urls": {"raw": "https://plus.unsplash.com/premium_photo-a3"}, "links": {"html": "https://unsplash.com/photos/a3"}, "user": {"name": "Cy"}},
                {"id": "a4", "width": 6000, "height": 4000, "alt_description": "a sunset over the sea",
                 "urls": {"raw": "https://images.unsplash.com/photo-a4"}, "links": {"html": "https://unsplash.com/photos/a4"}, "user": {"name": "Di"}}]
        return [c for c in (stock.Unsplash.candidate(r) for r in rows) if c] if "gold" in q else []

    def track(self, url):
        self.tracked.append(url)


import stock  # noqa: E402


class Stock(unittest.TestCase):
    def test_candidates_filters_and_links(self):
        src = FakeStock()
        files = [c["file"] for c in src.search("gold bars")]
        self.assertNotIn("unsplash:a3", files)                                           # Unsplash+ is not free
        shot = {"id": "bars", "q": "gold bars", "scene": "Gold bars"}
        r = B.choose(shot, lambda q: [cand("File:Gold bars commons.jpg")], stock_sources=[src])
        self.assertEqual(r[0][1]["file"], "unsplash:a1")                                 # stock first when it matches
        self.assertNotIn("unsplash:a2", [x[1]["file"] for x in r])                       # renders are not photos
        self.assertNotIn("unsplash:a4", [x[1]["file"] for x in r])                       # 'gold' and 'bar' must be named
        self.assertIn("File:Gold bars commons.jpg", [x[1]["file"] for x in r])
        p = B.photo(r[0][1], "bars", B.describe(r[0][1], "x"), "catalog", (0.5, 0.5))
        self.assertEqual((p["shows"], p["credit"], p["provider"]), ("Gold bar on black table", "Photo by Ann Lee on Unsplash", "unsplash"))
        self.assertTrue(p["url"].startswith("https://images.unsplash.com/photo-a1?ixid=x&w=2250&"))  # 1500 px tall for 4:5
        self.assertEqual(p["size"], [2250, 1500])
        self.assertIn("w=500", p["preview"])
        px = stock.Pexels.candidate({"id": 7, "width": 4000, "height": 6000, "url": "https://www.pexels.com/photo/oil-rig-at-sea-7/",
                                     "photographer": "Eve", "photographer_url": "https://www.pexels.com/@eve", "alt": "",
                                     "src": {"original": "https://images.pexels.com/photos/7/pexels-photo-7.jpeg"}})
        self.assertEqual((px["alt"], B.credit_line(px)), ("oil rig at sea", "Photo by Eve on Pexels"))
        self.assertEqual(B.links(px)[2], [1200, 1800])

    def test_people_never_come_from_stock(self):
        r = B.choose({"id": "boss", "q": "gold bars", "person": True}, lambda q: [], stock_sources=[FakeStock()])
        self.assertEqual(r, [])

    def test_download_count_never_waits_on_the_hourly_limit(self):
        import io, urllib.error, urllib.request
        from unittest import mock
        limited = urllib.error.HTTPError("https://api.unsplash.com/photos/a1/download", 403, "Forbidden",
                                         {"X-Ratelimit-Remaining": "0"}, io.BytesIO(b"Rate Limit Exceeded"))
        with mock.patch.object(urllib.request, "urlopen", side_effect=limited), \
             mock.patch.object(stock.time, "sleep", side_effect=AssertionError("waited")):
            self.assertIs(stock.Unsplash(log=lambda *_: None).track("https://api.unsplash.com/photos/a1/download"), False)

    def test_download_counts_not_sent_stay_pending_until_a_later_build(self):
        with tempfile.TemporaryDirectory() as d:
            bank = Path(d)
            src = Fake()
            src.stock = [FakeStock()]
            src.track = lambda p: False                                                   # the counter is at its limit
            m = B.build(MINI, bank, src, kinds=("topic",), log=lambda *_: None)
            self.assertTrue(m["gold"]["photos"][0]["track_pending"])
            sent = []
            src.track = lambda p: sent.append(p["track"])                                 # an hour later
            m = B.build(MINI, bank, src, kinds=("topic",), log=lambda *_: None)            # gold is not due: only the counts
            self.assertEqual(sent, ["https://api.unsplash.com/photos/a1/download"])
            self.assertNotIn("track_pending", m["gold"]["photos"][0])
            B.index(bank, "https://example.org/bank")
            self.assertNotIn("track_pending", (bank / "subjects" / "gold.json").read_text())


class Review(unittest.TestCase):
    def test_only_best_commons_photos_are_published_and_never_picked_again(self):
        with tempfile.TemporaryDirectory() as d:
            bank = Path(d)
            uni = [{"id": "MMM", "name": "3M", "tickers": ["MMM"], "sector": "Industrials", "commons_category": "3M",
                    "image": "3M HQ Maplewood.jpg", "ceo": "William Brown", "wikidata": "Q1"}]
            (bank / "universe.json").write_text(json.dumps({"companies": uni}))
            src = Fake()
            src.stock = [FakeStock()]
            src.track = lambda p: src.stock[0].track(p["track"])
            m = B.build(MINI, bank, src, kinds=("company", "topic"), log=lambda *_: None)
            self.assertEqual(m["gold"]["photos"][0]["provider"], "unsplash")
            self.assertEqual(src.stock[0].tracked, ["https://api.unsplash.com/photos/a1/download"])  # told once, when chosen
            mmm = [p["file"] for p in m["MMM"]["photos"]]
            B.save_review({"min_grade": 3, "grades": {mmm[0]: 3, mmm[1]: 2, mmm[2]: 1}}, bank)
            B.index(bank, "https://example.org/bank")
            rec = {s["id"]: s for s in json.loads((bank / "index.json").read_text())["subjects"]}
            self.assertEqual(rec["MMM"]["photos"], 2)                                  # graded 3, then 2 (plain); 1 and unreviewed hidden
            self.assertEqual(rec["MMM"]["fill_from"], "sector-industrials")
            gold = json.loads((bank / "subjects" / "gold.json").read_text())["photos"]
            self.assertEqual((gold[0]["provider"], gold[0]["author_url"]), ("unsplash", "https://unsplash.com/@ann?" + stock.UTM))
            m = B.build(MINI, bank, src, only="MMM", log=lambda *_: None)
            again = [p["file"] for p in m["MMM"]["photos"]]
            self.assertEqual(again[-1], mmm[1])                                        # the plain one is not picked again,
            self.assertEqual(again.count(mmm[1]), 1)                                   # but stays as the reserve
            self.assertNotIn(mmm[2], again)
            self.assertIn(mmm[0], again)


class ReviewTool(unittest.TestCase):
    def test_grades_from_sheets_start_the_gate(self):
        import review
        with tempfile.TemporaryDirectory() as d:
            bank, sheets = Path(d) / "bank", Path(d) / "review"
            bank.mkdir(); sheets.mkdir()
            (sheets / "sheets.json").write_text(json.dumps({"sheet-001": {"1": {"subject": "X", "file": "File:A.jpg"},
                                                                          "2": {"subject": "X", "file": "File:B.jpg"},
                                                                          "3": {"subject": "X", "file": "File:C.jpg"}}}))
            (sheets / "g.json").write_text(json.dumps({"sheet-001": {"3": [1], "2": [3]}}))
            self.assertEqual(review.grade(sheets / "g.json", sheets, bank), {1: 1, 2: 1, 3: 1})
            rv = B.load_review(bank)
            self.assertEqual((rv["min_grade"], rv["grades"]), (3, {"File:A.jpg": 3, "File:B.jpg": 1, "File:C.jpg": 2}))
            self.assertFalse(B.published({"file": "File:C.jpg"}, rv))
            self.assertTrue(B.published({"file": "pexels:7"}, rv))


class BrandStock:
    """A Pexels-like source with brand photos for the tests."""
    name = "pexels"

    def __init__(self):
        self.queries = []

    def search(self, q):
        self.queries.append(q)
        rows = [("iphone 15 pro on a wooden table", "Ann"), ("silver iphone in hand", "Ann"), ("iphone and airpods", "Ann"),
                ("red apple fruit on a table", "Bo"), ("apple store fifth avenue at night", "Cy"),
                ("3d render of an iphone", "Di"), ("a coca cola bottle on ice", "Ed"), ("macbook pro on desk", "Fa")]
        return [stock.Pexels.candidate({"id": i + 100 * len(q), "width": 5000, "height": 4000, "url": f"https://www.pexels.com/photo/x-{i}/",
                                        "photographer": a, "photographer_url": "https://www.pexels.com/@" + a, "alt": alt,
                                        "src": {"original": f"https://images.pexels.com/photos/{i}/p.jpeg"}})
                for i, (alt, a) in enumerate(rows)]


class Brands(unittest.TestCase):
    APPLE = {"name": "Apple Inc.", "tickers": ["AAPL"], "commons_category": "Apple Inc.", "ambiguous": True}

    def test_brand_photos_name_the_brand(self):
        src = Fake()
        src.stock = [BrandStock()]
        ph = B.brand_photos(self.APPLE, ["iPhone", "MacBook", "Apple Store", "AirPods"], src, set(), 10)
        shows = [p["shows"] for p in ph]
        self.assertEqual(src.stock[0].queries, ["iPhone", "MacBook", "Apple Store"])   # three brands searched
        self.assertNotIn("Red apple fruit on a table", shows)                          # 'Apple' alone is ambiguous
        self.assertNotIn("A coca cola bottle on ice", shows)
        self.assertNotIn("3d render of an iphone", shows)
        self.assertIn("Apple store fifth avenue at night", shows)
        self.assertLessEqual(sum(p["author"] == "Ann" for p in ph), 2)                 # one photographer, two at most
        self.assertEqual(B.brand_photos(self.APPLE, [], Fake(), set(), 10), [])        # no stock source, no photos
        self.assertTrue(B.has_term(B.flat("Coca-Cola can"), B.flat("coca cola")))

    def test_stock_only_keeps_approved_commons_and_fills_with_brands(self):
        with tempfile.TemporaryDirectory() as d:
            bank = Path(d)
            uni = [{"id": "AAPL", **self.APPLE, "sector": "Information Technology", "wikidata": "Q312"}]
            (bank / "universe.json").write_text(json.dumps({"companies": uni}))
            good, plain = cand("File:Apple Park ring.jpg"), cand("File:Apple office corridor.jpg")
            m = {"AAPL": {"name": "Apple Inc.", "kind": "company", "tickers": ["AAPL"], "sector": "sector-tech", "checked": "x",
                          "photos": [B.photo(good, "hq", "Apple Park", "catalog", (0.5, 0.5)), B.photo(plain, "c2", "x", "Commons category", (0.5, 0.5))]}}
            B.save_manifest(m, ["AAPL"], bank)
            B.save_review({"min_grade": 3, "grades": {good["file"]: 3, plain["file"]: 2}}, bank)
            src = Fake()
            src.stock = [BrandStock()]
            m = B.build(MINI, bank, src, kinds=("company",), redo=True, stock_only=True, log=lambda *_: None,
                        brands={"AAPL": ["iPhone", "MacBook", "Apple Store"]})
            files = [p["file"] for p in m["AAPL"]["photos"]]
            self.assertEqual(files[0], good["file"])                                   # approved Commons first, kept
            self.assertEqual(files[-1], plain["file"])                                 # the plain one stays, last
            self.assertEqual(src.calls, [])                                            # Commons not searched
            self.assertTrue(all(B.provider_of(p) == "pexels" for p in m["AAPL"]["photos"][1:-1]))
            rv = B.load_review(bank)
            pub = [p["file"] for p in B.published_photos(m["AAPL"], rv)]
            self.assertLessEqual(len(pub), B.TARGET)
            self.assertEqual(plain["file"] in pub, len(files) - 1 < B.TARGET)          # only in a place left free
            bad = m["AAPL"]["photos"][1]["file"]
            rv["grades"][bad] = 1                                                      # a stock photo can be rejected
            self.assertNotIn(bad, [p["file"] for p in B.published_photos(m["AAPL"], rv)])


class PlainReserve(unittest.TestCase):
    def test_plain_photos_fill_a_companys_free_places_and_are_marked(self):
        with tempfile.TemporaryDirectory() as d:
            bank = Path(d)
            good, plain, bad, gplain = (cand(f) for f in ("File:A HQ.jpg", "File:A office.jpg", "File:A lot.jpg", "File:Gold.jpg"))
            mk = lambda c: B.photo(c, "s", "x", "catalog", (0.5, 0.5))
            m = {"AAA": {"name": "A Corp", "kind": "company", "tickers": ["AAA"], "sector": "sector-tech",
                         "photos": [mk(plain), mk(good), mk(bad)]},
                 "gold": {"name": "Gold", "kind": "topic", "photos": [mk(gplain)]}}
            B.save_manifest(m, ["AAA", "gold"], bank)
            B.save_review({"min_grade": 3, "grades": {good["file"]: 3, plain["file"]: 2, bad["file"]: 1, gplain["file"]: 2}}, bank)
            B.index(bank, "https://example.org/")
            a = json.loads((bank / "subjects" / "AAA.json").read_text())
            self.assertEqual([(p["shows"] and p.get("plain", False)) for p in a["photos"]], [False, True])  # better first
            self.assertEqual(a["fill_from"], "sector-tech")
            self.assertEqual(json.loads((bank / "subjects" / "gold.json").read_text())["photos"], [])  # topics: no reserve


class StockKeys(unittest.TestCase):
    def test_key_from_environment_or_from_the_proxy(self):
        s = stock.sources(env={"UNSPLASH_ACCESS_KEY": "k1"}, probe=lambda url: False)
        self.assertEqual([(x.name, x.headers.get("Authorization")) for x in s], [("unsplash", "Client-ID k1")])
        s = stock.sources(env={}, probe=lambda url: "unsplash" in url)        # a network secret for api.unsplash.com
        self.assertEqual([(x.name, "Authorization" in x.headers) for x in s], [("unsplash", False)])
        self.assertEqual(stock.sources(env={}, probe=lambda url: False), [])

    def test_a_source_at_its_hourly_limit_still_counts_as_there(self):
        import email.message, urllib.error
        def answer(code, limited):
            def opener(req, timeout=None):
                h = email.message.Message()
                if limited:
                    h["X-Ratelimit-Limit"], h["X-Ratelimit-Remaining"] = "50", "0"
                raise urllib.error.HTTPError(req.full_url, code, "x", h, None)
            return opener
        url = stock.Unsplash.probe
        self.assertTrue(stock.answers_without_key(url, answer(403, True)))      # "Rate Limit Exceeded": key is there
        self.assertFalse(stock.answers_without_key(url, answer(401, False)))    # no key
        self.assertFalse(stock.answers_without_key(url, answer(403, False)))

    def test_a_download_count_whose_source_is_missing_stays_pending(self):
        live = B.Live(stock_sources=[])
        self.assertIs(live.track({"provider": "unsplash", "track": "https://api.unsplash.com/photos/x/download"}), False)
        self.assertIs(live.track({"provider": "commons"}), True)

    def test_build_of_topics_stops_when_no_stock_source_answers(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d, mock.patch.object(B.stock, "sources", return_value=[]):
            with self.assertRaises(SystemExit):
                B.build(MINI, bank=d, kinds=("topic", "sector"), log=lambda *_: None)
