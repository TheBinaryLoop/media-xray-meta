import json, sys, statistics as st
from pathlib import Path
for s in sys.argv[2:]:
    r = json.load(open(Path(sys.argv[1]) / 'results' / f's{int(s):02d}.json'))
    il = [e['intro']['end'] - e['intro']['start'] for e in r.values() if 'intro' in e]
    ol = [e['runtime'] - e['outro']['start'] for e in r.values() if 'outro' in e]
    print(f"S{int(s):02d}: {len(r)} eps, intro {len(il)} (len {min(il):.1f}-{max(il):.1f}, median {st.median(il):.1f}), "
          f"outro {len(ol)} (len {min(ol):.1f}-{max(ol):.1f}, median {st.median(ol):.1f}), "
          f"anchors {sum(len(e['anchors']) for e in r.values())}/{3*len(r)}")
    for k, e in r.items():
        flags = list(e['notes'])
        if 'intro' in e:
            i = e['intro']; L = i['end'] - i['start']
            if abs(L - st.median(il)) > 2.5: flags.append(f'intro length {L:.1f}')
            if i['spread'][0] > 0.5: flags.append(f'intro start spread {i["spread"][0]}')
            if i['confidence'] < 0.9: flags.append(f'intro confidence {i["confidence"]}')
        if 'outro' in e:
            L = e['runtime'] - e['outro']['start']
            if L < 20 or L > 90: flags.append(f'outro length {L:.1f}')
        if flags: print('  ', k, '; '.join(flags))
