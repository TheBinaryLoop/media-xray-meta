"""Turn the researched Bones trivia drafts into per-episode trivia files for enrich.py.
Entries are about the whole episode unless their moment can be placed: by a transcript line, or by the
verified music cue of the song the moment is about. Series-wide entries are kept aside (the format has no
series-level item yet). Usage: bones_trivia.py WORK"""
import json, re, sys
from pathlib import Path

work = Path(sys.argv[1])
drafts = json.loads((work / 'trivia-drafts' / 'bones.json').read_text())
recordings = json.loads((work / 'music' / 'recordings.json').read_text())

# How to place each documented moment: ('transcript', regex) or ('song', title).
PLACE = {
    ('s01e01', 'Scully and Mulder'): ('transcript', r'Mulder'),
    ('s01e15', 'Hot Blooded'): ('song', 'Hot Blooded'),
    ('s04e25', 'Stewie'): ('transcript', r'Stewie'),
}

def place(key, moment):
    for (k, marker), (how, what) in PLACE.items():
        if k != key or marker not in moment: continue
        if how == 'transcript':
            f = work / 'transcripts' / f'{key}.json'
            if not f.exists(): return None
            hits = [s for s in json.loads(f.read_text()) if re.search(what, s['text'])]
            return (hits[0]['start'], hits[0]['end']) if hits else None
        f = work / 'music' / f'{key}.json'
        if not f.exists(): return None
        cues = [c for c in json.loads(f.read_text()) if recordings.get(c['mbid'], {}).get('title', '').startswith(what)]
        return (min(c['from'] for c in cues), max(c['to'] for c in cues)) if cues else None
    return None

out_dir = work / 'trivia'; out_dir.mkdir(exist_ok=True)
placed = whole = 0
for key, entries in drafts.items():
    if key == 'series':
        (work / 'trivia-drafts' / 'bones-series.json').write_text(json.dumps(entries, ensure_ascii=False, indent=1))
        continue
    data = {'en': [], 'de': []}
    for e in entries:
        span = place(key, e['moment']) if e.get('moment') else None
        for lang in ('en', 'de'):
            item = {}
            if span: item.update({'from': span[0], 'to': span[1]})
            item.update({'text': e[lang], 'sources': e['sources']})
            if e.get('spoiler'): item['spoiler'] = True
            item.update({'source': 'language-model', 'confidence': 0.9, 'reviewed': False})
            data[lang].append(item)
        placed += bool(span); whole += not span
    (out_dir / f'{key}.json').write_text(json.dumps(data, ensure_ascii=False, indent=1))
print(len(drafts) - 1, 'episodes,', placed, 'placed at a moment,', whole, 'about the whole episode')
