"""Tests for tools/validate.py. Run with: python -m unittest discover -s tests"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import validate  # noqa: E402

EXAMPLE = ROOT / "examples" / "movies" / "tmdb-10331"


def read(name: str) -> dict:
    return json.loads((EXAMPLE / name).read_text(encoding="utf-8"))


class ItemTest(unittest.TestCase):
    """An item is written to a temporary directory and validated as validate.py would see it."""

    schemas = validate.validators()

    def setUp(self):
        self.timeline = read("theatrical.xray.json")
        self.en = read("theatrical.en.xray.json")
        self.de = read("theatrical.de.xray.json")

    def check(self, raw: dict[str, str] | None = None) -> dict[str, validate.Report]:
        documents = {"theatrical.xray.json": self.timeline, "theatrical.en.xray.json": self.en,
                     "theatrical.de.xray.json": self.de}
        with tempfile.TemporaryDirectory() as directory:
            files = []
            for name, document in documents.items():
                if document is None:
                    continue
                path = Path(directory) / name
                text = (raw or {}).get(name, validate.render(document))
                path.write_text(text, encoding="utf-8")
                files.append(validate.File(path, name, "theatrical", validate.FILE_NAME.match(name)["language"]))
            timeline = next((f for f in files if f.language is None), None)
            languages = [f for f in files if f.language is not None]
            return {f.name: f.report for f in validate.validate_item(timeline, languages, self.schemas, fix=False)}

    def assertFails(self, fragment: str, raw: dict[str, str] | None = None):
        reports = self.check(raw)
        errors = [e for r in reports.values() for e in r.errors]
        self.assertTrue(any(fragment in e for e in errors), f"expected an error containing {fragment!r}, got {errors}")

    def assertPasses(self):
        reports = self.check()
        self.assertEqual({n: r.errors for n, r in reports.items() if r.errors}, {})

    # -------------------------------------------------------------------------------- the example

    def test_example_is_valid(self):
        self.assertPasses()

    # -------------------------------------------------------------------------------- timeline file

    def test_time_must_have_milliseconds(self):
        self.timeline["scenes"][0]["to"] = "00:08:41"
        self.assertFails("does not match")

    def test_span_must_move_forward(self):
        self.timeline["scenes"][0]["to"] = self.timeline["scenes"][0]["from"]
        self.assertFails("is not before")

    def test_span_must_end_within_runtime(self):
        self.timeline["segments"][0]["to"] = "01:40:00.000"
        self.assertFails("past the runtime")

    def test_appearance_must_name_a_person(self):
        self.timeline["appearances"][0]["who"] = "johnny"
        self.assertFails("not a key of people")

    def test_person_needs_an_id(self):
        self.timeline["people"]["barbra"] = {"name": "Judith O'Dea"}
        self.assertFails("people/barbra")

    def test_one_person_cannot_overlap_themselves(self):
        self.timeline["appearances"][1]["from"] = "00:08:00.000"
        self.assertFails("overlaps")

    def test_scenes_cannot_overlap(self):
        self.timeline["scenes"][1]["from"] = "00:08:00.000"
        self.assertFails("overlaps")

    def test_scene_ids_are_unique(self):
        self.timeline["scenes"][1]["id"] = self.timeline["scenes"][0]["id"]
        self.assertFails("used twice")

    def test_machine_entries_must_say_whether_reviewed(self):
        del self.timeline["appearances"][1]["reviewed"]
        self.assertFails("'reviewed' is a required property")

    def test_machine_entries_must_carry_confidence(self):
        del self.timeline["appearances"][1]["confidence"]
        self.assertFails("'confidence' is a required property")

    def test_human_entries_need_no_review_flag(self):
        self.timeline["scenes"][0]["source"] = "human"
        self.assertPasses()

    def test_unknown_fields_are_rejected(self):
        self.timeline["appearances"][0]["character"] = "Barbra"
        self.assertFails("Unevaluated properties")

    def test_text_does_not_belong_in_the_timeline(self):
        self.timeline["scenes"][0]["title"] = {"en": "The cemetery"}
        self.assertFails("Unevaluated properties")

    def test_movie_cannot_have_a_season(self):
        self.timeline["title"]["season"] = 1
        self.assertFails("title")

    def test_episode_needs_series_season_and_episode(self):
        self.timeline["title"] = {"kind": "episode", "name": "Pilot", "series": {"tmdb": 1}}
        self.assertFails("'season' is a required property")

    def test_edition_must_match_file_name(self):
        self.timeline["reference"]["edition"] = "extended"
        self.assertFails("reference.edition is extended")

    def test_duplicate_keys_are_rejected(self):
        text = validate.render(self.timeline).replace('"year": 1968,', '"year": 1968,\n    "year": 1969,')
        self.assertFails("duplicate key", {"theatrical.xray.json": text})

    def test_unsorted_timeline_is_not_canonical(self):
        self.timeline["scenes"].reverse()
        text = json.dumps(self.timeline, indent=2, ensure_ascii=False) + "\n"
        self.assertFails("canonical", {"theatrical.xray.json": text})

    # -------------------------------------------------------------------------------- language files

    def test_language_must_match_file_name(self):
        self.de["language"] = "fr"
        self.assertFails("named for de")

    def test_scene_title_needs_a_scene(self):
        self.de["scenes"]["barn"] = "Die Scheune"
        self.assertFails("scenes.barn")

    def test_character_needs_a_person(self):
        self.en["characters"]["johnny"] = "Johnny"
        self.assertFails("characters.johnny")

    def test_trivia_needs_a_source(self):
        self.en["trivia"][0]["sources"] = []
        self.assertFails("trivia/0/sources")

    def test_anchor_must_end_within_runtime(self):
        self.en["anchors"][1]["to"] = "02:00:00.000"
        self.assertFails("past the runtime")

    def test_one_anchor_per_moment(self):
        self.en["anchors"].append(dict(self.en["anchors"][1]))
        self.assertFails("a second chromaprint anchor")

    def test_some_language_needs_two_anchors(self):
        self.en["anchors"] = self.en["anchors"][:1]
        self.assertFails("no language file has two anchors")

    def test_anchors_may_come_from_any_language(self):
        self.de["anchors"] = self.en.pop("anchors")
        self.assertPasses()

    def test_language_file_needs_a_timeline(self):
        self.timeline = None
        self.assertFails("no timeline file")

    def test_fix_sorts_timelines(self):
        shuffled = copy.deepcopy(self.timeline)
        shuffled["appearances"].reverse()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "theatrical.xray.json"
            path.write_text(json.dumps(shuffled, indent=4), encoding="utf-8")
            en = Path(directory) / "theatrical.en.xray.json"
            en.write_text(validate.render(self.en), encoding="utf-8")
            files = [validate.File(path, path.name, "theatrical", None),
                     validate.File(en, en.name, "theatrical", "en")]
            validate.validate_item(files[0], files[1:], self.schemas, fix=True)
            self.assertEqual(path.read_text(encoding="utf-8"), validate.render(self.timeline))


class PathTest(unittest.TestCase):
    def setUp(self):
        self.movie = read("theatrical.xray.json")
        self.episode = copy.deepcopy(self.movie)
        self.episode["title"] = {"kind": "episode", "name": "Pilot", "series": {"tmdb": 1399}, "season": 1, "episode": 1}

    def errors(self, directory: str, document: dict) -> list[str]:
        report = validate.Report()
        validate.check_directory(directory, document, report)
        return report.errors

    def test_movie_directory(self):
        self.assertEqual(self.errors("movies/tmdb-10331", self.movie), [])

    def test_movie_directory_must_match_id(self):
        self.assertTrue(self.errors("movies/tmdb-10332", self.movie))

    def test_episode_directory(self):
        self.assertEqual(self.errors("tv/tmdb-1399/s01e01", self.episode), [])

    def test_episode_directory_must_match_numbers(self):
        self.assertTrue(self.errors("tv/tmdb-1399/s01e02", self.episode))

    def test_episode_under_movies_is_rejected(self):
        self.assertTrue(self.errors("movies/tmdb-1399", self.episode))

    def test_malformed_directory_is_rejected(self):
        self.assertTrue(self.errors("tv/tmdb-1399/S1E1", self.episode))

    def test_file_names(self):
        self.assertEqual(validate.FILE_NAME.match("theatrical.xray.json")["language"], None)
        self.assertEqual(validate.FILE_NAME.match("directors-cut.pt-br.xray.json")["language"], "pt-br")
        self.assertIsNone(validate.FILE_NAME.match("theatrical.EN.xray.json"))


if __name__ == "__main__":
    unittest.main()
