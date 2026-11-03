"""Find where known recordings play in an item, by matching 4 s chunks of their reference fingerprints
(from acoustid_ref.py) against the item's audio and chaining consistent matches.

Usage: music_match.py WORK KEY RATE MBID_LIST_FILE  -> WORK/music/KEY.json
RATE corrects the item's playback speed (0.959040959 for a PAL-sped release, 1 otherwise)."""
import json, os, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent)); import fp

work, key, rate, listfile = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3]), Path(sys.argv[4])
CHUNK, STEP, MAX_ERR, MIN_CHUNKS = 32, 16, 0.24, 3

with tempfile.TemporaryDirectory() as d:
    wav = os.path.join(d, 'a.wav')
    af = [] if rate == 1 else ['-af', f'aresample=16000,asetrate=16000*{rate},aresample=16000']
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(work / 'fullaudio' / f'{key}.opus'), *af,
                    '-ac', '1', '-ar', '11025', wav], check=True)
    hay = fp.raw(wav)
# Every window of CHUNK items, as a view; XOR against a chunk gives all positions at once.
windows = np.lib.stride_tricks.sliding_window_view(hay, CHUNK)
informative_hay = np.array([len(set(w.tolist())) >= CHUNK // 2 for w in windows[::1]])

def chunk_matches(chunk):
    err = np.bitwise_count(np.bitwise_xor(windows, chunk)).sum(axis=1) / (32 * CHUNK)
    good = np.where((err <= MAX_ERR) & informative_hay)[0]
    # Keep local minima only, so one match is one position.
    keep = [i for i in good if err[i] == err[max(0, i - 3):i + 4].min()]
    return [(int(i), float(err[i])) for i in keep]

meta = {}
cues = []
for mbid in [l.strip() for l in listfile.read_text().splitlines() if l.strip()]:
    refs = json.loads((work / 'reffp' / f'{mbid}.json').read_text())
    hits = []   # (film item, ref item, err)
    for r in refs:
        ref = np.array(r['fp'], dtype=np.int64).astype(np.uint32)
        for s in range(0, len(ref) - CHUNK + 1, STEP):
            chunk = ref[s:s + CHUNK]
            if len(set(chunk.tolist())) < CHUNK // 2: continue      # near-silence matches near-silence
            for f, e in chunk_matches(chunk):
                hits.append((f, s, e))
    # Chain hits on the same diagonal (film - ref offset, within 2 items) with increasing positions.
    hits.sort(key=lambda h: (h[0] - h[1], h[0]))
    segs = []
    for f, s, e in hits:
        for seg in segs:
            if abs((f - s) - seg['diag']) <= 2 and 0 < f - seg['last'] <= STEP * 2 + 2:
                seg['last'] = f; seg['n'] += 1; seg['errs'].append(e); seg['ref_last'] = s; break
        else:
            segs.append({'diag': f - s, 'first': f, 'last': f, 'n': 1, 'errs': [e], 'ref_first': s, 'ref_last': s})
    for seg in segs:
        if seg['n'] < MIN_CHUNKS: continue
        # Film times on the item's own timeline (undo the speed correction).
        start = seg['first'] * fp.HOP * rate
        end = (seg['last'] + CHUNK) * fp.HOP * rate
        cues.append({'mbid': mbid, 'from': round(start, 2), 'to': round(end, 2), 'chunks': seg['n'],
                     'err': round(float(np.mean(seg['errs'])), 3),
                     'song_from': round(seg['ref_first'] * fp.HOP, 1), 'song_to': round((seg['ref_last'] + CHUNK) * fp.HOP, 1)})

# Merge overlapping cues of the same recording (several reference fingerprints find the same stretch).
cues.sort(key=lambda c: (c['mbid'], c['from']))
merged = []
for c in cues:
    if merged and merged[-1]['mbid'] == c['mbid'] and c['from'] <= merged[-1]['to'] + 2:
        m = merged[-1]; m['to'] = max(m['to'], c['to']); m['chunks'] += c['chunks']; m['err'] = min(m['err'], c['err'])
        m['song_to'] = max(m['song_to'], c['song_to']); m['song_from'] = min(m['song_from'], c['song_from'])
    else:
        merged.append(dict(c))
(work / 'music').mkdir(exist_ok=True)
(work / 'music' / f'{key}.json').write_text(json.dumps(sorted(merged, key=lambda c: c['from']), indent=1))
print(key, len(merged), 'cues')
