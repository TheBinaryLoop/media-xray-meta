"""Transcribe the music-heavy stretches of an episode (no speech filter) to catch song lyrics.
Stretches: gaps of at least MIN_GAP s between transcript lines, outside the intro and credits.
Usage: lyrics.py WORK KEY [MIN_GAP]  -> WORK/lyrics/KEY.json  [{from, to, text}] (internal only)"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
work, key = Path(sys.argv[1]), sys.argv[2]
MIN_GAP = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
lines = json.loads((work / 'transcripts' / f'{key}.json').read_text())
res = json.loads((work / 'bones' / 'results' / f's{key[1:3]}.json').read_text())[key]
skip = [(res[k]['start'], res[k]['end']) for k in ('intro', 'outro') if k in res]
# Music-heavy stretches: transcript segments that are long but nearly wordless (the speech filter spans the
# music with them), and the last four minutes before the credits, where the show places its closing songs.
cand = [(s['start'], s['end']) for s in lines if s['end'] - s['start'] >= 8 and len(s['text'].split()) / (s['end'] - s['start']) < 0.8]
end = res['outro']['start'] if 'outro' in res else res['runtime']
cand.append((max(0.0, end - 240), end))
cand.sort()
gaps = []
for a, b in cand:
    if any(a < y and b > x for x, y in skip if (x, y) != (end, res['runtime'])) and (a, b) != (max(0.0, end - 240), end): continue
    if gaps and a <= gaps[-1][1]: gaps[-1] = (gaps[-1][0], max(gaps[-1][1], b))
    else: gaps.append((a, b))
pcm = subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(work / 'fullaudio' / f'{key}.opus'),
                      '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], check=True, capture_output=True).stdout
x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
model = WhisperModel('small.en', device='cpu', compute_type='int8', cpu_threads=8)
out = []
for a, b in gaps:
    seg, _ = model.transcribe(x[int(a * 16000):int(b * 16000)], language='en', vad_filter=False, beam_size=1,
                              condition_on_previous_text=False)
    text = ' '.join(s.text.strip() for s in seg if s.no_speech_prob < 0.6)
    if len(text.split()) >= 4: out.append({'from': round(a, 1), 'to': round(b, 1), 'text': text})
(work / 'lyrics').mkdir(exist_ok=True)
(work / 'lyrics' / f'{key}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(key, len(gaps), 'gaps,', len(out), 'with words')
