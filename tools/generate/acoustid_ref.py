"""Reference fingerprints of a MusicBrainz recording, taken from acoustid.org (CC BY-SA; used locally only).
Usage: acoustid_ref.py WORK MBID [MAX]  -> WORK/reffp/MBID.json  [{track, fingerprint_id, length, fp:[...]}]"""
import json, re, sys, time, urllib.request
from pathlib import Path
work = Path(sys.argv[1]); mbid = sys.argv[2]; limit = int(sys.argv[3]) if len(sys.argv) > 3 else 6
out = work / 'reffp'; out.mkdir(exist_ok=True)
dest = out / f'{mbid}.json'
if dest.exists(): print(mbid, 'cached'); sys.exit()
UA = {'User-Agent': 'media-xray-meta/0.1 (https://github.com/TheBinaryLoop/media-xray-meta)'}
client = (work / 'secrets' / 'acoustid').read_text().strip()
def get(url, parse_json=False):
    time.sleep(1.0)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        data = r.read().decode('utf-8', 'replace')
    return json.loads(data) if parse_json else data
tracks = [t['id'] for t in get(f'https://api.acoustid.org/v2/track/list_by_mbid?client={client}&mbid={mbid}', True).get('tracks', [])]
refs = []
for track in tracks:
    for fid in sorted(set(re.findall(r'/fingerprint/(\d+)', get(f'https://acoustid.org/track/{track}'))))[:3]:
        page = get(f'https://acoustid.org/fingerprint/{fid}')
        m = re.search(r'data-fp="(\[[^"]+\])"', page)
        length = re.search(r'File length\s*</[^>]+>\s*<[^>]+>\s*([0-9:]+)', page)
        if m:
            refs.append({'track': track, 'fingerprint_id': fid, 'length': length.group(1) if length else None,
                         'fp': json.loads(m.group(1))})
        if len(refs) >= limit: break
    if len(refs) >= limit: break
dest.write_text(json.dumps(refs))
print(mbid, len(tracks), 'tracks,', len(refs), 'fingerprints')
