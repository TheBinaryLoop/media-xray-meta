"""Transcribe an item's full audio with timestamps (internal use only; never published).
Usage: transcribe.py WORK KEY [MODEL] [LANG]"""
import json, subprocess, sys, time
from pathlib import Path
import numpy as np
from faster_whisper import WhisperModel
work = Path(sys.argv[1]); key = sys.argv[2]
model_name = sys.argv[3] if len(sys.argv) > 3 else 'small.en'
lang = sys.argv[4] if len(sys.argv) > 4 else 'en'
dest = work / 'transcripts' / f'{key}.json'
pcm = subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', str(work / 'fullaudio' / f'{key}.opus'),
                      '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], check=True, capture_output=True).stdout
x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
t0 = time.time()
model = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=12)
segments, info = model.transcribe(x, language=lang, vad_filter=True, word_timestamps=False, beam_size=1)
out = [{'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip()} for s in segments]
dest.write_text(json.dumps(out, ensure_ascii=False))
print(key, len(out), 'segments', round(time.time() - t0), 's for', round(len(x) / 16000), 's audio')
