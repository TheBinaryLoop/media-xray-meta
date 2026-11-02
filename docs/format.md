# The media-xray format, version 1

The data for one **release** of one film or episode is a small set of JSON files side by side: who is
on screen when, what music is playing, what the scenes are called, which stretches can be skipped, and
trivia tied to a moment. The machine-readable definitions are
[`schema/v1/xray.schema.json`](../schema/v1/xray.schema.json) and
[`schema/v1/language.schema.json`](../schema/v1/language.schema.json) (JSON Schema 2020-12). This
document covers what the schemas cannot say.

## Files

An item is one **timeline file** and one **language file** per language:

| File | Holds |
|---|---|
| `<edition>.xray.json` | Everything that is the same in every language: ids, the reference release, segments, people (by id), appearances, scene boundaries, music |
| `<edition>.<language>.xray.json` | Everything that depends on a language: anchors taken from that language's audio and subtitles, scene titles, character names, trivia |

`<language>` is a lower-case BCP 47 tag (`en`, `de`, `pt-br`) and matches the file's own `language`.
Splitting by language lets a translator add one language without touching any other, keeps each
diff to one language, and lets a player fetch only the languages it needs. A language file never
repeats times or ids from the timeline: it refers to scenes by their `id` and to people by their key.

Items live at:

| What | Directory |
|---|---|
| Film | `movies/tmdb-<TMDB movie id>/` |
| Episode | `tv/tmdb-<TMDB series id>/s<NN>e<NN>/` |

so *Bones* S01E01 is `tv/tmdb-1911/s01e01/original.xray.json`, with `original.en.xray.json` and
`original.de.xray.json` beside it. Season and episode numbers are zero-padded to at least two digits
and follow TMDB's numbering (specials are season 0). The directory follows from the timeline's
`title`, the file names from its `reference.edition`, and `tools/validate.py` rejects files whose
names and contents disagree.

TMDB is the key because it numbers films, series, seasons and episodes in one consistent scheme. The
other ids (`imdb`, `tvdb`, `wikidata`) are there so consumers keyed on something else can still find
the item.

## The reference timeline

**Every time in an item is a position in one specific release**, the one named by `reference`,
counted from its first frame. That is the most important rule in this format and the reason anchors
exist.

The same film is not the same timeline everywhere. A different cut adds or removes scenes. A PAL
release plays 4% fast. One encode keeps the distributor logos and another trims them. "Ben arrives at
00:14:05" is true for exactly one of those. So the timeline states:

- `edition`: which cut. Different cuts are different items, because a scene that exists in only one
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
consumer finds both numbers. Each is a short stretch, in the language of the file it is in, that can
be recognised in a local copy:

- `subtitle`: a line of dialogue, with the times it is on screen in the reference. Match it fuzzily
  against the local subtitle track in that language. Easy for a person to add by hand.
