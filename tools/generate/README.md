# How the generated data was made

The scripts here produced the machine-made entries in this repository (*Bones*, *Deadpool*). They
are kept as a record of the method and a starting point for other titles, not as a polished tool:
paths, the media host and per-title constants are passed or edited by hand.

Everything they produce is marked `source` + `confidence` + `reviewed: false`.

They need ffmpeg (on the media host and locally), `fpcalc` with libchromaprint, Python 3.12+ with
numpy, and for `langcheck.py` faster-whisper.

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
