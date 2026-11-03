# How the generated data was made

The scripts here produced the machine-made entries in this repository (*Bones*, *Deadpool*). They
are kept as a record of the method and a starting point for other titles, not as a polished tool:
paths, the media host and per-title constants are passed or edited by hand.

Everything they produce is marked `source` + `confidence` + `reviewed: false`.

They need ffmpeg (on the media host and locally), `fpcalc` with libchromaprint, Python 3.12+ with
numpy, faster-whisper for `langcheck.py` and `transcribe.py`, and OpenCV for the face scripts. API
access: a TMDB key and an AcoustID application key, kept outside the repository.

## Principle

Nothing is taken on trust from a single detector. Each boundary is found by one method and checked
by an independent one, and an episode whose evidence disagrees gets **no** segment rather than a
guess. Boundaries were also spot-checked against the frames by eye during development.

## Steps

Heavy work (decoding) runs at `nice 19` / `ionice idle` on the machine that holds the media, one
thread per job; only small extracts leave it.

1. **Audio windows** (`plan.py`, `cut.sh`, `cut-ger.sh`, `cut-first-track.sh`): mono 11025 Hz FLAC of
   the intro region, the ending, and three 100 s contexts at 20/50/80 % of the runtime, per language.
2. **Picture data** (`plan_thumbs.py`, `thumbs.sh`, `plan_luma.py`, `luma.sh`, `cards.sh`): every
   frame of the intro region as a 32×18 grey thumbnail; 5 fps brightness (`YAVG`) of the ending; 5 fps
   90th-percentile brightness (`YHIGH`) from the credits candidate onwards.
3. **Intros** (`analyze.py`, `vintro.py`, `spectrum.py`, `fp.py`): an episode's intro is the run of
   frames it shares, frame for frame, with other episodes of its season, confirmed by the shared theme
   audio (Chromaprint). A season may switch title-sequence versions midway, so agreement is counted
   among episodes showing the same sequence, and each boundary is the outermost value two partners
   agree on. The intro ends where the episode's own picture leaves black.
4. **Credits**: the last long dark stretch that runs into the closing logos, started at the first
   frame that is a credit card (at least 90 % pure black, so a dim final scene does not count). For a
   film, the credits end at the cut to a post-credits scene, so skipping them never skips it.
5. **Anchors** (`analyze.py`, `dubs.py`, `movie_anchors.py`): 20 s Chromaprint fingerprints in each
   context, accepted only if found at their own position (±0.25 s, bit error ≤ 10 %), unique within
   the context (next best ≥ 30 %), not near-silence, and still found after simulating a copy at the
   other common frame rate and resampling it back as `docs/format.md` describes. The dub is
   fingerprinted at the same moments and verified the same way.
6. **Language check** (`langcheck.py`): every track used for anchors was confirmed by speech
   recognition to be the language it is labelled as.
7. **Files** (`gen.py`): one timeline file and one file per language per item.

`summary.py` prints per-season distributions and outliers, which is where every manual check started.

## Cast, music, trivia and faces

8. **Cast** (`tmdb_credits.py`, `dub_tables.py`, `people.py`): credits per episode and film from the
   TMDB API, with each person's IMDb and Wikidata ids. English character names come from TMDB. German
   character names and voice actors come from the dub tables on German Wikipedia (which cite
   Synchronkartei), matched to the cast by Wikidata id, with the voice chosen by season where it
   changed. TMDB's own German character names are not used: they are usually the English strings.
9. **Music** (`acoustid_ref.py`, `music_match.py`, `mb_candidates.py`, `fox_lists.py`,
   `music_bones.py`): a recording is only placed where its fingerprint is found. Reference fingerprints
   for MusicBrainz recordings come from AcoustID (used locally, not published); 4 s chunks of them are
   matched against the item's whole soundtrack (slowed back to the original speed for a PAL release),
   and consistent matches are chained into cues. Candidates are the soundtrack albums on MusicBrainz
   and, for *Bones* seasons 1 to 5, the songs FOX listed for each episode on its own website (archived
   on the Wayback Machine). AcoustID's lookup service was tried for unknown songs and does not work on
   music under dialogue or not aligned with the start of a recording, so songs nobody listed are not
   found. AcoustID fingerprints cover only about the first two minutes of a recording, so a cue ends
   where its matches end, and a song used from a later point is missed.
   The speed is checked per season, not assumed: most *Bones* seasons of this release are PAL-sped,
   season 4 is not, and candidates for seasons 6 to 12 are matched at both speeds (a recording at the
   wrong speed does not match). For seasons 6 to 12, which FOX never listed, candidates come from
   lyrics: `lyrics.py` transcribes the music-heavy stretches, songs are identified from the sung lines
   by searching their lyrics (never from lists of the show's music), and only the ones whose
   fingerprint is then found are kept, about half of them.
10. **Trivia** (`deadpool_trivia.py`, `bones_trivia.py`): facts from pages fetched and read for the
    purpose (English and German Wikipedia), written anew in English and German, each with its source.
    A fact is tied to a moment only where a transcript line or a matched music cue places it;
    otherwise it is about the whole item. Transcripts (`transcribe.py`) are internal and never published.
11. **Faces** (`frames_gpu.sh`, `ref_faces.py`, `faces.py`): one frame per second, decoded on the media
    host's GPU and paused while it transcodes for a viewer. Faces are detected with YuNet and compared
    with SFace (OpenCV model zoo; MIT and Apache 2.0) against TMDB profile photos of the item's own
    credited cast only. A face is labelled at cosine similarity 0.45 or more with a margin of 0.08 over
    the runner-up; clusters of faces within the item lend a confident label to their other members.
    Appearances are runs of labelled seconds. Photos and face embeddings stay local and are never
    published; only the time spans are.
12. **Merging** (`enrich.py`): writes cast, music and trivia into the item's files.