- `chromaprint`: a [Chromaprint](https://acoustid.org/chromaprint) fingerprint of that language's
  audio track between `from` and `to`, in the compressed base64url form `fpcalc` prints by default
  (not its `-raw` output). The algorithm is encoded in the fingerprint. Decode it
  (`chromaprint_decode_fingerprint`) and slide it over the raw fingerprint of the local track in the
  same language; a match has a bit error rate around 10% or less, where unrelated audio sits around
  50%.

### Dubbed tracks

Dialogue is part of a Chromaprint fingerprint, so an anchor taken from the English track does not
match the German dub of the same moment. Many copies carry only a dub, which is why anchors live in
the language files: the German file fingerprints the German track, ideally at the same moments as the
English one. A consumer matches each of its audio tracks against the anchors of that track's language
and uses whichever matches. The original language should be present whenever the release has it.

### Copies at a different speed

Subtitle anchors work at any speed, since only the text is compared. A Chromaprint anchor does not:
a European 25 fps release of something shot at 24000/1001 fps runs about 4% fast with the pitch
raised to match, and its fingerprint no longer lines up with one taken at the original speed. So
before matching, a consumer whose audio does not match as-is should resample it by each of the
common ratios and try again:

| Reference | Local copy | Resample the local audio by |
|---|---|---|
| 25 | 24000/1001 | 1.0427 (= 25 × 1001 / 24000), speeding it up |
| 24000/1001 | 25 | 0.9590 (= 24000 / 1001 / 25), slowing it down |
| 25 | 24 | 1.0417 |
| 24 | 25 | 0.96 |

"Resample by r" here means playing the audio r times as fast, changing speed and pitch together as
the PAL speed-up did (for example ffmpeg's `asetrate`), not a pitch-preserving time stretch. A match
found this way gives a position on the resampled audio; multiplying it by r gives the position in the
local file. With a match for every anchor, fitting the mapping below recovers the scale directly.

An item needs at least two anchors in at least one language, and they should be far apart: two
anchors near the start fix the offset but say almost nothing about the scale. The validator warns
when a language's anchors cover less than half the runtime.

A consumer should find the mapping from every anchor it can match (least squares over the matched
pairs). It should **show no time-coded data at all** if fewer than two anchors match, or if they
disagree by more than a second after fitting. Wrong data at the wrong moment is worse than none. Data
that is not tied to a time (the people list, say) can still be shown.

## Languages

Everything a viewer reads is either in a language file or fetched by id in the viewer's language:
scene titles, character names and trivia are the former; titles, performers' names, photos and
biographies the latter. The timeline holds no text for viewers. Its only plain strings are labels for
whoever reviews the file (`title.name`, `people.*.name`) and proper names that are not translated (a
song's title and artist).

A language file holds whatever has been written in that language, and nothing has to be complete: a
German file may carry only anchors, or only a few scene titles. A consumer showing German falls back
to whatever it prefers (often the original language) for anything the German file lacks.

## Sections

All timeline entries have `from` and `to` (end exclusive). Each list is kept sorted by `from` (then
`to`), which the validator enforces, so a new entry shows up as an insertion in a diff.

### Timeline: `people` and `appearances`

`people` is keyed by a short slug that only means something inside the item (`ben`, `barbra`,
`young-ellie`). Each person carries at least one external id (`tmdb`, `imdb` or `wikidata`) and a
`name`. The name is a label for whoever is reviewing the file. Consumers should take what they
display (name, photo, biography) from the ids, so a correction made upstream reaches everyone and no
licensed data is copied here. When two performers play one character (younger and older versions,
say), give each their own key.

An appearance says that `who` is present between `from` and `to`. `presence` is `on-screen` (the
default) or `voice` for someone heard but not seen. One person's appearances of the same presence
must not overlap: two overlapping spans are one span that was split by accident.

### Timeline: `scenes`

Stretches with a stable `id` (a slug, unique within the item). Their titles are in the language files.
Scenes must not overlap. They need not cover the whole runtime.

### Timeline: `segments`

Stretches a player may offer to skip: `intro`, `outro`, `recap`, `preview` and `commercial`. These
are Jellyfin's media segment types, so a Jellyfin-based consumer can pass them through unchanged.
Segments of the same type must not overlap. An `outro` covers the credits only; a scene after the
credits is not part of it, so skipping the credits never skips it.

### Timeline: `music`

A `recording` with a `title` and optionally an `artist` and a MusicBrainz recording id, and a `usage`:
`background` (score or a song under the scene), `on-screen` (performed or played within the story),
`opening` or `closing` titles.

### Language: `scenes` and `characters`

`scenes` maps scene ids to their titles in this language. `characters` maps people keys to who they
play, as credited in this language: dubs rename characters.

### Language: `trivia`

A fact tied to a stretch of the film, written in this language in the contributor's own words with at
least one source URL. `spoiler: true` marks one a player should hide until asked. Trivia is not
expected to be a translation of another language's: each language collects its own.

## Provenance

Every timeline entry, and every trivia entry, may say how it came to exist:

| Field | Meaning |
|---|---|
| `source` | `human` (the default when omitted), `face`, `speaker`, `audio-fingerprint`, `shot-detection`, `video-analysis` (picture measurements such as black frames or brightness) or `subtitles` |
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

`schemaVersion` is `1` in every file. Additions that old files still satisfy (a new optional field, a
new enum value) stay in version 1. Anything that would make an existing file invalid or change its
meaning is version 2, in `schema/v2/`, and the files are migrated in the same change.
