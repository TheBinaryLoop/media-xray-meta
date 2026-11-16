"""Fetch credits for Deadpool and every Bones episode, plus each person's external ids, from TMDB.
Respects 2 requests/second. Writes WORK/tmdb/*.json; never prints the key."""
import json, sys, time, urllib.request, urllib.error
from pathlib import Path
work = Path(sys.argv[1]); out = work / 'tmdb'; out.mkdir(exist_ok=True)
key = (work / 'secrets' / 'tmdb').read_text().strip()
last = [0.0]
def get(path):
    for attempt in range(5):
        wait = 0.5 - (time.time() - last[0])
        if wait > 0: time.sleep(wait)
        last[0] = time.time()
        req = urllib.request.Request('https://api.themoviedb.org/3' + path, headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(5); continue
            if e.code == 404: return None
            raise
    raise RuntimeError('too many retries ' + path)
def cached(name, path):
    f = out / name
    if f.exists(): return json.loads(f.read_text())
    d = get(path); f.write_text(json.dumps(d)); return d

cached('movie-293660-credits.json', '/movie/293660/credits?language=en-US')
cached('movie-293660-credits-de.json', '/movie/293660/credits?language=de-DE')
seasons = {s: cached(f'tv-1911-s{s:02d}.json', f'/tv/1911/season/{s}?language=en-US') for s in range(1, 13)}
cached('tv-1911-aggregate.json', '/tv/1911/aggregate_credits?language=en-US')
people = set()
for s, season in seasons.items():
    for ep in season['episodes']:
        c = cached(f"tv-1911-s{s:02d}e{ep['episode_number']:02d}-credits.json",
                   f"/tv/1911/season/{s}/episode/{ep['episode_number']}/credits?language=en-US")
        for p in c.get('cast', []) + c.get('guest_stars', []): people.add(p['id'])
        cached(f"tv-1911-s{s:02d}e{ep['episode_number']:02d}-ids.json",
               f"/tv/1911/season/{s}/episode/{ep['episode_number']}/external_ids")
for p in cached('movie-293660-credits.json', '')['cast']: people.add(p['id'])
print(len(people), 'people')
for i, pid in enumerate(sorted(people)):
    cached(f'person-{pid}-ids.json', f'/person/{pid}/external_ids')
    if i % 200 == 0: print(i, flush=True)
print('done')
