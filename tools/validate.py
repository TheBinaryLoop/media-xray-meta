#!/usr/bin/env python3
"""Validate media-xray files: the JSON Schema, plus the rules a schema cannot express.

    python tools/validate.py              # everything under movies/, tv/ and examples/
    python tools/validate.py FILE...      # just these
    python tools/validate.py --fix ...    # rewrite files into canonical order and formatting

Exits non-zero if any file has an error. Warnings are printed but do not fail.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "v1" / "xray.schema.json"
DATA_ROOTS = ("movies", "tv")
DEFAULT_PATHS = (*DATA_ROOTS, "examples")
SUFFIX = ".xray.json"
IGNORED = {".gitkeep"}

MOVIE_PATH = re.compile(r"^movies/tmdb-(?P<tmdb>[1-9][0-9]*)/(?P<edition>[a-z0-9]+(?:-[a-z0-9]+)*)\.xray\.json$")
EPISODE_PATH = re.compile(
    r"^tv/tmdb-(?P<tmdb>[1-9][0-9]*)/s(?P<season>[0-9]{2,})e(?P<episode>[0-9]{2,})"
    r"/(?P<edition>[a-z0-9]+(?:-[a-z0-9]+)*)\.xray\.json$"
)

# Timeline sections, each kept sorted so that a contribution shows up as an insertion in a diff
# rather than as a reshuffle.
TIMELINES = ("appearances", "scenes", "segments", "music", "trivia")


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def millis(time: str) -> int:
    hours, minutes, rest = time.split(":")
    seconds, ms = rest.split(".")
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) * 1000 + int(ms)


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    # json.load keeps the last of two equal keys without a word, which would silently drop a person
    # or an id that a contributor typed twice.
    seen: dict = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def sort_key(entry: dict) -> tuple:
    return (millis(entry["from"]), millis(entry["to"]), entry.get("who", ""), entry.get("type", ""))


def canonical(document: dict) -> dict:
    """The document with every timeline sorted. Key order within objects is left as authored."""
    result = dict(document)
    for section in TIMELINES:
        if isinstance(result.get(section), list):
            result[section] = sorted(result[section], key=sort_key)
    if isinstance(result.get("anchors"), list):
        result["anchors"] = sorted(result["anchors"], key=lambda a: millis(a["from"]))
    return result


def render(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def relative(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None


def check_path(rel: str, document: dict, report: Report) -> None:
    title = document["title"]
    edition = document["reference"]["edition"]

    if rel.startswith("movies/"):
        match = MOVIE_PATH.match(rel)
        if not match:
            report.error("path must be movies/tmdb-<id>/<edition>.xray.json")
            return
        if title["kind"] != "movie":
            report.error(f"a file under movies/ must have title.kind movie, not {title['kind']}")
        elif int(match["tmdb"]) != title["ids"]["tmdb"]:
            report.error(f"path says TMDB {match['tmdb']}, title.ids.tmdb says {title['ids']['tmdb']}")
    else:
        match = EPISODE_PATH.match(rel)
        if not match:
            report.error("path must be tv/tmdb-<series id>/sNNeNN/<edition>.xray.json")
            return
        if title["kind"] != "episode":
            report.error(f"a file under tv/ must have title.kind episode, not {title['kind']}")
        else:
            expected = (int(match["tmdb"]), int(match["season"]), int(match["episode"]))
            actual = (title["series"]["tmdb"], title["season"], title["episode"])
            if expected != actual:
                report.error(
                    "path says series TMDB %d S%02dE%02d, title says series TMDB %d S%02dE%02d"
                    % (*expected, *actual)
                )

    if match["edition"] != edition:
        report.error(f"file is named {match['edition']}{SUFFIX} but reference.edition is {edition}")


def check_semantics(document: dict, report: Report) -> None:
    runtime = millis(document["reference"]["runtime"])
    people = document.get("people", {})

    def check_span(where: str, entry: dict) -> None:
        start, end = millis(entry["from"]), millis(entry["to"])
        if start >= end:
            report.error(f"{where}: from {entry['from']} is not before to {entry['to']}")
        if end > runtime:
            report.error(f"{where}: to {entry['to']} is past the runtime {document['reference']['runtime']}")

    for index, anchor in enumerate(document["anchors"]):
        check_span(f"anchors[{index}]", anchor)

    anchor_starts = sorted(millis(a["from"]) for a in document["anchors"])
    if anchor_starts[-1] - anchor_starts[0] < runtime // 2:
        report.warn("anchors cover less than half the runtime; a consumer cannot correct drift well")

    for section in TIMELINES:
        for index, entry in enumerate(document.get(section, [])):
            check_span(f"{section}[{index}]", entry)

    referenced = set()
    for index, appearance in enumerate(document.get("appearances", [])):
        referenced.add(appearance["who"])
        if appearance["who"] not in people:
            report.error(f"appearances[{index}]: who {appearance['who']!r} is not a key of people")
    for unused in sorted(set(people) - referenced):
        report.warn(f"people.{unused} has no appearances")

    def check_overlap(section: str, group) -> None:
        spans: dict[object, list[tuple[int, int, int]]] = {}
        for index, entry in enumerate(document.get(section, [])):
            spans.setdefault(group(entry), []).append((millis(entry["from"]), millis(entry["to"]), index))
        for entries in spans.values():
            entries.sort()
            for (_, end, earlier), (start, _, later) in zip(entries, entries[1:]):
                if start < end:
                    report.error(f"{section}[{later}] overlaps {section}[{earlier}]")

    # Two spans of the same person being present at once are one span, split by accident. Scenes
    # partition the runtime, so two of them cannot both be the current one.
    check_overlap("appearances", lambda e: (e["who"], e.get("presence", "on-screen")))
    check_overlap("scenes", lambda e: None)
    check_overlap("segments", lambda e: e["type"])


def validate(path: Path, validator: Draft202012Validator, fix: bool) -> Report:
    report = Report()
    text = path.read_text(encoding="utf-8")
    try:
        document = json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except ValueError as error:
        report.error(f"not valid JSON: {error}")
        return report

    schema_errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    for error in schema_errors:
        location = "/".join(str(part) for part in error.absolute_path) or "(root)"
        report.error(f"{location}: {error.message}")
    if schema_errors:
        # Everything below assumes the shape the schema guarantees.
        return report

    rel = relative(path)
    if rel is not None and rel.split("/", 1)[0] in DATA_ROOTS:
        check_path(rel, document, report)
    check_semantics(document, report)

    expected = render(canonical(document))
    if text != expected:
        if fix:
            path.write_text(expected, encoding="utf-8")
            report.warn("rewritten into canonical form")
        else:
            report.error("not in canonical form (sorted timelines, 2-space JSON); run tools/validate.py --fix")
    return report


def collect(arguments: list[str]) -> list[Path]:
    files: list[Path] = []
    for argument in arguments or [str(ROOT / p) for p in DEFAULT_PATHS]:
        path = Path(argument)
        if path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.is_file() and p.name not in IGNORED and p.suffix != ".md"))
        elif path.exists():
            files.append(path)
        else:
            print(f"{argument}: no such file or directory", file=sys.stderr)
            sys.exit(2)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fix", action="store_true", help="rewrite files into canonical form")
    parser.add_argument("paths", nargs="*")
    arguments = parser.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    failed = 0
    files = collect(arguments.paths)
    for path in files:
        name = relative(path) or str(path)
        if not path.name.endswith(SUFFIX):
            print(f"{name}: error: only *{SUFFIX} files belong here")
            failed += 1
            continue
        report = validate(path, validator, arguments.fix)
        for message in report.warnings:
            print(f"{name}: warning: {message}")
        for message in report.errors:
            print(f"{name}: error: {message}")
        failed += bool(report.errors)

    print(f"{len(files)} file(s) checked, {failed} with errors")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
