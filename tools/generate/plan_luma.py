import csv, sys
from pathlib import Path
work = Path(sys.argv[1]); seasons = {int(s) for s in sys.argv[2].split(',')}
T = 1e7
with open(work / 'plan-luma.tsv', 'w') as out:
    for s, e, path, ticks, imdb, tvdb, segs in csv.reader(open(work / 'items.tsv'), delimiter='\t'):
        if int(s) not in seasons: continue
        rt = int(ticks) / T; key = f's{int(s):02d}e{int(e):02d}'
        seg = {x.split(':')[0]: (int(x.split(':')[3]) / T, int(x.split(':')[4]) / T) for x in segs.split(',') if x}
        cs = seg['1'][0] if '1' in seg else rt - 120
        start = max(0.0, min(cs - 60, rt - 120))
        out.write(f'{key}.ending\t{path}\t{start:.3f}\t{rt - start:.3f}\n')
