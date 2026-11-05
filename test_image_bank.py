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
        return {t: {"3M": "Q1", "Alphabet Inc.": "Q2", "Berkshire Hathaway": "Q3", "Filler 0": "Q4"}.get(t) for t in titles}

    def search_entity(self, name, ticker):
        return "Q9" if ticker == "TSM" else None

    def existing_categories(self, names):
        return {n for n in names if n == "Filler 1"}

    def entities(self, qids, props="labels|claims"):
        ents = {"Q1": {"claims": {"P373": [{"mainsnak": {"datavalue": {"value": "3M"}}}],
                                  "P18": [{"mainsnak": {"datavalue": {"value": "3M HQ Maplewood.jpg"}}}],
                                  "P169": [{"mainsnak": {"datavalue": {"value": {"id": "Q100"}}}, "qualifiers": {"P582": [{}]}},
                                           {"mainsnak": {"datavalue": {"value": {"id": "Q101"}}}}]}},
                "Q3": {"sitelinks": {"commonswiki": {"title": "Category:Berkshire Hathaway"}}},
                "Q2": {"claims": {"P910": [{"mainsnak": {"datavalue": {"value": {"id": "Q20"}}}}]}},
                "Q20": {"sitelinks": {"commonswiki": {"title": "Category:Alphabet Inc."}}},
                "Q4": {"sitelinks": {"commonswiki": {"title": "Filler zero gallery"}}},
                "Q101": {"labels": {"mul": {"value": "William Brown"}}},
                "Q100": {"labels": {"en": {"value": "Old Boss"}}}}
        return {q: ents.get(q, {}) for q in qids if q}

    def search(self, q):
        self.calls.append(q)
        if q == '"William Brown"':
            return [cand("File:Someone else.jpg"), cand("File:William Brown 2023.jpg", w=2000, h=3000, restr=["personality"])]
        if q.startswith("3M"):
            return [cand(f"File:{q} view {i}.jpg") for i in range(3)] + [cand("File:Unrelated tower.jpg")]
        return [cand(f"File:{q} photo {i}.jpg") for i in range(4)]

    def info(self, titles):
        return {t: cand(t) for t in titles if "missing" not in t}

    def category_photos(self, cat, name):
        files = [(f"File:3M building {i}.jpg", "3M") for i in range(1, 4)]            # near-duplicates: one kept
        files += [(f"File:3M plant {c} site.jpg", "3M factories") for c in "abc"]       # same subcategory: two kept
        files += [("File:3M logo.png", "3M"), ("File:Post-it notes macro.jpg", "Post-it"), ("File:Scotch tape roll.jpg", "Scotch tape")]
        return [(cand(f), where) for f, where in files]


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
        self.assertEqual((rows[4]["name"], rows[4]["sector"]), ("Cboe Global Markets", "Financials"))  # "||" rows
        self.assertEqual((rows[1]["wiki"], rows[1]["name"], rows[1]["sector"]), ("Alphabet Inc.", "Alphabet Inc. (Class A)", "Communication Services"))
        self.assertEqual(rows[3]["sector"], "Financials")

    def test_universe(self):
        with tempfile.TemporaryDirectory() as d:
            src = Fake(n_sp=400)
            extras = [{"ticker": "TSM", "name": "TSMC", "wiki": None, "sector": "Information Technology"},
                      {"ticker": "MMM", "name": "3M again", "wiki": "3M", "sector": "Industrials"}]
            uni = {e["id"]: e for e in B.build_universe(MINI, src, d, extras, log=lambda *_: None)}
            self.assertEqual(uni["GOOGL"]["tickers"], ["GOOGL", "GOOG"])          # two share classes, one company
            self.assertEqual(uni["GOOGL"]["name"], "Alphabet Inc.")
            self.assertEqual(uni["BRK-B"]["wikidata"], "Q3")
            self.assertEqual(uni["BRK-B"]["commons_category"], "Berkshire Hathaway")    # from the Commons sitelink
            self.assertEqual(uni["GOOGL"]["commons_category"], "Alphabet Inc.")         # from its main category's item
            self.assertEqual(uni["X1"]["commons_category"], "Filler 1")                 # named like its article, and exists
            self.assertIsNone(uni["X0"]["commons_category"])                            # a gallery is not a category
            self.assertEqual((uni["MMM"]["commons_category"], uni["MMM"]["ceo"]), ("3M", "William Brown"))  # current CEO only
            self.assertEqual(uni["TSM"]["wikidata"], "Q9")                           # found by name and ticker
            self.assertEqual(sum(1 for e in uni.values() if "MMM" in e["tickers"]), 1)  # an extra already in the S&P 500
            # a hand correction survives the next run
            u = json.loads((Path(d) / "universe.json").read_text())
            next(e for e in u["companies"] if e["id"] == "MMM").update(commons_category="3M Company", manual=["commons_category"])
            (Path(d) / "universe.json").write_text(json.dumps(u))
            uni = {e["id"]: e for e in B.build_universe(MINI, src, d, extras, log=lambda *_: None)}
            self.assertEqual(uni["MMM"]["commons_category"], "3M Company")

    def test_categories_of_a_company(self):
        tree = {"Apple Inc.": ["Apple Inc. buildings", "Apple Inc. logos", "Criticism of Apple Inc.", "Apple Inc. retail",
                               "Taligent", "Employees of Apple Inc.", "Apple Inc. products"],
                "Apple Inc. buildings": ["Apple Park", "One Infinite Loop", "Apple Inc. maps"],
                "Apple Inc. retail": ["Apple Fifth Avenue"]}
        cats = B.pick_categories("Apple Inc.", "Apple", lambda c: tree.get(c, []))
        self.assertEqual(cats, ["Apple Inc.", "Apple Inc. buildings", "Apple Inc. retail", "Apple Inc. products",
                                "Apple Park", "One Infinite Loop", "Apple Fifth Avenue"])
        qs = B.category_queries(cats)
        self.assertEqual(qs, ['incategory:"Apple Inc.|Apple Inc. buildings|Apple Inc. retail|Apple Inc. products|Apple Park|'
                              'One Infinite Loop|Apple Fifth Avenue"'])
        many = B.category_queries([f"Category number {i:02d} of a long company name" for i in range(40)])
        self.assertEqual(len(many), 2)                                                  # at most two searches
        self.assertTrue(all(len(q) <= 280 for q in many))
        self.assertIn("number 00", many[0])

    def test_a_broken_wikipedia_table_stops_the_run(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(RuntimeError):
            B.build_universe(MINI, Fake(n_sp=0), d, [], log=lambda *_: None)

    def test_wikidata_helpers(self):
        ent = {"claims": {"P414": [{"qualifiers": {"P249": [{"datavalue": {"value": "BRK.B"}}]}}]}}
        self.assertTrue(B.has_ticker(ent, "BRK-B"))
        self.assertFalse(B.has_ticker(ent, "BRK-A"))


def ap(file, **kw):
    """A candidate filed under Apple Park: it matches the 'Apple Park' search of the Choosing tests."""
    return cand(file, cats=["Apple Park", *kw.pop("cats", [])], **kw)


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
        self.assertIsNone(B.score(ap("File:Small.jpg", w=1200, h=800), 0, S))
        self.assertIsNone(B.score(ap("File:Apple logo.png", mime="image/png"), 0, S))
        self.assertIsNone(B.score(ap("File:Map of Cupertino.jpg"), 0, S))
        self.assertIsNone(B.score(ap("File:A.jpg", lic="gfdl", short="GFDL"), 0, S))
        self.assertIsNone(B.score(ap("File:A.jpg"), 0, S, used={"File:A.jpg"}))
        self.assertIsNone(B.score(ap("File:A.jpg"), 0, S, no_sa=True))
        self.assertIsNone(B.score(ap("File:A.tif", mime="image/tiff"), 0, S))      # thumbnails named differently
        self.assertIsNone(B.score(ap("File:" + "x" * 170 + ".jpg"), 0, S))
        self.assertIsNone(B.score(ap("File:Some tower.jpg"), 0, {**S, "must": ["3m"]}))
        self.assertIsNotNone(B.score(ap("File:Tower.jpg", cats=["3M buildings"]), 0, {**S, "must": ["3m"]}))
        self.assertIsNotNone(B.score(ap("File:Apple Park plant.jpg"), 0, S))     # "plan" is not "plant"
        self.assertIsNone(B.score(ap("File:Still life.jpg", cats=["Paintings by Jane Doe"]), 0, S))  # photos only
        self.assertIsNotNone(B.score(ap("File:Still life.jpg", cats=["Paintings by Jane Doe"]), 0, {**S, "allow": ["painting"]}))
        old_man = cand("File:William Mason Brown portrait.jpg", year=1870)
        self.assertIsNone(B.score(old_man, 0, {"id": "leader", "q": '"William Brown"', "person": True}))
        self.assertIsNone(B.score(cand("File:William Smith.jpg"), 0, {"id": "l", "q": "William", "must_all": ["william", "brown"]}))

    def test_relevance(self):
        crystals = cand("File:Gold-crystals.jpg", cats=["Gold", "Featured pictures on Wikimedia Commons"])
        self.assertEqual(B.relevance(crystals, "gold vault"), 0.5)
        self.assertIsNone(B.score(crystals, 0, {"id": "vault", "q": "gold vault"}))     # half the words is not enough
        bars = cand("File:Gold bars in a vault.jpg")
        self.assertEqual(B.relevance(bars, "gold bars vaults"), 1)                         # plurals folded
        sh = {"id": "vault", "q": "gold vault", "scene": "Gold bars stacked inside a bank vault"}
        self.assertEqual(B.scene_or_file(sh, bars, "gold vault"), "Gold bars stacked inside a bank vault")
        self.assertEqual(B.scene_or_file(sh, cand("File:Fort Knox gate.jpg", cats=["Gold"]), "gold vault"), "Fort Knox gate")

    def test_ranking(self):
        S = self.SHOT
        plain = B.score(ap("File:A.jpg"), 0, S)
        self.assertGreater(B.score(ap("File:B.jpg", cats=["Featured pictures on Wikimedia Commons"]), 3, S), plain)
        self.assertEqual(B.score(ap("File:C.jpg", w=3000, h=4000), 0, S), plain)       # portrait crops well to 4:5
        self.assertLess(B.score(ap("File:P.jpg", w=6000, h=2000), 0, S), plain)        # a panorama does not
        self.assertLess(B.score(ap("File:D.jpg", year=1975), 0, S), plain)
        self.assertGreater(B.score(ap("File:F.jpg", lic="cc-by-4.0", short="CC BY 4.0"), 0, S), plain)

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
        self.assertEqual((ph[2]["shows"], ph[2]["person"], ph[2]["focus"]), ("William Brown, 3M CEO", True, [0.5, 0.33]))
        self.assertIn("restrictions: personality", ph[2]["flags"])
        files = [p["file"] for p in ph]
        self.assertEqual(len(files), len(set(files)))
        self.assertEqual(sum("3M building" in f for f in files), 1)                     # near-duplicates
        self.assertLessEqual(sum(p.get("category") == "3M factories" for p in ph), 2)   # two per subcategory
        self.assertNotIn("File:3M logo.png", files)
        self.assertNotIn("File:Unrelated tower.jpg", files)                             # searches must name the company
        self.assertEqual(ph[0]["shows"], "3M Center campus")

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
        self.assertEqual(B.credits(self.bank), 25)                          # MMM 10, ZZZ 5 (one per search: same name stem), gold 10
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

    def test_rate_limit_waits(self):
        class Err:
            def __init__(self, h): self.headers = h
        self.assertEqual(B.retry_after(Err({"Retry-After": "37"}), 0), 37)
        self.assertEqual(B.retry_after(Err({}), 0), 5)
        self.assertEqual(B.retry_after(Err({}), 3), 40)
        self.assertEqual(B.retry_after(Err({"Retry-After": "9999"}), 0), 300)

    def test_commons_answer_parsing(self):
        page = {"title": "File:Apple Park.jpg", "index": 1, "imageinfo": [{"width": 6000, "height": 4000, "mime": "image/jpeg",
                "url": UP + "Apple_Park.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=original",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Apple_Park.jpg?utm_source=x",
                "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "License": {"value": "cc-by-sa-4.0"},
                                "Artist": {"value": '<a href="//x">Daniel L. Lu</a>'}, "DateTimeOriginal": {"value": "2018-05-03 10:00"},
                                "Categories": {"value": "Apple Park|Quality images"}, "Restrictions": {"value": ""}}}]}
        c = B.candidate(page)
        self.assertEqual((c["author"], c["year"], c["orig"]), ("Daniel L. Lu", 2018, UP + "Apple_Park.jpg"))
        self.assertEqual(c["categories"], ["Apple Park", "Quality images"])
        self.assertEqual(c["page"], "https://commons.wikimedia.org/wiki/File:Apple_Park.jpg")       # tracking dropped
        self.assertEqual(B.links(c)[1], UP.replace("/commons/", "/commons/thumb/") + "Apple_Park.jpg/500px-Apple_Park.jpg")


if __name__ == "__main__":
    unittest.main()
