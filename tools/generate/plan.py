"""Plan the audio windows to cut from each Bones episode. Writes plan.tsv: key, path, start, duration."""
import csv, sys
from pathlib import Path

work = Path(sys.argv[1]); seasons = {int(s) for s in sys.argv[2].split(',')}
T = 1e7
rows = []
for s, e, path, ticks, imdb, tvdb, segs in csv.reader(open(work / 'items.tsv'), delimiter='\t'):
    s, e = int(s), int(e)
    if s not in seasons: continue
    runtime = int(ticks) / T
    key = f's{s:02d}e{e:02d}'
    segments = [tuple(x.split(':')) for x in segs.split(',') if x]
    for typ, src, state, a, b in segments:
        a, b = int(a) / T, int(b) / T
        name = {'0': 'intro', '1': 'credits', '3': 'recap', '2': 'preview'}[typ]
        start = max(0.0, a - 30); end = min(runtime, b + 30)
        rows.append((f'{key}.{name}', path, start, end - start))
    # Anchor context windows: 100 s around 20/50/80 % of the runtime. The final anchor positions are
    # chosen later inside these, away from anything that repeats across episodes.
    for pct in (20, 50, 80):
        centre = runtime * pct / 100
        rows.append((f'{key}.ctx{pct}', path, centre - 50, 100.0))
with open(work / 'plan.tsv', 'w') as f:
    for k, p, a, d in rows: f.write(f'{k}\t{p}\t{a:.3f}\t{d:.3f}\n')
print(len(rows), 'windows')
