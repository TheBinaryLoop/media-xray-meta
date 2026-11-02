"""Plan German-track windows around each English anchor. Usage: dubplan.py WORK SEASONS OUT"""
import csv, json, sys
from pathlib import Path
work = Path(sys.argv[1]); seasons = [int(s) for s in sys.argv[2].split(',')]
paths = {f"s{int(s):02d}e{int(e):02d}": p for s, e, p, *_ in csv.reader(open(work / 'items.tsv'), delimiter='\t')}
with open(sys.argv[3], 'w') as out:
    for s in seasons:
        for key, ep in json.load(open(work / 'results' / f's{s:02d}.json')).items():
            for a in ep['anchors']:
                if a['language'] != 'en': continue
                out.write(f"{key}.de.{round(a['start'] * 1000)}\t{paths[key]}\t{a['start'] - 30:.3f}\t80\n")
