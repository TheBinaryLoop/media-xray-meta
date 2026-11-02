# The media-xray format, version 1

One JSON file describes one **release** of one film or episode: who is on screen when, what music is
playing, what the scenes are called, which stretches can be skipped, and trivia tied to a moment. The
machine-readable definition is [`schema/v1/xray.schema.json`](../schema/v1/xray.schema.json) (JSON
Schema 2020-12). This document covers what the schema cannot say.

## Where a file lives

| What | Path |
|---|---|
| Film | `movies/tmdb-<TMDB movie id>/<edition>.xray.json` |
| Episode | `tv/tmdb-<TMDB series id>/s<NN>e<NN>/<edition>.xray.json` |

Season and episode numbers are zero-padded to at least two digits and follow TMDB's numbering
(specials are season 0). The path is derived from the file's own `title` and `reference.edition`, and
`tools/validate.py` rejects a file whose path and contents disagree.

TMDB is the key because it numbers films, series, seasons and episodes in one consistent scheme. The
other ids (`imdb`, `tvdb`, `wikidata`) are there so consumers keyed on something else can still find
the file.

## The reference timeline

**Every time in a file is a position in one specific release**, the one named by `reference`, counted
from its first frame. That is the most important rule in this format and the reason anchors exist.

The same film is not the same timeline everywhere. A different cut adds or removes scenes. A PAL
release plays 4% fast. One encode keeps the distributor logos and another trims them. "Ben arrives at
00:14:05" is true for exactly one of those. So a file states:

- `edition`: which cut. Different cuts get different files, because a scene that exists in only one
  of them cannot be mapped onto the other.
- `runtime`: how long the reference release runs.
- `frameRate` (optional): its nominal frame rate as a rational, so `24000/1001` rather than `23.976`.
- `release` (optional): free text saying what the times were taken from.

Times are strings in the form `HH:MM:SS.mmm`, which is how a person reads them off a player. Using
strings also keeps floating-point noise out of diffs.

## Anchors: mapping the reference onto your copy

A consumer rarely has the exact reference release, so it has to work out the relationship between
the two timelines:

```
local = scale × reference + offset
```

`scale` is 1 for the same cut at the same speed. It is about 0.959 when a 24000/1001 reference is
played back as a 25 fps PAL release. `offset` absorbs trimmed or added logos. Anchors are how a
consumer finds both numbers. Each one is a short stretch that can be recognised in a local copy:

- `subtitle`: a line of dialogue, with the times it is on screen in the reference. Match it fuzzily
  against the local subtitle track. Easy for a person to add by hand.
- `chromaprint`: a [Chromaprint](https://acoustid.org/chromaprint) fingerprint of the audio between
  `from` and `to`, in the compressed base64url form `fpcalc` prints by default (not its `-raw`
  output). Match it by sliding the fingerprint over the local audio.

A file needs at least two anchors, and they should be far apart: two anchors near the start fix the
offset but say almost nothing about the scale. The validator warns when the anchors cover less than
half the runtime.

A consumer should find the mapping from every anchor it can match (least squares over the matched
pairs). It should **show no time-coded data at all** if fewer than two anchors match, or if they
disagree by more than a second after fitting. Wrong data at the wrong moment is worse than none. Data
that is not tied to a time (the people list, say) can still be shown.

## Sections

All timeline entries have `from` and `to` (end exclusive). Each section is kept sorted by `from`
(then `to`), which the validator enforces, so a new entry shows up as an insertion in a diff.

### `people` and `appearances`

`people` is keyed by a short slug that only means something inside the file (`ben`, `barbra`,
`young-ellie`). Each person carries at least one external id (`tmdb`, `imdb` or `wikidata`) and a
`name`. The name is a label for whoever is reviewing the file. Consumers should take what they
display (name, photo, biography) from the ids, so a correction made upstream reaches everyone and no
licensed data is copied here.

`character` is who they play, as credited. When two performers play one character (younger and older
versions, say), give each their own key.

An appearance says that `who` is present between `from` and `to`. `presence` is `on-screen` (the
default) or `voice` for someone heard but not seen. One person's appearances of the same presence
must not overlap: two overlapping spans are one span that was split by accident.

### `scenes`

Named stretches, with titles keyed by language tag (`{"en": "...", "de": "..."}`). Scenes must not
overlap. They need not cover the whole runtime.

### `segments`

Stretches a player may offer to skip: `intro`, `outro`, `recap`, `preview` and `commercial`. These
are Jellyfin's media segment types, so a Jellyfin-based consumer can pass them through unchanged.
Segments of the same type must not overlap.

### `music`

A `recording` with a `title` and optionally an `artist` and a MusicBrainz recording id, and a `usage`:
`background` (score or a song under the scene), `on-screen` (performed or played within the story),
`opening` or `closing` titles.

### `trivia`

A fact tied to a stretch of the film, written in the contributor's own words with at least one
source URL. `spoiler: true` marks one a player should hide until asked.

## Provenance

Every timeline entry may say how it came to exist:

| Field | Meaning |
|---|---|
| `source` | `human` (the default when omitted), `face`, `speaker`, `audio-fingerprint`, `shot-detection` or `subtitles` |
| `confidence` | the tool's own score between 0 and 1. **Required** whenever `source` is not `human`. |
| `reviewed` | whether a person has checked the entry. **Required** whenever `source` is not `human`. |

Consumers decide for themselves whether to show unreviewed entries. A human entry counts as reviewed.

## What is deliberately not here

- **Names, photos and biographies.** They belong to TMDB, Wikidata and MusicBrainz and are referenced
  by id.
- **Face embeddings or any other biometric data.** A generator may compute them; only the labelled
  time spans it produces are published.
- **Text copied from IMDb, Amazon X-Ray, Tunefind, fan wikis or any other source** whose licence does
  not allow it. See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Versioning

`schemaVersion` is `1`. Additions that old files still satisfy (a new optional field, a new enum
value) stay in version 1. Anything that would make an existing file invalid or change its meaning is
version 2, in `schema/v2/`, and the files are migrated in the same change.
