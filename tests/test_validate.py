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

EXAMPLE = ROOT / "examples" / "movies" / "tmdb-10331" / "theatrical.xray.json"


def schema_validator():
    from jsonschema import Draft202012Validator, FormatChecker

    schema = json.loads(validate.SCHEMA_PATH.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


class ValidateTest(unittest.TestCase):
    validator = schema_validator()

    def setUp(self):
        self.document = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def check(self, document: dict, text: str | None = None) -> validate.Report:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.xray.json"
            path.write_text(text if text is not None else validate.render(document), encoding="utf-8")
            return validate.validate(path, self.validator, fix=False)

    def assertFails(self, document: dict, fragment: str, text: str | None = None):
        report = self.check(document, text)
        self.assertTrue(
            any(fragment in error for error in report.errors),
            f"expected an error containing {fragment!r}, got {report.errors}",
        )

    def test_example_is_valid(self):
        report = validate.validate(EXAMPLE, self.validator, fix=False)
        self.assertEqual(report.errors, [])

    def test_time_must_have_milliseconds(self):
        self.document["scenes"][0]["to"] = "00:08:41"
        self.assertFails(self.document, "does not match")

    def test_span_must_move_forward(self):
        self.document["scenes"][0]["to"] = self.document["scenes"][0]["from"]
        self.assertFails(self.document, "is not before")

    def test_span_must_end_within_runtime(self):
        self.document["segments"][0]["to"] = "01:40:00.000"
        self.assertFails(self.document, "past the runtime")

    def test_appearance_must_name_a_person(self):
        self.document["appearances"][0]["who"] = "johnny"
        self.assertFails(self.document, "not a key of people")

    def test_person_needs_an_id(self):
        self.document["people"]["barbra"] = {"name": "Judith O'Dea"}
        self.assertFails(self.document, "people/barbra")

    def test_one_person_cannot_overlap_themselves(self):
        self.document["appearances"][1]["from"] = "00:08:00.000"
        self.assertFails(self.document, "overlaps")

    def test_scenes_cannot_overlap(self):
        self.document["scenes"][1]["from"] = "00:08:00.000"
        self.assertFails(self.document, "overlaps")

    def test_machine_entries_must_say_whether_reviewed(self):
        del self.document["appearances"][1]["reviewed"]
        self.assertFails(self.document, "'reviewed' is a required property")

    def test_human_entries_need_no_review_flag(self):
        self.document["scenes"][0]["source"] = "human"
        self.assertEqual(self.check(self.document).errors, [])

    def test_unknown_fields_are_rejected(self):
        self.document["appearances"][0]["character"] = "Barbra"
        self.assertFails(self.document, "Unevaluated properties")

    def test_movie_cannot_have_a_season(self):
        self.document["title"]["season"] = 1
        self.assertFails(self.document, "title")

    def test_episode_needs_series_season_and_episode(self):
        self.document["title"] = {"kind": "episode", "name": "Pilot", "series": {"tmdb": 1}}
        self.assertFails(self.document, "'season' is a required property")

    def test_trivia_needs_a_source(self):
        self.document["trivia"][0]["sources"] = []
        self.assertFails(self.document, "trivia/0/sources")

    def test_needs_two_anchors(self):
        self.document["anchors"] = self.document["anchors"][:1]
        self.assertFails(self.document, "anchors")

    def test_duplicate_keys_are_rejected(self):
        text = validate.render(self.document).replace('"year": 1968,', '"year": 1968,\n    "year": 1969,')
        self.assertFails(self.document, "duplicate key", text)

    def test_unsorted_timeline_is_not_canonical(self):
        self.document["scenes"].reverse()
        text = json.dumps(self.document, indent=2, ensure_ascii=False) + "\n"
        self.assertFails(self.document, "canonical", text)

    def test_fix_sorts_timelines(self):
        shuffled = copy.deepcopy(self.document)
        shuffled["appearances"].reverse()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.xray.json"
            path.write_text(json.dumps(shuffled, indent=4), encoding="utf-8")
            validate.validate(path, self.validator, fix=True)
            self.assertEqual(path.read_text(encoding="utf-8"), validate.render(self.document))


class PathTest(unittest.TestCase):
    def setUp(self):
        self.movie = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        self.episode = copy.deepcopy(self.movie)
        self.episode["title"] = {
            "kind": "episode",
            "name": "Pilot",
            "series": {"tmdb": 1399},
            "season": 1,
            "episode": 1,
        }
        self.episode["reference"]["edition"] = "original"

    def errors(self, rel: str, document: dict) -> list[str]:
        report = validate.Report()
        validate.check_path(rel, document, report)
        return report.errors

    def test_movie_path(self):
        self.assertEqual(self.errors("movies/tmdb-10331/theatrical.xray.json", self.movie), [])

    def test_movie_path_must_match_id(self):
        self.assertTrue(self.errors("movies/tmdb-10332/theatrical.xray.json", self.movie))

    def test_movie_path_must_match_edition(self):
        self.assertTrue(self.errors("movies/tmdb-10331/extended.xray.json", self.movie))

    def test_episode_path(self):
        self.assertEqual(self.errors("tv/tmdb-1399/s01e01/original.xray.json", self.episode), [])

    def test_episode_path_must_match_numbers(self):
        self.assertTrue(self.errors("tv/tmdb-1399/s01e02/original.xray.json", self.episode))

    def test_episode_under_movies_is_rejected(self):
        self.assertTrue(self.errors("movies/tmdb-1399/original.xray.json", self.episode))

    def test_malformed_path_is_rejected(self):
        self.assertTrue(self.errors("tv/tmdb-1399/S1E1/original.xray.json", self.episode))


if __name__ == "__main__":
    unittest.main()
