"""Match candidate recordings against every Bones episode whose full audio is here.
Candidates: the theme and the soundtrack album for every episode, plus the episode's own songs from FOX's
lists (seasons 1-5). Usage: music_bones.py WORK"""
import json, subprocess, sys
from pathlib import Path
work = Path(sys.argv[1])
ost = [l for l in (work / 'bones' / 'music' / 'candidates.txt').read_text().split() if l]
fox = json.loads((work / 'bones' / 'fox' / 'songs.json').read_text())
# Songs proposed from transcribed lyrics (seasons 6-12): candidates like FOX's, verified the same way.
lyric_songs = work / 'bones' / 'lyrics-songs.json'
if lyric_songs.exists():
    for k, v in json.loads(lyric_songs.read_text()).items(): fox.setdefault(k, []).extend(x for x in v if x not in fox.get(k, []))
cands = json.loads((work / 'bones' / 'fox' / 'candidates.json').read_text())
rec_path = work / 'music' / 'recordings.json'
recordings = json.loads(rec_path.read_text())
for k, recs in cands.items():
    for r in recs:
        if r.get('fingerprints'): recordings.setdefault(r['mbid'], {'title': r['title'], 'artist': r['artist']})
rec_path.write_text(json.dumps(recordings, indent=1, ensure_ascii=False))
lists = work / 'music' / 'lists'; lists.mkdir(parents=True, exist_ok=True)
done = 0
for audio in sorted((work / 'fullaudio').glob('s*.opus')):
    key = audio.stem
    out = work / 'music' / f'{key}.json'
    mbids = list(ost)
    for song in fox.get(key, []):
        for r in cands.get(f"{song['title']}\t{song['artist']}", []):
            if r.get('fingerprints') and r['mbid'] not in mbids: mbids.append(r['mbid'])
    lf = lists / f'{key}.txt'
    if out.exists() and lf.exists() and lf.read_text().split() == mbids and key[:3] != 's04': continue
    lf.write_text('\n'.join(mbids) + '\n')
    # Most seasons of this release are PAL-sped, season 4 is not, and for 6-12 it is not known: match at
    # every candidate speed and keep all cues (a recording at the wrong speed does not match at all).
    season = int(key[1:3])
    rates = {4: ['1'], 1: ['0.959040959'], 2: ['0.959040959'], 3: ['0.959040959'], 5: ['0.959040959']}.get(
        season, ['0.959040959', '1'])
    merged = []
    for rate in rates:
        subprocess.run(['uv', 'run', '--quiet', '--python', '3.12', '--with', 'numpy', 'python',
                        str(Path(__file__).parent / 'music_match.py'), str(work), key, rate, str(lf)], check=True)
        cues = json.loads(out.read_text())
        for c in cues: c['rate'] = float(rate)
        merged += cues
    out.write_text(json.dumps(sorted(merged, key=lambda c: c['from']), indent=1))
    done += 1
print(done, 'episodes matched')
