"""Cast, characters and German voices for every item. Usage: people.py WORK -> WORK/people/<key>.json

people:     TMDB credits (regulars, then guests, in billing order) with TMDB, IMDb and Wikidata ids
characters: en from TMDB; de from the German Wikipedia dub tables, matched on the actor's Wikidata id
voices:     de from the same tables; a season-qualified voice wins over an unqualified one"""
import json, re, sys, unicodedata
from pathlib import Path

work = Path(sys.argv[1]); tm = work / 'tmdb'; out = work / 'people'; out.mkdir(exist_ok=True)

def slug(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-') or 'person'

def norm(name):
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower())

def person_ids(pid):
    f = tm / f'person-{pid}-ids.json'
    d = json.loads(f.read_text()) if f.exists() else None
    ids = {'tmdb': pid}
    if d and d.get('imdb_id') and re.fullmatch(r'nm[0-9]{7,}', d['imdb_id']): ids['imdb'] = d['imdb_id']
    if d and d.get('wikidata_id') and re.fullmatch(r'Q[1-9][0-9]*', d['wikidata_id']): ids['wikidata'] = d['wikidata_id']
    return ids

def dub_lookup(table):
    by_qid, by_name = {}, {}
    for row in table:
        for actor in row['actors']:
            if actor['wikidata']: by_qid[actor['wikidata']] = row
            by_name[norm(actor['name'])] = row
    return by_qid, by_name

def voice_for(row, season):
    voices = [v for v in row['voices'] if v['wikidata']]
    qualified = [v for v in voices if v['seasons'] and season is not None and v['seasons'][0] <= season <= v['seasons'][1]]
    if qualified: return qualified[0]
    # An unqualified voice covers every season no qualified voice claims.
    plain = [v for v in voices if not v['seasons']]
    if season is not None and any(v['seasons'] for v in row['voices']) and not plain: return None
    return plain[0] if plain else None

def build(credits, dub, season, guest_key='guest_stars'):
    by_qid, by_name = dub_lookup(dub)
    people, chars_en, chars_de, voices_de = {}, {}, {}, {}
    seen = {}
    billing = 0
    entries = [(p, 'main') for p in credits.get('cast', [])] + [(p, 'guest') for p in credits.get(guest_key, []) or []]
    for p, credit in entries:
        if p['id'] in seen:                         # one person credited twice: join the characters
            key = seen[p['id']]
            if p.get('character'): chars_en[key] = ' / '.join(filter(None, [chars_en.get(key), p['character'].strip()]))
            continue
        key = slug(p['name'])
        if key in people: key = f"{key}-{p['id']}"
        seen[p['id']] = key
        ids = person_ids(p['id'])
        people[key] = {'name': p['name'], **ids, 'credit': credit, 'billing': billing}
        billing += 1
        if p.get('character', '').strip(): chars_en[key] = p['character'].strip()
        row = by_qid.get(ids.get('wikidata')) or by_name.get(norm(p['name']))
        if row:
            chars_de[key] = row['role']
            v = voice_for(row, season)
            if v: voices_de[key] = {'name': v['name'], 'wikidata': v['wikidata']}
    return {'people': people, 'characters': {'en': chars_en, 'de': chars_de}, 'voices': {'de': voices_de}}

dp = json.loads((tm / 'movie-293660-credits.json').read_text())
(out / 'deadpool.json').write_text(json.dumps(build({'cast': dp['cast']}, json.loads((work / 'dub' / 'deadpool.json').read_text()), None),
                                              ensure_ascii=False, indent=1))
bones = json.loads((work / 'dub' / 'bones.json').read_text())
n = 0
for f in sorted(tm.glob('tv-1911-s*e*-credits.json')):
    m = re.search(r's(\d+)e(\d+)', f.name); season = int(m.group(1))
    data = build(json.loads(f.read_text()), bones, season)
    (out / f"s{season:02d}e{int(m.group(2)):02d}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    n += 1
print(n + 1, 'items')
