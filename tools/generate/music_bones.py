"""Match candidate recordings against every Bones episode whose full audio is here.
Candidates: the theme and the soundtrack album for every episode, plus the episode's own songs from FOX's
lists (seasons 1-5). Usage: music_bones.py WORK"""
import json, subprocess, sys
from pathlib import Path
work = Path(sys.argv[1])
ost = [l for l in (work / 'bones' / 'music' / 'candidates.txt').read_text().split() if l]
fox = json.loads((work / 'bones' / 'fox' / 'songs.json').read_text())
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
    if out.exists() and lf.exists() and lf.read_text().split() == mbids: continue
    lf.write_text('\n'.join(mbids) + '\n')
    subprocess.run(['uv', 'run', '--quiet', '--python', '3.12', '--with', 'numpy', 'python',
                    str(Path(__file__).parent / 'music_match.py'), str(work), key, '0.959040959', str(lf)], check=True)
    done += 1
print(done, 'episodes matched')
