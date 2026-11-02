# Contributing

Thank you for helping. Every contribution is a pull request that adds or edits `*.xray.json` files.
The format is described in [docs/format.md](docs/format.md).

## Licence: read this first

Everything in this repository is dedicated to the public domain under [CC0 1.0](LICENSE). By opening
a pull request you confirm that you have the right to dedicate what you submit, and that you do so.

That rules out copying from sources whose terms do not allow it, which includes most places this
kind of data is found:

- IMDb (trivia, goofs, soundtrack lists, character names beyond the bare credit)
- Amazon Prime Video's X-Ray
- Tunefind, WhatSong and similar soundtrack sites
- Fandom and other fan wikis
- TMDB text and images. Reference TMDB by **id**; do not copy its overviews or biographies.

**Facts are fine; someone else's wording is not.** "The copyright notice was dropped when the film was
retitled" is a fact anyone may state. Copying the sentence in which a website stated it is not. Write
trivia in your own words and link where you learned it. Wikipedia is a good source to cite, but its
text is CC BY-SA and must not be pasted in.

## Making a file

1. Decide which **release** you are timing: the cut, and the copy you are watching. Every time you
   write is a position in that copy. Describe it in `reference.release`.
2. Put the file at the path for its TMDB id and edition (see [docs/format.md](docs/format.md#where-a-file-lives)).
3. Add at least two **anchors**, one near the start and one near the end. A subtitle line with its
   on-screen times is the easiest kind to add by hand.
4. Add whatever you know: scenes, segments, appearances, music, trivia. A file with only an intro
   segment and two anchors is already useful.
5. Run the checks:

   ```sh
   python -m pip install -r requirements.txt
   python tools/validate.py --fix   # sorts timelines and normalises formatting
   python tools/validate.py
   python -m unittest discover -s tests
   ```

## Machine-generated data

Entries produced by a tool (face recognition, audio fingerprinting, shot detection) must say so with
`source`, carry the tool's `confidence`, and set `reviewed: false` until a person has checked them.
Mark an entry `reviewed: true` only after you have looked at that moment yourself.

Never commit face embeddings, voice prints or any other biometric data. Publish only the labelled
time spans.

## Review

A reviewer checks that the path and ids match the title, that the anchors are spread out, that
trivia has sources and is not copied text, and spot-checks a few times against a copy of the
release where they can.
