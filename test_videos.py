"""Offline tests of the video bank (no network): python -m unittest discover -p "test_*.py" """
import json, tempfile, unittest
from pathlib import Path

import image_bank as B
import videos as V


def pixabay_hit(i, w=3840, h=2160, tags="gold bars, gold, bullion", dur=12, user="ann", typ="film"):
    ren = lambda k, ww, hh: {"url": f"https://cdn.pixabay.com/video/{i}_{k}.mp4", "width": ww, "height": hh,
                             "thumbnail": f"https://cdn.pixabay.com/video/{i}_{k}.jpg"}
    return {"id": i, "pageURL": f"https://pixabay.com/videos/id-{i}/", "type": typ, "tags": tags, "duration": dur,
            "user": user, "user_id": 7, "videos": {
                "large": ren("large", w, h) if max(w, h) >= 3840 else {"url": "", "width": 0, "height": 0, "thumbnail": ""},
                "medium": ren("medium", *((w, h) if max(w, h) < 3840 else (w // 2, h // 2))),
                "small": ren("small", w // 3, h // 3),
                "tiny": ren("tiny", w // 4, h // 4)}}


class FakeSource:
    name = "pixabay"

    def __init__(self, hits):
        self.hits, self.queries = hits, []

    def search(self, q):
        self.queries.append(q)
        return [c for c in (V.PixabayVideo.candidate(h) for h in self.hits.get(q, [])) if c]


class Candidates(unittest.TestCase):
    def test_pixabay_candidate_sizes_orientation_and_credit(self):
        c = V.PixabayVideo.candidate(pixabay_hit(1))
        self.assertEqual((c["w"], c["h"], c["provider"]), (3840, 2160, "pixabay"))
        self.assertTrue(c["url"].endswith("1_large.mp4"))
        self.assertTrue(c["url_1080"].endswith("1_medium.mp4"))          # the 1920 px file
        self.assertTrue(c["preview_mp4"].endswith("1_tiny.mp4"))
        v = V.video(c, "gold-bars")
        self.assertEqual((v["orientation"], v.get("vertical_crop_ok")), ("horizontal", True))
        self.assertEqual(v["credit"], "Video by ann on Pixabay")
        hd = V.video(V.PixabayVideo.candidate(pixabay_hit(2, 1920, 1080)), "s")
        self.assertNotIn("vertical_crop_ok", hd)                           # 1080 px tall: a 9:16 crop is upscaled
        self.assertEqual(hd["url"], hd["url_1080"])
        self.assertEqual(V.video(V.PixabayVideo.candidate(pixabay_hit(3, 1080, 1920)), "s")["orientation"], "vertical")
        self.assertIsNone(V.PixabayVideo.candidate({"id": 4, "videos": {}}))

    def test_rules_for_a_clip(self):
        shot = {"id": "gold-bars", "q": "gold bars"}
        good = V.PixabayVideo.candidate(pixabay_hit(1))
        self.assertTrue(V.ok(good, shot, "gold bars"))
        bad = lambda **k: V.ok(V.PixabayVideo.candidate(pixabay_hit(9, **k)), shot, "gold bars")
        self.assertFalse(bad(tags="gold bars, 3d, render"))                 # not real footage
        self.assertFalse(bad(tags="gold, animation"))
        self.assertFalse(bad(typ="animation"))
        self.assertFalse(bad(dur=2))                                       # too short
        self.assertFalse(bad(dur=95))                                      # too long for a stock clip
        self.assertFalse(bad(w=1280, h=720))                               # under 1080p
        self.assertFalse(bad(tags="gold coins"))                           # 'bars' missing
        self.assertFalse(V.ok(good, shot, "gold bars", grades={good["file"]: 2}))   # graded below 3: never again
        self.assertFalse(V.ok(good, shot, "gold bars", used={good["file"]}))       # used by another subject

    def test_commons_clips_free_licences_only_and_no_news(self):
        def page(title, lic="CC BY 4.0", code="cc-by-4.0", dur=40, w=1920, h=1080, cats=""):
            return {"title": title, "videoinfo": [{"width": w, "height": h, "mime": "video/webm", "duration": dur,
                    "url": "https://upload.wikimedia.org/wikipedia/commons/a/ab/X.webm?utm_source=x",
                    "descriptionurl": "https://commons.wikimedia.org/wiki/File:X.webm",
                    "thumburl": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/X.webm/640px--X.webm.jpg?utm_source=x",
                    "extmetadata": {"LicenseShortName": {"value": lic}, "License": {"value": code},
                                    "Artist": {"value": "Jan"}, "Categories": {"value": cats}},
                    "derivatives": [{"src": "https://upload.wikimedia.org/t/X.webm.240p.vp9.webm", "type": "video/webm", "width": 426, "height": 240},
                                    {"src": "https://upload.wikimedia.org/t/X.webm.480p.vp9.webm", "type": "video/webm", "width": 854, "height": 480},
                                    {"src": "https://upload.wikimedia.org/t/X.webm.1080p.vp9.webm", "type": "video/webm", "width": 1920, "height": 1080}]}]}
        shot = {"id": "container-ship", "q": "container ship"}
        c = V.CommonsVideo.candidate(page("File:Container ship at sea.webm"))
        self.assertTrue(c["url"].endswith("1080p.vp9.webm") and c["preview_mp4"].endswith("480p.vp9.webm"))
        self.assertTrue(V.ok(c, shot, "container ship"))
        self.assertEqual(V.video(c, "s")["credit"], "Jan, CC BY 4.0, via Wikimedia Commons")
        frames = V.frame_urls({**V.video(c, "s"), "duration": 40.0})
        self.assertEqual(frames[1], "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/X.webm/640px-seek%3D20-X.webm.jpg")
        sa = V.CommonsVideo.candidate(page("File:Container ship at sea.webm", "CC BY-SA 4.0", "cc-by-sa-4.0"))
        self.assertFalse(V.ok(sa, shot, "container ship"))                  # a reel cut from it would be BY-SA
        self.assertFalse(V.ok(V.CommonsVideo.candidate(page("File:Container ship news report.webm")), shot, "container ship"))
        self.assertFalse(V.ok(V.CommonsVideo.candidate(page("File:Container ship.webm", dur=600)), shot, "container ship"))
        self.assertTrue(V.ok(V.CommonsVideo.candidate(page("File:Container ship.webm", dur=150)), shot, "container ship"))

    def test_nasa_clips_public_domain_and_not_launch_providers(self):
        d = {"nasa_id": "KSC-1", "title": "Artemis rocket launch", "photographer": "Kim Shiflett"}
        hrefs = ["http://images-assets.nasa.gov/video/KSC-1/KSC-1~orig.mp4", "http://images-assets.nasa.gov/video/KSC-1/KSC-1~small.mp4",
                 "http://images-assets.nasa.gov/video/KSC-1/KSC-1~small_1.jpg", "http://images-assets.nasa.gov/video/KSC-1/KSC-1~small_3.jpg",
                 "http://images-assets.nasa.gov/video/KSC-1/KSC-1~small_5.jpg", "http://images-assets.nasa.gov/video/KSC-1/metadata.json"]
        c = V.NasaVideo.candidate(d, hrefs, {"QuickTime:ImageWidth": 1920, "QuickTime:ImageHeight": 1080, "QuickTime:Duration": "0:01:05"})
        self.assertEqual((c["duration"], c["url"][:8], len(c["frames"])), (65.0, "https://", 3))
        self.assertEqual(V.credit_line(c), "Video: NASA/Kim Shiflett, public domain")
        self.assertTrue(V.NasaVideo.third({"secondary_creator": "Rocket Lab"}))
        self.assertTrue(V.NasaVideo.third({"description": "Video credit: SpaceX"}))
        self.assertFalse(V.NasaVideo.third(d))
        self.assertEqual(V.NasaVideo(fetch=lambda u: 1 / 0).search("gold bars"), [])   # not space: never searched


class Picking(unittest.TestCase):
    def setUp(self):
        self.s = {"id": "gold", "kind": "topic", "name": "Gold", "shots": ["gold bars", "gold coins", "gold mine"]}
        self.hits = {
            "gold bars": [pixabay_hit(i, tags="gold bars", user=f"u{i}") for i in range(1, 6)]
                         + [pixabay_hit(50, 1080, 1920, tags="gold bars", user="v1")],
            "gold coins": [pixabay_hit(i, tags="gold coins", user="same") for i in range(10, 15)]
                          + [pixabay_hit(51, 2160, 3840, tags="gold coins", user="v2")],
            "gold mine": [pixabay_hit(20, tags="gold mine", user="m1")]}

    def test_verticals_first_then_one_per_shot_and_two_per_uploader(self):
        vids = V.subject_videos(self.s, [FakeSource(self.hits)], target=6, log=lambda *a: None)
        self.assertEqual(len(vids), 6)
        self.assertEqual([v["orientation"] for v in vids[:2]], ["vertical", "vertical"])
        self.assertLessEqual(sum(1 for v in vids if v["author"] == "same"), 2)
        self.assertEqual({v["shot"] for v in vids}, {"gold-bars", "gold-coins", "gold-mine"})   # every shot before seconds
        self.assertEqual(len({v["file"] for v in vids}), 6)

    def test_proven_shots_are_searched_first_and_searching_stops_when_enough(self):
        src = FakeSource(self.hits)
        photos = {"photos": [{"file": "unsplash:x", "provider": "unsplash", "shot": "gold-mine"}]}
        V.subject_videos(self.s, [src], target=1, photo_entry=photos, log=lambda *a: None, max_searches=1)
        self.assertEqual(src.queries, ["gold mine"])

    def test_build_index_and_review_gate(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "review.json").write_text(json.dumps({"min_grade": 3, "grades": {}}))
            cat = {"subjects": [self.s, {"id": "AAPL", "kind": "company", "name": "Apple", "shots": []}]}
            n = V.build(bank=d, catalog=cat, srcs=[FakeSource(self.hits)], target=4, log=lambda *a: None)
            self.assertEqual(n, 4)
            idx = json.loads((Path(d) / "videos" / "index.json").read_text())
            self.assertEqual([s["id"] for s in idx["subjects"]], ["gold"])          # topics and sectors only
            self.assertEqual((idx["videos"], idx["subjects"][0]["vertical"]), (4, 2))
            one = json.loads((Path(d) / "videos" / "gold.json").read_text())["videos"]
            self.assertTrue(all("credit" in v and "source" in v and "preview_mp4" not in v for v in one))
            # a clip graded 2 is hidden at once and replaced on a rebuild; the others stay
            m = V.load(d)
            first = m["gold"]["videos"][0]["file"]
            rv = V.load_review(d)
            rv["grades"][first] = 2
            V.save_review(rv, d)
            self.assertEqual(json.loads((Path(d) / "review.json").read_text())["grades"], {})   # photos' grades untouched
            self.assertEqual(V.index(d), 3)
            V.build(bank=d, catalog=cat, srcs=[FakeSource(self.hits)], target=4, redo=True, log=lambda *a: None)
            files = [v["file"] for v in V.load(d)["gold"]["videos"]]
            self.assertNotIn(first, files)
            self.assertEqual(len(files), 4)
            self.assertEqual(files[:3], [v["file"] for v in m["gold"]["videos"][1:]])  # kept, in their order

    def test_grades_from_sheets_go_to_their_own_file(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "sheets.json").write_text(json.dumps({"sheet-001": {"1": {"subject": "gold", "file": "pixabay-video:1"},
                                                                           "2": {"subject": "gold", "file": "File:X.webm"}}}))
            (Path(d) / "g.json").write_text(json.dumps({"sheet-001": {"3": [2]}}))
            self.assertEqual(V.grade(Path(d) / "g.json", d, bank=d), {1: 1, 2: 0, 3: 1})
            self.assertEqual(V.load_review(d)["grades"], {"File:X.webm": 3, "pixabay-video:1": 1})
            self.assertFalse((Path(d) / "review.json").exists())

    def test_commons_clips_need_grade_three(self):
        v = {"file": "File:X.webm", "provider": "commons"}
        self.assertFalse(V.published(v, {}))
        self.assertTrue(V.published(v, {"File:X.webm": 3}))
        p = {"file": "pixabay-video:1", "provider": "pixabay"}
        self.assertTrue(V.published(p, {}))
        self.assertFalse(V.published(p, {"pixabay-video:1": 2}))

    def test_the_key_never_reaches_an_error_message(self):
        import stock
        old = stock.fetch
        try:
            stock.fetch = lambda url, h, log=None: (_ for _ in ()).throw(RuntimeError("no answer from " + url))
            with self.assertRaises(RuntimeError) as e:
                V.PixabayVideo("SECRETKEY123").search("gold")
            self.assertNotIn("SECRETKEY123", str(e.exception))
        finally:
            stock.fetch = old

    def test_sources_need_the_key_in_the_environment(self):
        self.assertEqual([s.name for s in V.sources(env={})], ["commons", "nasa"])
        self.assertEqual([s.name for s in V.sources(env={"PIXABAY_API_KEY": "k"})], ["pixabay", "commons", "nasa"])


if __name__ == "__main__":
    unittest.main()
