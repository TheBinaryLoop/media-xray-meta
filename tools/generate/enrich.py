"""Add cast, music, characters, voices and trivia to the items already in the repository.
Usage: enrich.py WORK REPO KEY...   (KEY: deadpool or sNNeNN)

Music cues: pieces of the same recording less than MERGE_GAP apart are one cue; where two recordings claim
the same stretch, the closer match wins. Times are the item's own (the reference) timeline."""
import json, sys
from pathlib import Path

work, repo = Path(sys.argv[1]), Path(sys.argv[2])
MERGE_GAP = 20.0
recordings = json.loads((work / 'music' / 'recordings.json').read_text())   # mbid -> {title, artist}

def ts(seconds):
    ms = round(seconds * 1000)
    h, rest = divmod(ms, 3600_000); m, rest = divmod(rest, 60_000); s, ms = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

def item_paths(key):
    if key == 'deadpool':
        return repo / 'movies' / 'tmdb-293660', 'theatrical'
    return repo / 'tv' / 'tmdb-1911' / key, 'original'

def music_cues(key, runtime, outro):
    f = work / 'music' / f'{key}.json'
    if not f.exists(): return []
    raw = sorted(json.loads(f.read_text()), key=lambda c: (c['mbid'], c['from']))
    merged = []
    for c in raw:
        if merged and merged[-1]['mbid'] == c['mbid'] and c['from'] - merged[-1]['to'] <= MERGE_GAP:
            m = merged[-1]; m['to'] = max(m['to'], c['to']); m['errs'].append(c['err']); m['chunks'] += c['chunks']
        else:
            merged.append({'mbid': c['mbid'], 'from': c['from'], 'to': c['to'], 'errs': [c['err']], 'chunks': c['chunks']})
    for m in merged: m['err'] = min(m['errs'])
    # Overlapping cues of different recordings: keep the closer match.
    merged.sort(key=lambda m: m['err'])
    kept = []
    for m in merged:
        clash = [k for k in kept if min(k['to'], m['to']) - max(k['from'], m['from']) > 0.5 * min(k['to'] - k['from'], m['to'] - m['from'])]
        if not clash: kept.append(m)
    out = []
    for m in sorted(kept, key=lambda m: m['from']):
        rec = recordings[m['mbid']]
        cue = {'from': ts(max(0.0, m['from'])), 'to': ts(min(runtime, m['to'])),
               'recording': {'title': rec['title'], **({'artist': rec['artist']} if rec.get('artist') else {}), 'musicbrainz': m['mbid']}}
        if outro and m['from'] >= outro[0] - 1 and m['to'] <= outro[1] + 1: cue['usage'] = 'closing'
        if rec.get('usage'): cue['usage'] = rec['usage']
        cue.update({'source': 'audio-fingerprint', 'confidence': round(max(0.0, min(1.0, 1 - 2 * m['err'])), 2), 'reviewed': False})
        out.append(cue)
    return out

def millis(t):
    h, m, rest = t.split(':'); s, ms = rest.split('.')
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)

def write(path, doc):
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

for key in sys.argv[3:]:
    directory, edition = item_paths(key)
    tl_path = directory / f'{edition}.xray.json'
    if not tl_path.exists(): print(key, 'no timeline'); continue
    tl = json.loads(tl_path.read_text())
    runtime = millis(tl['reference']['runtime']) / 1000
    outro = next(((millis(s['from']) / 1000, millis(s['to']) / 1000) for s in tl.get('segments', []) if s['type'] == 'outro'), None)
    people = json.loads((work / 'people' / f'{key}.json').read_text())
    # Rebuild in schema order so repeated runs give the same file.
    new = {k: tl[k] for k in ('$schema', 'schemaVersion', 'title', 'reference') if k in tl}
    if people['people']: new['people'] = people['people']
    faces_file = work / 'faces' / 'results' / f'{key}.frames.json'
    if faces_file.exists():
        apps = [{'who': a['who'], 'from': ts(a['from']), 'to': ts(min(runtime, a['to'])), 'source': 'face',
                 'confidence': round(min(1.0, a['similarity']), 2), 'reviewed': False}
                for a in json.loads(faces_file.read_text())['appearances']
                if a['who'] in people['people'] and a['to'] - a['from'] >= 2]
        if apps: new['appearances'] = apps
    elif tl.get('appearances'): new['appearances'] = tl['appearances']
    for k in ('scenes', 'segments'):
        if tl.get(k): new[k] = tl[k]
    cues = music_cues(key, runtime, outro)
    if cues: new['music'] = cues
    write(tl_path, new)

    trivia_file = work / 'trivia' / f'{key}.json'
    trivia = json.loads(trivia_file.read_text()) if trivia_file.exists() else {}
    for lang in ('en', 'de'):
        lp = directory / f'{edition}.{lang}.xray.json'
        doc = json.loads(lp.read_text()) if lp.exists() else {
            '$schema': 'https://raw.githubusercontent.com/TheBinaryLoop/media-xray-meta/master/schema/v1/language.schema.json',
            'schemaVersion': 1, 'language': lang}
        new_l = {k: doc[k] for k in ('$schema', 'schemaVersion', 'language', 'anchors') if k in doc}
        if doc.get('scenes'): new_l['scenes'] = doc['scenes']
        chars = {k: v for k, v in people['characters'].get(lang, {}).items() if k in people['people']}
        if chars: new_l['characters'] = chars
        voices = people.get('voices', {}).get(lang, {})
        if voices: new_l['voices'] = voices
        items = []
        for t in trivia.get(lang, []):
            e = dict(t)
            if 'from' in e: e['from'], e['to'] = ts(e['from']), ts(min(runtime, e['to']))
            items.append(e)
        if items: new_l['trivia'] = items
        if len(new_l) > 3 or lp.exists(): write(lp, new_l)
    print(key, len(people['people']), 'people,', len(cues), 'cues,', len(trivia.get('en', [])), 'trivia')
