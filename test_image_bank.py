"""Offline tests of the image bank (no network): python -m unittest discover -p "test_*.py" """
import io, json, tempfile, unittest
from pathlib import Path

from PIL import Image

import image_bank as B


def cand(file, w=4000, h=2667, lic="cc-by-sa-4.0", short="CC BY-SA 4.0", year=2021, cats=(), mime="image/jpeg", restr=()):
    return {"file": file, "w": w, "h": h, "mime": mime, "url": "https://upload.wikimedia.org/x/" + file, "page": "https://commons.wikimedia.org/wiki/" + file,
            "licence": short, "licence_code": lic, "licence_url": "https://creativecommons.org/licenses/by-sa/4.0", "author": "Jane Doe",
            "year": year, "categories": list(cats), "restrictions": list(restr), "description": ""}


def size(path):
    with Image.open(path) as im:
        return im.size


def jpeg(w=3000, h=2000):
    b = io.BytesIO()
    Image.new("RGB", (w, h), (120, 90, 60)).save(b, "JPEG")
    return b.getvalue()


SHOT = {"id": "hq", "q": "Apple Park", "scene": "Apple Park"}
MINI = {"style": "Photo.", "negative": "text", "subjects": [
    {"id": "AAPL", "kind": "company", "name": "Apple", "tickers": ["AAPL"], "shots": [
        {"id": f"s{i}", "q": "Apple Park", "scene": f"scene {i}"} for i in range(5)] + [
        {"id": "leader", "q": "Tim Cook", "scene": "Tim Cook", "person": True}]},
    {"id": "gold", "kind": "topic", "name": "Gold", "aliases": ["bullion"], "shots": [
        {"id": f"g{i}", "q": "gold bars", "scene": f"gold {i}"} for i in range(5)]},
]}


class Catalog(unittest.TestCase):
    def test_real_catalog_is_valid(self):
        cat = B.load_catalog()
        self.assertGreaterEqual(len([s for s in cat["subjects"] if s["kind"] == "company"]), 40)
        self.assertGreaterEqual(len([s for s in cat["subjects"] if s["kind"] == "topic"]), 25)
        for s in cat["subjects"]:
            self.assertIn(len(s["shots"]), (5, 6), s["id"])

    def test_problems_are_reported(self):
        bad = {"subjects": [{"id": "X", "kind": "company", "name": "X", "shots": [{"id": "a", "q": "x", "scene": "x"}] * 2}]}
        p = B.check_catalog(bad)
        self.assertTrue(any("2 shots" in x for x in p) and any("repeated shot" in x for x in p))

    def test_find_by_ticker_and_alias(self):
        self.assertEqual(B.find_subject(MINI, "aapl")["id"], "AAPL")
        self.assertEqual(B.find_subject(MINI, "Bullion")["id"], "gold")
        self.assertIsNone(B.find_subject(MINI, "nope"))


