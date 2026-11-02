"""German fingerprints of the moments the English anchors cover, verified like the English ones.
Usage: dubs.py WORK SEASON  -> WORK/dubs/sNN.json {episode: [anchor, ...]}"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); import fp
work = Path(sys.argv[1]); season = int(sys.argv[2])
results = json.load(open(work / 'results' / f's{season:02d}.json'))
out, rejected = {}, []
for key, ep in results.items():
    for a in ep['anchors']:
        if a['language'] != 'en': continue
        path = work / 'dub' / f"{key}.de.{round(a['start'] * 1000)}.flac"
        if not path.exists(): rejected.append((key, a['start'], 'no audio')); continue
        comp = fp.compressed(str(path), 30, 20)
        needle, _ = fp.decode(comp)
        if len(set(needle.tolist())) < 0.5 * len(needle): rejected.append((key, a['start'], 'near-silence')); continue
        hay = fp.raw(str(path))
        res = fp.align(needle, hay, min_overlap=len(needle))
        best = res[0]; second = next((r for r in res if abs(r[1] - best[1]) > 16), None)
        if abs(best[1] * fp.HOP - 30) > 0.25 or best[0] > 0.10: rejected.append((key, a['start'], f'self-match {best}')); continue
        if second is not None and second[0] < 0.30: rejected.append((key, a['start'], f'repeats {second[0]:.2f}')); continue
        out.setdefault(key, []).append(dict(start=a['start'], end=a['end'], fingerprint=comp, language='de',
                                             ber=round(best[0], 3), second=round(second[0], 3) if second else None))
(work / 'dubs').mkdir(exist_ok=True)
json.dump(out, open(work / 'dubs' / f's{season:02d}.json', 'w'), indent=1)
print(f'S{season:02d}: {sum(map(len, out.values()))} German anchors, {len(rejected)} rejected')
for r in rejected: print('  ', *r)
