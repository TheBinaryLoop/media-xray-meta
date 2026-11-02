"""Spoken-language check of each episode's ctx50 window (the track the anchors come from)."""
import sys, subprocess, numpy as np
from pathlib import Path
from faster_whisper import WhisperModel
audio = Path(sys.argv[1])
m = WhisperModel('tiny', device='cpu', compute_type='int8')
for f in sorted(audio.glob('*.ctx50.flac')):
    pcm = subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-ss', '20', '-t', '60', '-i', str(f),
                          '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], check=True, capture_output=True).stdout
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
    _, info = m.transcribe(x)
    print(f.name.split('.')[0], info.language, round(info.language_probability, 3), flush=True)
