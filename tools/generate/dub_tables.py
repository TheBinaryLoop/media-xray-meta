"""Parse the German dub tables (Rolle / Darsteller / Synchronsprecher) of a German Wikipedia article and
resolve every linked person to Wikidata. Usage: dub_tables.py WIKITEXT_JSON OUT_JSON

Output: [{role, actors:[{name, wikidata}], voices:[{name, wikidata, seasons:[first,last] | null}]}]"""
import json, re, sys, time, urllib.parse, urllib.request

wikitext = json.load(open(sys.argv[1]))['parse']['wikitext']['*']
UA = {'User-Agent': 'media-xray-meta/0.1 (https://github.com/TheBinaryLoop/media-xray-meta)'}

def links(cell):
    """[[Target|Label]] links in a cell, in order, with any 'Staffel a–b:' qualifier just before each."""
    out = []
    for m in re.finditer(r'(?:<small>\s*(?:Staffel|Ab Staffel)\s*([0-9]+)(?:\s*[–-]\s*([0-9]+))?\s*:?\s*</small>(?:&nbsp;|\s)*)?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', cell):
        first, last, target, label = m.groups()
        seasons = None
        if first:
            ab = 'Ab Staffel' in m.group(0)
            seasons = [int(first), 99 if ab else int(last or first)]
        out.append({'target': target.strip(), 'name': (label or target).strip(), 'seasons': seasons})
    return out

rows = []
for table in re.findall(r'\{\|.*?\n\|\}', wikitext, flags=re.S):
    header = table.split('\n|-', 2)
    if 'Synchronsprecher' not in table or 'Rolle' not in table: continue
    for row in table.split('\n|-')[1:]:
        cells = [c.strip() for c in re.split(r'\n\||\|\|', '\n' + row.split('\n', 1)[-1] if row.startswith(' style') else '\n' + row)
                 if c.strip()]
        cells = [c for c in cells if not c.startswith('!') and not c.startswith('style=')]
        if len(cells) < 3: continue
        role = re.sub(r'<[^>]+>|\[\[|\]\]', '', cells[0]).strip()
        actors = links(cells[1]); voices = links(cells[2])
        if role and actors and voices:
            rows.append({'role': role, 'actors': actors, 'voices': voices})

# Wikidata ids for every linked page, 50 titles per request.
titles = sorted({p['target'] for r in rows for p in r['actors'] + r['voices']})
qid = {}
for i in range(0, len(titles), 50):
    batch = titles[i:i + 50]
    url = 'https://de.wikipedia.org/w/api.php?' + urllib.parse.urlencode(
        {'action': 'query', 'prop': 'pageprops', 'ppprop': 'wikibase_item', 'redirects': 1, 'format': 'json', 'titles': '|'.join(batch)})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        q = json.load(r)['query']
    alias = {n['from']: n['to'] for n in q.get('normalized', []) + q.get('redirects', [])}
    found = {p['title']: p.get('pageprops', {}).get('wikibase_item') for p in q['pages'].values()}
    for t in batch:
        target = alias.get(alias.get(t, t), alias.get(t, t))
        qid[t] = found.get(target)
    time.sleep(1)
for r in rows:
    for p in r['actors'] + r['voices']:
        p['wikidata'] = qid.get(p['target'])
json.dump(rows, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
print(len(rows), 'roles,', sum(1 for r in rows for p in r['actors'] + r['voices'] if not p['wikidata']), 'links without Wikidata')
