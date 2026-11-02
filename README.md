# media-xray-meta

Open, time-coded scene metadata for films and TV episodes, the kind of data behind Prime Video's
X-Ray: who is on screen right now, what song is playing, what this scene is called, where the intro
ends, and trivia tied to the moment you paused on.

Everything here is plain JSON checked against a published JSON Schema, kept in git, and dedicated to
the public domain under [CC0 1.0](LICENSE). Any player, media server or tool may use it.

## Layout

```
schema/v1/xray.schema.json       the timeline file, as JSON Schema 2020-12
schema/v1/language.schema.json   the per-language file
docs/format.md                   what the format means, including what the schemas cannot say
movies/tmdb-<id>/<edition>.xray.json              timeline: ids, segments, people, appearances, scenes
movies/tmdb-<id>/<edition>.<language>.xray.json   one per language: anchors, scene titles, characters, trivia
tv/tmdb-<series id>/s<NN>e<NN>/...                the same for an episode
examples/                        sample files; their timings are illustrative, not real data
tools/validate.py                schema and consistency checks, also run in CI
```

## An item in brief

`theatrical.xray.json`, the same in every language:

```json
{
  "schemaVersion": 1,
  "title": { "kind": "movie", "name": "Night of the Living Dead", "ids": { "tmdb": 10331 } },
  "reference": { "edition": "theatrical", "runtime": "01:36:12.000", "frameRate": "24000/1001" },
  "people": { "ben": { "name": "Duane Jones", "tmdb": 97912 } },
  "appearances": [ { "who": "ben", "from": "00:14:05.750", "to": "00:16:30.250" } ],
  "scenes":      [ { "id": "cemetery", "from": "00:00:00.000", "to": "00:08:41.500" } ],
  "segments":    [ { "from": "01:34:20.000", "to": "01:36:12.000", "type": "outro" } ]
}
```

`theatrical.en.xray.json`, and likewise `theatrical.de.xray.json` and any other language:

```json
{
  "schemaVersion": 1,
  "language": "en",
  "anchors": [
    { "kind": "subtitle", "from": "00:04:52.300", "to": "00:04:54.900", "text": "They're coming to get you, Barbra." },
    { "kind": "chromaprint", "from": "01:21:40.000", "to": "01:21:50.000", "fingerprint": "AQAA..." }
  ],
  "scenes": { "cemetery": "The cemetery" },
  "characters": { "ben": "Ben" }
}
```

Times refer to one specific release, named in `reference`. Your copy will usually differ from it by
a few seconds, or run 4% fast if it is a PAL release. The **anchors** let a consumer work out the
exact mapping for its own file, from whichever audio or subtitle language it has: anchors are kept
per language because a dub does not sound like the original. Read [docs/format.md](docs/format.md) before consuming or producing
data.

People, music and titles are stored as **ids** (TMDB, IMDb, Wikidata, MusicBrainz), not copied
names, photos and biographies. Consumers look those up, so this repository stays free of other
databases' licence terms.

## Using the data

Clone or fetch the repository and read the files you need: the timeline, plus the language files for
the languages you show and the audio tracks you have. The path follows from the TMDB id, so no index
is required. The schemas are at:

```
https://raw.githubusercontent.com/TheBinaryLoop/media-xray-meta/master/schema/v1/xray.schema.json
https://raw.githubusercontent.com/TheBinaryLoop/media-xray-meta/master/schema/v1/language.schema.json
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: one release per item, one file per language, your
own words, a source for every trivia item, and `python tools/validate.py` must pass.

## Licence

The data, schema and tools are dedicated to the public domain under
[CC0 1.0 Universal](LICENSE). By contributing you dedicate your contribution under the same terms.
