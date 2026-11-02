# media-xray-meta

Open, time-coded scene metadata for films and TV episodes, the kind of data behind Prime Video's
X-Ray: who is on screen right now, what song is playing, what this scene is called, where the intro
ends, and trivia tied to the moment you paused on.

Everything here is plain JSON checked against a published JSON Schema, kept in git, and dedicated to
the public domain under [CC0 1.0](LICENSE). Any player, media server or tool may use it.

## Layout

```
schema/v1/xray.schema.json      the format, as JSON Schema 2020-12
docs/format.md                  what the format means, including what the schema cannot say
movies/tmdb-<id>/<edition>.xray.json
tv/tmdb-<series id>/s<NN>e<NN>/<edition>.xray.json
examples/                       sample files; their timings are illustrative, not real data
tools/validate.py               schema and consistency checks, also run in CI
```

## A file in brief

```json
{
  "schemaVersion": 1,
  "title": { "kind": "movie", "name": "Night of the Living Dead", "ids": { "tmdb": 10331 } },
  "reference": { "edition": "theatrical", "runtime": "01:36:12.000", "frameRate": "24000/1001" },
  "anchors": [
    { "kind": "subtitle", "from": "00:04:52.300", "to": "00:04:54.900", "language": "en", "text": "They're coming to get you, Barbra." },
    { "kind": "chromaprint", "from": "01:21:40.000", "to": "01:21:50.000", "fingerprint": "AQAA..." }
  ],
  "people": { "ben": { "name": "Duane Jones", "character": "Ben", "tmdb": 97912 } },
  "appearances": [ { "who": "ben", "from": "00:14:05.750", "to": "00:16:30.250" } ],
  "scenes":      [ { "from": "00:00:00.000", "to": "00:08:41.500", "title": { "en": "The cemetery" } } ],
  "segments":    [ { "from": "01:34:20.000", "to": "01:36:12.000", "type": "outro" } ]
}
```

Times refer to one specific release, named in `reference`. Your copy will usually differ from it by
a few seconds, or run 4% fast if it is a PAL release. The **anchors** let a consumer work out the
exact mapping for its own file. Read [docs/format.md](docs/format.md) before consuming or producing
data.

People, music and titles are stored as **ids** (TMDB, IMDb, Wikidata, MusicBrainz), not copied
names, photos and biographies. Consumers look those up, so this repository stays free of other
databases' licence terms.

## Using the data

Clone or fetch the repository and read the files you need. The path follows from the TMDB id, so no
index is required. Pin the schema by its URL:

```
https://raw.githubusercontent.com/TheBinaryLoop/media-xray-meta/master/schema/v1/xray.schema.json
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: one release per file, your own words, a source
for every trivia item, and `python tools/validate.py` must pass.

## Licence

The data, schema and tools are dedicated to the public domain under
[CC0 1.0 Universal](LICENSE). By contributing you dedicate your contribution under the same terms.