class Choosing(unittest.TestCase):
    def test_licences(self):
        self.assertEqual(B.licence_kind(cand("a", lic="cc-by-sa-4.0")), "by-sa")
        self.assertEqual(B.licence_kind(cand("a", lic="cc-by-2.0", short="CC BY 2.0")), "by")
        self.assertEqual(B.licence_kind(cand("a", lic="cc0", short="CC0")), "cc0")
        self.assertEqual(B.licence_kind(cand("a", lic="pd", short="Public domain")), "pd")
        self.assertIsNone(B.licence_kind(cand("a", lic="gfdl", short="GFDL")))

    def test_rejections(self):
        self.assertIsNone(B.score(cand("File:Small.jpg", w=1200, h=800), 0, SHOT))
        self.assertIsNone(B.score(cand("File:Apple logo.png"), 0, SHOT))
        self.assertIsNone(B.score(cand("File:Map of Cupertino.jpg"), 0, SHOT))
        self.assertIsNone(B.score(cand("File:A.jpg", lic="gfdl", short="GFDL"), 0, SHOT))
        self.assertIsNone(B.score(cand("File:A.jpg"), 0, SHOT, used={"File:A.jpg"}))
        self.assertIsNone(B.score(cand("File:A.jpg"), 0, SHOT, no_sa=True))
        self.assertIsNone(B.score(cand("File:A.svg", mime="image/svg+xml"), 0, SHOT))
        self.assertIsNotNone(B.score(cand("File:Apple Park plant.jpg"), 0, SHOT))  # "plan" is not "plant"
        self.assertIsNotNone(B.score(cand("File:Crypto chart.jpg"), 0, {**SHOT, "allow": ["chart"]}))

    def test_ranking(self):
        plain = B.score(cand("File:A.jpg"), 0, SHOT)
        self.assertGreater(B.score(cand("File:B.jpg", cats=["Featured pictures on Wikimedia Commons"]), 3, SHOT), plain)
        self.assertLess(B.score(cand("File:C.jpg", w=2000, h=3000), 0, SHOT), plain)       # portrait for a landscape shot
        self.assertLess(B.score(cand("File:D.jpg", year=1975), 0, SHOT), plain)           # old photo
        self.assertEqual(B.score(cand("File:D.jpg", year=1929), 0, {**SHOT, "historic": True}), B.score(cand("File:E.jpg", year=None), 0, SHOT))
        self.assertGreater(B.score(cand("File:F.jpg", lic="cc-by-4.0", short="CC BY 4.0"), 0, SHOT), plain)  # freer licence

    def test_fallback_queries_only_when_needed(self):
        asked = []
        def search(q):
            asked.append(q)
            return [cand(f"File:{q} {i}.jpg") for i in range(4)] if q == "main" else [cand("File:alt.jpg")]
        r = B.choose({"id": "x", "q": "main", "alt": ["other"], "scene": "x"}, search)
        self.assertEqual(asked, ["main"])
        self.assertEqual(r[0][1]["file"], "File:main 0.jpg")
        asked.clear()
        r = B.choose({"id": "x", "q": "none", "alt": ["other"], "scene": "x"}, lambda q: asked.append(q) or ([cand("File:alt.jpg")] if q == "other" else []))
        self.assertEqual((asked, r[0][1]["file"]), (["none", "other"], "File:alt.jpg"))


