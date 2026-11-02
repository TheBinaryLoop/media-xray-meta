"""Parse FOX's archived Bones music pages (seasons 1-5) into episode -> songs, matched to TMDB episode numbers.
Usage: fox_lists.py WORK -> WORK/bones/fox/songs.json"""
import difflib, html, json, re, sys
from pathlib import Path
work = Path(sys.argv[1])
titles = {}
for line in open(work / 'bones' / 'tmdb-titles.tsv', encoding='utf-8'):
    s, e, name = line.rstrip('\n').split('\t'); titles[(int(s), int(e))] = name
norm = lambda t: re.sub(r'[^a-z0-9]', '', t.lower().replace('&', 'and'))
out = {}
for season in range(1, 6):
    h = (work / 'bones' / 'fox' / f'season{season}.html').read_text(encoding='latin-1')
    t = re.sub(r'(?s)<script.*?</script>|<style.*?</style>', '', h)
    t = html.unescape(re.sub(r'<[^>]+>', '\n', t))
    lines = [l.strip() for l in t.split('\n') if l.strip()]
    i = next(k for k, l in enumerate(lines) if l.startswith('Season 5')) + 1
    current = None
    for l in lines[i:]:
        if l in ('Prev', 'Next') or l.startswith('BONES,'): break
        m = re.match(r'^[“"](.+?)[”"]\s*(?:\(([^)]*)\))?\s*[-–]\s*(.+)$', l)
        if m and current:
            out.setdefault(current, []).append({'title': m.group(1).strip(), 'artist': m.group(3).strip(),
                                                **({'note': m.group(2)} if m.group(2) else {})})
        elif l.startswith(('"', '“')):
            # A piece without an artist (played on screen, say): nothing to look up, but not a heading either.
            continue
        elif not l.startswith('|'):
            candidates = {k: v for k, v in titles.items() if k[0] == season}
            best = max(candidates, key=lambda k: difflib.SequenceMatcher(None, norm(l), norm(candidates[k])).ratio())
            r = difflib.SequenceMatcher(None, norm(l), norm(candidates[best])).ratio()
            current = f's{best[0]:02d}e{best[1]:02d}' if r > 0.75 else None
            if not current: print('unmatched heading', season, repr(l), '->', candidates[best], round(r, 2))
(work / 'bones' / 'fox' / 'songs.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(len(out), 'episodes,', sum(map(len, out.values())), 'songs')
