"""Write media-xray items (timeline + one file per language) for one season from verified results.

Usage: gen.py WORK SEASON REPO
"""
import json, sys
from pathlib import Path

work, season, repo = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
BASE = "https://raw.githubusercontent.com/TheBinaryLoop/media-xray-meta/master/schema/v1/"
RELEASE = {"s10e10": "25 fps European release with German audio only"}
SERIES = {"tmdb": 1911, "imdb": "tt0460627", "tvdb": 75682, "wikidata": "Q207803"}

titles = {}
for line in open(work / "tmdb-titles.tsv", encoding="utf-8"):
    s, e, name = line.rstrip("\n").split("\t")
    titles[(int(s), int(e))] = name

def ts(seconds):
    ms = round(seconds * 1000)
    h, rest = divmod(ms, 3600_000); m, rest = divmod(rest, 60_000); s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def write(path, document):
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

results = json.load(open(work / "results" / f"s{season:02d}.json"))
dubs_path = work / "dubs" / f"s{season:02d}.json"
dubs = json.load(open(dubs_path)) if dubs_path.exists() else {}

for key, ep in results.items():
    e = int(key[4:])
    anchors = {}
    for a in ep["anchors"] + dubs.get(key, []):
        anchors.setdefault(a["language"], []).append(
            {"kind": "chromaprint", "from": ts(a["start"]), "to": ts(a["end"]), "fingerprint": a["fingerprint"]})
    if not any(len(v) >= 2 for v in anchors.values()):
        print(f"{key}: skipped, no language has two anchors")
        continue

    ids = {k: v for k, v in (("imdb", ep["imdb"]), ("tvdb", ep["tvdb"])) if v}
    title = {"kind": "episode", "name": titles[(season, e)]}
    if ids: title["ids"] = ids
    title.update({"series": SERIES, "season": season, "episode": e})
    timeline = {
        "$schema": BASE + "xray.schema.json",
        "schemaVersion": 1,
        "title": title,
        "reference": {
            "edition": "original",
            "runtime": ts(ep["runtime"]),
            "frameRate": "25",
            "release": RELEASE.get(key, "25 fps European release with English and German audio"),
        },
    }
    segments = []
    for kind, field in (("intro", "intro"), ("outro", "outro"), ("recap", "recap")):
        if field in ep:
            x = ep[field]
            segments.append({"from": ts(x["start"]), "to": ts(x["end"]), "type": kind,
                             "source": "video-analysis", "confidence": x["confidence"], "reviewed": False})
    if segments:
        timeline["segments"] = sorted(segments, key=lambda x: x["from"])

    directory = repo / "tv" / "tmdb-1911" / f"s{season:02d}e{e:02d}"
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob("*.xray.json"):
        old.unlink()
    write(directory / "original.xray.json", timeline)
    for language, items in sorted(anchors.items()):
        write(directory / f"original.{language}.xray.json",
              {"$schema": BASE + "language.schema.json", "schemaVersion": 1, "language": language,
               "anchors": sorted(items, key=lambda a: a["from"])})
print("season", season, "written")