class Crops(unittest.TestCase):
    def test_sizes_focus_and_enlargement(self):
        im = Image.new("RGB", (2560, 1707))
        out, k = B.crop(im, (1920, 1080))
        self.assertEqual(out.size, (1920, 1080))
        self.assertLess(k, 1.25)
        out, k = B.crop(im, (1080, 1920), (0.0, 0.5))   # focus at the left edge: the crop is clamped inside
        self.assertEqual(out.size, (1080, 1920))
        self.assertGreater(k, 1.0)


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bank = Path(self.tmp.name)
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def search(self, q):
        self.calls.append(q)
        if q == "Tim Cook":
            return [cand("File:Tim Cook 2023.jpg", w=2000, h=3000, restr=["personality"])]
        return [cand(f"File:{q} {i}.jpg") for i in range(8)]

    def run_build(self, **kw):
        return B.build(MINI, self.bank, search_fn=self.search, info_fn=lambda t: cand(t), fetch_fn=lambda u: jpeg(), pause=0, log=lambda *_: None, **kw)

    def test_full_build_outputs(self):
        m = self.run_build()
        shots = m["AAPL"]["shots"]
        self.assertTrue(all(s["status"] == "ok" for e in m.values() for s in e["shots"].values()))
        files = [s["file"] for e in m.values() for s in e["shots"].values()]
        self.assertEqual(len(files), len(set(files)))                     # never the same photo twice
        self.assertEqual(size(self.bank / "AAPL" / "s0.16x9.jpg"), (1920, 1080))
        self.assertEqual(size(self.bank / "AAPL" / "s0.9x16.jpg"), (1080, 1920))
        self.assertEqual(max(size(self.bank / "AAPL" / "s0.jpg")), 2560)
        self.assertEqual(shots["leader"]["focus"], [0.5, 0.33])
        self.assertIn("restrictions: personality", shots["leader"]["flags"])
        self.assertEqual(shots["s0"]["credit"], "Jane Doe, CC BY-SA 4.0, via Wikimedia Commons")
        self.assertEqual(len(shots["s0"]["alternates"]), 3)
        self.assertEqual(B.credits(self.bank), 11)
        self.assertIn("Jane Doe", (self.bank / "CREDITS.md").read_text())
        self.assertEqual(B.prompts(MINI, self.bank), 0)
        self.assertEqual(B.prompts(MINI, self.bank, all_shots=True), 10)  # the person is never generated
        self.assertEqual(B.sheet(MINI, self.bank), (11, 11))
        self.assertEqual(len(B.lookup("bullion", "9x16", self.bank, MINI)), 5)

    def test_dashboard_shows_downloaded_previews(self):
        import dashboard as D
        self.run_build(only="gold")
        rows = {s["id"]: s for s in D.data(MINI, self.bank)}
        self.assertEqual(rows["gold"]["shots"][0]["thumb"], "gold/g0.thumb.jpg")
        self.assertIsNone(rows["AAPL"]["shots"][0]["thumb"])
        self.assertIsNone(rows["AAPL"]["shots"][5]["prompt"])          # a real person: no AI prompt
        self.assertEqual(sorted(D.thumb_files(self.bank)), [f"gold/g{i}.thumb.jpg" for i in range(5)])

    def test_second_build_is_incremental(self):
        self.run_build()
        self.calls.clear()
        self.run_build()
        self.assertEqual(self.calls, [])
        self.run_build(only="gold")
        self.assertEqual(set(self.calls), {"gold bars"})

    def test_manual_corrections_survive(self):
        m = self.run_build()
        first = m["AAPL"]["shots"]["s0"]["file"]
        m["AAPL"]["shots"]["s0"].update(exclude=[first], manual=["exclude"])
        m["AAPL"]["shots"]["s1"].update(prefer="File:Chosen.jpg", focus=[0.2, 0.5], manual=["prefer", "focus"])
        m["gold"]["shots"]["g0"]["manual"] = True
        m["gold"]["shots"]["g0"]["note"] = "frozen"
        (self.bank / "manifest.json").write_text(json.dumps(m))
        m = self.run_build(redo=True)
        s0, s1 = m["AAPL"]["shots"]["s0"], m["AAPL"]["shots"]["s1"]
        self.assertNotEqual(s0["file"], first)
        self.assertEqual(s0["exclude"], [first])
        self.assertEqual((s1["file"], s1["focus"]), ("File:Chosen.jpg", [0.2, 0.5]))
        self.assertEqual(m["gold"]["shots"]["g0"]["note"], "frozen")

    def test_missing_and_errors(self):
        self.search = lambda q: [cand("File:tiny.jpg", w=800, h=600)]
        m = self.run_build(only="gold")
        self.assertEqual({s["status"] for s in m["gold"]["shots"].values()}, {"missing"})
        self.assertEqual(B.prompts(MINI, self.bank), 10)   # gold x5 + AAPL never built x5 (person left out)
        def boom(q): raise OSError("network down")
        self.search = boom
        m = self.run_build(only="AAPL")
        self.assertEqual(m["AAPL"]["shots"]["s0"]["status"], "error")

    def test_error_keeps_a_good_photo(self):
        self.run_build()
        def boom(q): raise OSError("network down")
        self.search = boom
        m = self.run_build(only="gold")
        g0 = m["gold"]["shots"]["g0"]
        self.assertEqual(g0["status"], "ok")
        self.assertIn("kept the previous photo", g0["note"])
        self.assertTrue((self.bank / "gold" / "g0.jpg").exists())

    def test_commons_answer_parsing(self):
        page = {"title": "File:Apple Park.jpg", "index": 1, "imageinfo": [{"width": 6000, "height": 4000, "mime": "image/jpeg",
                "url": "https://upload.wikimedia.org/o.jpg", "thumburl": "https://upload.wikimedia.org/t3840.jpg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Apple_Park.jpg",
                "extmetadata": {"LicenseShortName": {"value": "CC BY-SA 4.0"}, "License": {"value": "cc-by-sa-4.0"},
                                "Artist": {"value": '<a href="//x">Daniel L. Lu</a>'}, "DateTimeOriginal": {"value": "2018-05-03 10:00"},
                                "Categories": {"value": "Apple Park|Quality images"}, "Restrictions": {"value": ""}}}]}
        c = B.candidate(page)
        self.assertEqual((c["author"], c["year"], c["url"]), ("Daniel L. Lu", 2018, "https://upload.wikimedia.org/t3840.jpg"))
        self.assertEqual(c["categories"], ["Apple Park", "Quality images"])
        page["imageinfo"][0].update(width=3000, height=2000)
        self.assertEqual(B.candidate(page)["url"], "https://upload.wikimedia.org/o.jpg")


if __name__ == "__main__":
    unittest.main()
