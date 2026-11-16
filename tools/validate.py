#!/usr/bin/env python3
"""Validate media-xray files: the JSON Schemas, plus the rules a schema cannot express.

    python tools/validate.py              # everything under movies/, tv/ and examples/
    python tools/validate.py PATH...      # just these files or directories
    python tools/validate.py --fix ...    # rewrite files into canonical order and formatting

An item is a timeline file, <edition>.xray.json, and its language files, <edition>.<language>.xray.json,
side by side. Files are checked on their own and then against the rest of their item.

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
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema" / "v1"
DATA_ROOTS = ("movies", "tv")
DEFAULT_PATHS = (*DATA_ROOTS, "examples")
SUFFIX = ".xray.json"
IGNORED = {".gitkeep"}

FILE_NAME = re.compile(
    r"^(?P<edition>[a-z0-9]+(?:-[a-z0-9]+)*)(?:\.(?P<language>[a-z]{2,3}(?:-[a-z0-9]{2,8})*))?\.xray\.json$"
)
MOVIE_DIR = re.compile(r"^movies/tmdb-(?P<tmdb>[1-9][0-9]*)$")
EPISODE_DIR = re.compile(r"^tv/tmdb-(?P<tmdb>[1-9][0-9]*)/s(?P<season>[0-9]{2,})e(?P<episode>[0-9]{2,})$")

# Timeline sections, each kept sorted so that a contribution shows up as an insertion in a diff
# rather than as a reshuffle.
TIMELINES = ("appearances", "scenes", "segments", "music")
LANGUAGE_TIMELINES = ("trivia",)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


@dataclass
class File:
    path: Path
    name: str
    edition: str
    language: str | None
    text: str = ""
    document: dict | None = None
    report: Report = field(default_factory=Report)


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
    # Entries about the whole item (trivia without a span) come first.
    if "from" not in entry:
        return (-1, -1, "", "", "", entry.get("text", ""))
    return (millis(entry["from"]), millis(entry["to"]), entry.get("who", ""), entry.get("type", ""), entry.get("id", ""),
            entry.get("text", ""))


def canonical(document: dict) -> dict:
    """The document with every timeline sorted. Key order within objects is left as authored."""
    result = dict(document)
    for section in (*TIMELINES, *LANGUAGE_TIMELINES):
        if isinstance(result.get(section), list):
            result[section] = sorted(result[section], key=sort_key)
    if isinstance(result.get("anchors"), list):
        result["anchors"] = sorted(result["anchors"], key=lambda a: (millis(a["from"]), a["kind"]))
    return result


def render(document: dict) -> str:
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def relative(path: Path) -> str | None:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return None


def validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    schemas = {name: json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
               for name in ("xray.schema.json", "language.schema.json")}
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas.values()
    )
    made = []
    for name in ("xray.schema.json", "language.schema.json"):
        Draft202012Validator.check_schema(schemas[name])
        made.append(Draft202012Validator(schemas[name], registry=registry, format_checker=FormatChecker()))
    return made[0], made[1]


def load(file: File, validator: Draft202012Validator) -> None:
    file.text = file.path.read_text(encoding="utf-8")
    try:
        document = json.loads(file.text, object_pairs_hook=reject_duplicate_keys)
    except ValueError as error:
        file.report.error(f"not valid JSON: {error}")
        return
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    for error in errors:
        location = "/".join(str(part) for part in error.absolute_path) or "(root)"
        file.report.error(f"{location}: {error.message}")
    if not errors:
        # Everything after this assumes the shape the schema guarantees.
        file.document = document


def check_directory(rel_dir: str, document: dict, report: Report) -> None:
    title = document["title"]
    if rel_dir.startswith("movies/"):
        match = MOVIE_DIR.match(rel_dir)
        if not match:
            report.error("a film lives in movies/tmdb-<id>/")
        elif title["kind"] != "movie":
            report.error(f"a file under movies/ must have title.kind movie, not {title['kind']}")
        elif int(match["tmdb"]) != title["ids"]["tmdb"]:
            report.error(f"directory says TMDB {match['tmdb']}, title.ids.tmdb says {title['ids']['tmdb']}")
    else:
        match = EPISODE_DIR.match(rel_dir)
        if not match:
            report.error("an episode lives in tv/tmdb-<series id>/sNNeNN/")
        elif title["kind"] != "episode":
            report.error(f"a file under tv/ must have title.kind episode, not {title['kind']}")
        else:
            expected = (int(match["tmdb"]), int(match["season"]), int(match["episode"]))
            actual = (title["series"]["tmdb"], title["season"], title["episode"])
            if expected != actual:
                report.error(
                    "directory says series TMDB %d S%02dE%02d, title says series TMDB %d S%02dE%02d"
                    % (*expected, *actual)
                )


def check_span(where: str, entry: dict, runtime: int, runtime_text: str, report: Report) -> None:
    start, end = millis(entry["from"]), millis(entry["to"])
    if start >= end:
        report.error(f"{where}: from {entry['from']} is not before to {entry['to']}")
    if end > runtime:
        report.error(f"{where}: to {entry['to']} is past the runtime {runtime_text}")


def check_overlap(document: dict, section: str, group, report: Report) -> None:
    spans: dict[object, list[tuple[int, int, int]]] = {}
    for index, entry in enumerate(document.get(section, [])):
        spans.setdefault(group(entry), []).append((millis(entry["from"]), millis(entry["to"]), index))
    for entries in spans.values():
        entries.sort()
        for (_, end, earlier), (start, _, later) in zip(entries, entries[1:]):
            if start < end:
                report.error(f"{section}[{later}] overlaps {section}[{earlier}]")


def check_timeline(file: File) -> None:
    document, report = file.document, file.report
    runtime_text = document["reference"]["runtime"]
    runtime = millis(runtime_text)
    if document["reference"]["edition"] != file.edition:
        report.error(f"file is named {file.edition}{SUFFIX} but reference.edition is {document['reference']['edition']}")

    for section in TIMELINES:
        for index, entry in enumerate(document.get(section, [])):
            check_span(f"{section}[{index}]", entry, runtime, runtime_text, report)

    people = document.get("people", {})
    for index, appearance in enumerate(document.get("appearances", [])):
        if appearance["who"] not in people:
            report.error(f"appearances[{index}]: who {appearance['who']!r} is not a key of people")

    ids = [scene["id"] for scene in document.get("scenes", [])]
    for duplicate in sorted({i for i in ids if ids.count(i) > 1}):
        report.error(f"scene id {duplicate!r} is used twice")

    # Two spans of the same person being present at once are one span, split by accident. Scenes
    # partition the runtime, so two of them cannot both be the current one.
    check_overlap(document, "appearances", lambda e: (e["who"], e.get("presence", "on-screen")), report)
    check_overlap(document, "scenes", lambda e: None, report)
    check_overlap(document, "segments", lambda e: e["type"], report)


def check_language(file: File, timeline: dict) -> None:
    document, report = file.document, file.report
    runtime_text = timeline["reference"]["runtime"]
    runtime = millis(runtime_text)
    if document["language"] != file.language:
        report.error(f"file is named for {file.language} but language is {document['language']}")

    seen = set()
    for index, anchor in enumerate(document.get("anchors", [])):
        check_span(f"anchors[{index}]", anchor, runtime, runtime_text, report)
        key = (anchor["kind"], anchor["from"])
        if key in seen:
            report.error(f"anchors[{index}]: a second {anchor['kind']} anchor at {anchor['from']}")
        seen.add(key)
    starts = sorted(millis(a["from"]) for a in document.get("anchors", []))
    if len(starts) >= 2 and starts[-1] - starts[0] < runtime // 2:
        report.warn("anchors cover less than half the runtime; a consumer cannot correct drift well")
    if len(starts) == 1:
        report.warn("a single anchor fixes the offset but not the speed; add another far from it")

    for index, entry in enumerate(document.get("trivia", [])):
        if "from" in entry:
            check_span(f"trivia[{index}]", entry, runtime, runtime_text, report)

    scene_ids = {scene["id"] for scene in timeline.get("scenes", [])}
    for key in sorted(set(document.get("scenes", {})) - scene_ids):
        report.error(f"scenes.{key}: no scene with that id in {file.edition}{SUFFIX}")
    people = set(timeline.get("people", {}))
    for section in ("characters", "voices"):
        for key in sorted(set(document.get(section, {})) - people):
            report.error(f"{section}.{key}: no such key in people of {file.edition}{SUFFIX}")


def check_canonical(file: File, fix: bool) -> None:
    expected = render(canonical(file.document))
    if file.text != expected:
        if fix:
            file.path.write_text(expected, encoding="utf-8")
            file.report.warn("rewritten into canonical form")
        else:
            file.report.error("not in canonical form (sorted timelines, 2-space JSON); run tools/validate.py --fix")


def validate_item(timeline: File | None, languages: list[File], schemas, fix: bool) -> list[File]:
    timeline_schema, language_schema = schemas
    files = ([timeline] if timeline else []) + languages
    if timeline:
        load(timeline, timeline_schema)
    for file in languages:
        load(file, language_schema)

    if timeline is None:
        for file in languages:
            file.report.error(f"no timeline file {file.edition}{SUFFIX} beside it")
        return files

    if timeline.document is not None:
        rel = relative(timeline.path)
        if rel is not None and rel.split("/", 1)[0] in DATA_ROOTS:
            check_directory(rel.rsplit("/", 1)[0], timeline.document, timeline.report)
        check_timeline(timeline)
        for file in languages:
            if file.document is not None:
                check_language(file, timeline.document)
        # A consumer needs two anchors in one language to align its copy at all.
        if not any(len(f.document.get("anchors", [])) >= 2 for f in languages if f.document is not None):
            timeline.report.error("no language file has two anchors, so no copy can be aligned with this timeline")

    for file in files:
        if file.document is not None and not file.report.errors:
            check_canonical(file, fix)
    return files


def collect(arguments: list[str]) -> tuple[dict[tuple[Path, str], list[Path]], list[Path]]:
    """Files grouped into items by directory and edition, plus files that cannot belong to any item."""
    paths: list[Path] = []
    for argument in arguments or [str(ROOT / p) for p in DEFAULT_PATHS]:
        path = Path(argument)
        if path.is_dir():
            paths.extend(sorted(p for p in path.rglob("*") if p.is_file() and p.name not in IGNORED and p.suffix != ".md"))
        elif path.exists():
            paths.append(path)
        else:
            print(f"{argument}: no such file or directory", file=sys.stderr)
            sys.exit(2)
    items: dict[tuple[Path, str], list[Path]] = {}
    strays = []
    for path in paths:
        match = FILE_NAME.match(path.name)
        if not match:
            strays.append(path)
            continue
        items.setdefault((path.parent.resolve(), match["edition"]), []).append(path)
    return items, strays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fix", action="store_true", help="rewrite files into canonical form")
    parser.add_argument("paths", nargs="*")
    arguments = parser.parse_args()

    schemas = validators()
    items, strays = collect(arguments.paths)
    failed = checked = 0
    for path in strays:
        print(f"{relative(path) or path}: error: only <edition>{SUFFIX} and <edition>.<language>{SUFFIX} files belong here")
        failed += 1
        checked += 1

    for (directory, edition), paths in sorted(items.items()):
        # A language file checked on its own still needs its timeline, and the timeline its languages.
        names = {p.name for p in paths}
        for sibling in directory.glob(f"{edition}.*"):
            match = FILE_NAME.match(sibling.name)
            if match and match["edition"] == edition and sibling.name not in names:
                paths.append(sibling)
        files = [File(p, relative(p) or str(p), edition, FILE_NAME.match(p.name)["language"]) for p in sorted(paths)]
        timeline = next((f for f in files if f.language is None), None)
        languages = [f for f in files if f.language is not None]
        for file in validate_item(timeline, languages, schemas, arguments.fix):
            checked += 1
            for message in file.report.warnings:
                print(f"{file.name}: warning: {message}")
            for message in file.report.errors:
                print(f"{file.name}: error: {message}")
            failed += bool(file.report.errors)

    print(f"{checked} file(s) checked, {failed} with errors")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
