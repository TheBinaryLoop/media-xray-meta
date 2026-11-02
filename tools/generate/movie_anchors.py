"""Anchors for a film: English windows pick the moments, the dub is fingerprinted at the same moments.
Usage: movie_anchors.py DIR RUNTIME PERCENTS  (DIR has en/ and de/ with <name>.ctxNN.flac, 100 s each)"""
import json, os, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); import fp

d = Path(sys.argv[1]); runtime = float(sys.argv[2]); percents = [int(p) for p in sys.argv[3].split(',')]
SPEEDUP = 25 / (24000 / 1001)       # a 25 fps European copy of a 24000/1001 film plays this much faster

def other_speed(ctx):
    """The context as a 25 fps copy would sound, then slowed back by the consumer."""
    with tempfile.TemporaryDirectory() as t:
        fast = os.path.join(t, 'fast.wav')
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', ctx, '-af',
                        f'asetrate=11025*{SPEEDUP},aresample=11025', '-ac', '1', '-ar', '11025', fast], check=True)
        return fp.raw(fast, rate=1 / SPEEDUP), fp.raw(fast)

def verify(ctx, off):
    comp = fp.compressed(ctx, off, 20)
    needle, _ = fp.decode(comp)
    if len(set(needle.tolist())) < 0.5 * len(needle): return None, 'near-silence'
    res = fp.align(needle, fp.raw(ctx), min_overlap=len(needle))
    best = res[0]; second = next((r for r in res if abs(r[1] - best[1]) > 16), None)
    if abs(best[1] * fp.HOP - off) > 0.25 or best[0] > 0.10: return None, f'self-match {best[0]:.3f}'
    if second is not None and second[0] < 0.30: return None, f'repeats {second[0]:.2f}'
    restored, raw_fast = other_speed(ctx)
    fixed = fp.align(needle, restored, min_overlap=len(needle))[0]
    unfixed = fp.align(needle, raw_fast, min_overlap=len(needle))[0]
    return dict(fingerprint=comp, ber=round(best[0], 3), second=round(second[0], 3) if second else None,
                other_speed_unfixed=round(unfixed[0], 3), other_speed_fixed=round(fixed[0], 3),
                other_speed_offset_error=round(fixed[1] * fp.HOP - off, 2)), None

out = {'en': [], 'de': []}
for p in percents:
    cstart = runtime * p / 100 - 50
    for off in (40, 30, 50, 20, 60, 10, 70):
        en, why = verify(str(d / 'en' / f'dp.ctx{p}.flac'), off)
        if not en: print(p, off, 'en', why); continue
        de, why_de = verify(str(d / 'de' / f'dp.ctx{p}.flac'), off)
        if not de: print(p, off, 'de', why_de); continue
        for lang, a in (('en', en), ('de', de)):
            out[lang].append(dict(start=round(cstart + off, 3), end=round(cstart + off + 20, 3), **a))
        break
    else:
        print(p, 'no moment works in both languages')
json.dump(out, open(d / 'anchors.json', 'w'), indent=1)
for lang, items in out.items():
    for a in items: print(lang, a['start'], a['ber'], a['second'], 'other speed: unfixed', a['other_speed_unfixed'], 'fixed', a['other_speed_fixed'], 'offset error', a['other_speed_offset_error'])
