import csv, sys
from pathlib import Path
work = Path(sys.argv[1]); seasons = {int(s) for s in sys.argv[2].split(',')}
T = 1e7
with open(work / 'plan-thumbs.tsv', 'w') as out:
    for s, e, path, ticks, imdb, tvdb, segs in csv.reader(open(work / 'items.tsv'), delimiter='\t'):
        if int(s) not in seasons: continue
        seg = {x.split(':')[0]: int(x.split(':')[3]) / T for x in segs.split(',') if x}
        if '0' in seg:
            out.write(f's{int(s):02d}e{int(e):02d}.intro\t{path}\t{max(0, seg["0"] - 8):.3f}\t55\n')
