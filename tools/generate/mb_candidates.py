"""MusicBrainz recordings for each listed song, then their AcoustID reference fingerprints.
Usage: mb_candidates.py WORK SONGS_JSON OUT_JSON   (SONGS_JSON: {episode: [{title, artist}]})"""
import json, subprocess, sys, time, urllib.parse, urllib.request
from pathlib import Path
work, songs_file, out_file = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
UA = {'User-Agent': 'media-xray-meta/0.1 (https://github.com/TheBinaryLoop/media-xray-meta)'}
songs = json.loads(songs_file.read_text())
done = json.loads(out_file.read_text()) if out_file.exists() else {}
def esc(s): return s.replace('"', '\\"')
for ep, items in songs.items():
    for song in items:
        k = f"{song['title']}\t{song['artist']}"
        if k in done: continue
        q = f'recording:"{esc(song["title"])}" AND artist:"{esc(song["artist"])}"'
        url = 'https://musicbrainz.org/ws/2/recording/?' + urllib.parse.urlencode({'query': q, 'fmt': 'json', 'limit': 10})
        for attempt in range(4):
            time.sleep(1.1)
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r: d = json.load(r); break
            except Exception: time.sleep(5)
        else: d = {'recordings': []}
        recs = [{'mbid': r['id'], 'title': r['title'], 'artist': ''.join(a['name'] + a.get('joinphrase', '') for a in r.get('artist-credit', [])),
                 'score': r.get('score', 0), 'length': r.get('length')} for r in d.get('recordings', []) if r.get('score', 0) >= 90][:3]
        for r in recs:
            subprocess.run([sys.executable, '-I', str(Path(__file__).parent / 'acoustid_ref.py'), str(work), r['mbid'], '3'],
                           capture_output=True)
            ref = work / 'reffp' / f"{r['mbid']}.json"
            r['fingerprints'] = len(json.loads(ref.read_text())) if ref.exists() else 0
        done[k] = recs
        out_file.write_text(json.dumps(done, indent=1, ensure_ascii=False))
        print(ep, song['title'], '-', song['artist'], '->', [(r['title'], r['artist'], r['fingerprints']) for r in recs], flush=True)
