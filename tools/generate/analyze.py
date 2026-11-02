"""Derive intro/outro/recap segments and anchors for one season, verified independently of Intro Skipper.

Usage: analyze.py WORK SEASON  -> WORK/results/sNN.json
"""
import csv, json, re, statistics as st, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import fp, spectrum as w

work = Path(sys.argv[1]); season = int(sys.argv[2])
T = 1e7
PAL = 24000 / 1001 / 25        # a 23.976 fps copy plays at this speed relative to the 25 fps reference

def luma(name, start):
    path = work / 'luma' / f'{name}.luma'
    if start is None or not path.exists(): return None
    t, y = [], []
    for line in open(path):
        m = re.search(r'pts_time:([\d.]+)', line)
        if m: t.append(start + float(m.group(1)))
        m = re.search(r'YAVG=([\d.]+)', line)
        if m: y.append(float(m.group(1)))
    return np.array(t[:len(y)]), np.array(y[:len(t)])

def runs(mask, gap=0):
    """(i, j) index runs where mask is true, bridging up to `gap` false samples."""
    out, i, n = [], 0, len(mask)
    while i < n:
        if not mask[i]: i += 1; continue
        j = i
        while True:
            k = j + 1
            while k < n and not mask[k] and k - j <= gap: k += 1
            if k < n and mask[k] and k - j <= gap + 1: j = k
            else: break
        out.append((i, j + 1)); i = j + 1
    return out

windows = {k: float(a) for k, p, a, dur in csv.reader(open(work / 'plan-luma.tsv'), delimiter='\t')}

episodes = {}
for s, e, path, ticks, imdb, tvdb, segs in csv.reader(open(work / 'items.tsv'), delimiter='\t'):
    if int(s) != season: continue
    seg = {}
    for x in segs.split(','):
        if x:
            typ, src, state, a, b = x.split(':')
            seg[typ] = (int(a) / T, int(b) / T)
    episodes[int(e)] = dict(key=f's{season:02d}e{int(e):02d}', path=path, runtime=int(ticks) / T,
                            imdb=imdb or None, tvdb=int(tvdb) if tvdb else None, seg=seg, notes=[])

# ---------------------------------------------------------------- intro: audio shared across the season
intro = {}
for e, d in episodes.items():
    if '0' in d['seg']:
        a, b = d['seg']['0']
        wstart = max(0.0, a - 30)
        path = str(work / 'audio' / f"{d['key']}.intro.flac")
        x = w.pcm(path)
        intro[e] = dict(a=a, b=b, w=wstart, fp=fp.raw(path), spec=w.spec(x))

for e, d in intro.items():
    starts, ends, confirmed = [], [], 0
    core0 = int((d['a'] - d['w'] + 2) / fp.HOP); core1 = int((d['b'] - d['w'] - 2) / fp.HOP)
    partners = [f for f in intro if f != e]
    for f in partners:
        g = intro[f]
        best = fp.align(d['fp'][core0:core1], g['fp'], min_overlap=core1 - core0)
        if not best or best[0][0] > 0.25: continue
        confirmed += 1
        # Fingerprint offset -> spectrogram frame lag, refined to 50 ms.
        guess = round((best[0][1] - core0) * fp.HOP / w.HOPS)
        c0 = int((d['a'] - d['w'] + 3) / w.HOPS); c1 = int((d['b'] - d['w'] - 3) / w.HOPS)
        A, B = d['spec'], g['spec']
        bestL = max(((float((A[c0:c1] * B[c0 + L:c1 + L]).sum(axis=1).mean()), L)
                     for L in range(guess - 6, guess + 7) if c0 + L >= 0 and c1 + L <= len(B)), default=None)
        if bestL is None: continue
        sim = w.similarity(A, B, bestL[1])
        r = [ij for ij in runs(sim > 0.6, gap=6) if ij[0] <= (c0 + c1) // 2 < ij[1]]
        if not r: continue
        starts.append(d['w'] + r[0][0] * w.HOPS); ends.append(d['w'] + r[0][1] * w.HOPS)
    d['confirmed'] = confirmed; d['partners'] = len(partners)
    if starts:
        d['audio_start'], d['audio_end'] = st.median(starts), st.median(ends)
        d['spread'] = (st.pstdev(starts) if len(starts) > 1 else 0.0)

import vintro
twin = {k.split('.')[0]: float(x) for k, p_, x, dur in csv.reader(open(work / 'plan-thumbs.tsv'), delimiter='\t')}
thumbs = {e: vintro.load(work / 'thumbs' / f"{episodes[e]['key']}.intro.gray") for e in intro
          if (work / 'thumbs' / f"{episodes[e]['key']}.intro.gray").exists()}
video = vintro.boundaries(thumbs, {e: twin[episodes[e]['key']] for e in thumbs}, {e: intro[e]['a'] for e in thumbs})

for e, d in intro.items():
    ep = episodes[e]
    if d.get('confirmed', 0) < 3 or 'audio_start' not in d:
        ep['notes'].append(f"intro: audio not confirmed ({d.get('confirmed', 0)}/{d['partners']})"); continue
    if e not in video or video[e][0] is None:
        ep['notes'].append('intro: no picture match'); continue
    vs, ve, agree, partners, sspread, espread = video[e]
    # partners counts only episodes showing the same title sequence; at least three must agree.
    if agree < 3 or agree < 0.8 * partners:
        ep['notes'].append(f'intro: picture boundaries agreed by only {agree}/{partners}'); continue
    if abs(vs - d['audio_start']) > 4 or abs(vs - d['a']) > 4 or ve - vs < 15:
        ep['notes'].append(f"intro: picture {vs:.2f}-{ve:.2f} disagrees with audio {d['audio_start']:.2f} / IS {d['a']:.2f}"); continue
    ep['intro'] = dict(start=round(vs, 3), end=round(ve, 3), confidence=round(agree / partners, 2),
                       audio=(round(d['audio_start'], 2), round(d['audio_end'], 2)), IS=(round(d['a'], 2), round(d['b'], 2)),
                       spread=(round(sspread, 2), round(espread, 2)))

def card_frames(key):
    path = work / 'cards' / f'{key}.cards.cards'
    start = card_windows.get(key)
    if start is None or not path.exists(): return None
    t, high = [], []
    for line in open(path):
        m = re.search(r'pts_time:([\d.]+)', line)
        if m: t.append(start + float(m.group(1)))
        m = re.search(r'YHIGH=([\d.]+)', line)
        if m: high.append(float(m.group(1)))
    n = min(len(t), len(high))
    return np.array(t[:n]), np.array(high[:n])

card_windows = {}
for name in ('plan-cards-a.tsv', 'plan-cards-b.tsv'):
    if (work / name).exists():
        for k, p_, x, dur in csv.reader(open(work / name), delimiter='\t'):
            card_windows[k.split('.')[0]] = float(x)

# ---------------------------------------------------------------- outro: credits on black through to the end
for e, ep in episodes.items():
    rt = ep['runtime']
    cs = ep['seg'].get('1', (None,))[0]
    start = windows.get(f"{ep['key']}.ending")
    lu = luma(f"{ep['key']}.ending", start)
    if lu is None:
        ep['notes'].append('no luma for ending'); continue
    t, y = lu
    dark = runs(y <= 26.0, gap=3)
    # The credits: the last dark run of at least 15 s that is followed only by logos and black, i.e. it
    # ends within 25 s of the end of the file.
    long_runs = [(i, j) for i, j in dark if t[min(j, len(t) - 1)] - t[i] >= 15]
    if not long_runs:
        ep['notes'].append('outro: no credits-on-black run found'); continue
    i, j = long_runs[-1]
    run_end = t[j] if j < len(t) else rt
    if rt - run_end > 25:
        ep['notes'].append(f'outro: dark run ends {rt - run_end:.1f}s before the end'); continue
    # The run starts as soon as the last shot is dim, and a night scene can stay dim for a while; the
    # credits start at the first truly black frame, which in this show separates the last shot from the
    # first card.
    black = [k for k in range(i, j) if y[k] <= 18.5]
    if black: i = black[0]
    # Refine with the card measurement where it exists: a credits card is at least 90% pure black, so
    # its 90th-percentile luma stays at black, where a dim final scene's faces and lamps lift it. The
    # credits are the first unbroken stretch of card frames lasting 15 s.
    cards = card_frames(ep['key'])
    if cards is not None:
        ct, chigh = cards
        # Black is not always exactly 16 after encoding, so the limit follows this episode's own black.
        limit = float(chigh.min()) + 3
        card_runs = [(a, b) for a, b in runs(chigh <= limit, gap=2) if ct[min(b, len(ct) - 1)] - ct[a] >= 15]
        if not card_runs:
            ep['notes'].append('outro: no 15 s stretch of credit cards'); continue
        start_card = float(ct[card_runs[0][0]])
        ep['outro'] = dict(start=round(start_card, 3), end=round(rt, 3), IS=round(cs, 2) if cs else None,
                           confidence=round(float((chigh[card_runs[0][0]:card_runs[0][1]] <= limit).mean()), 2),
                           luma_start=round(float(t[i]), 3))
        continue
    ep['outro'] = dict(start=round(float(t[i]), 3), end=round(rt, 3), IS=round(cs, 2) if cs else None,
                       confidence=round(float((y[i:j] <= 26.0).mean()), 2))

# ---------------------------------------------------------------- anchors
def anchor_in(ep, centre):
    key = ep['key']; ctx = str(work / 'audio' / f'{key}.ctx{centre}.flac')
    cstart = ep['runtime'] * centre / 100 - 50
    hay = fp.raw(ctx)
    hay_pal = fp.raw(ctx, rate=PAL)
    busy = [(ep[k]['start'], ep[k]['end']) for k in ('intro', 'outro') if k in ep]
    for off in (40, 30, 50, 20, 60, 10, 70):
        a = cstart + off
        if any(a < y and a + 20 > x for x, y in busy): continue
        comp = fp.compressed(ctx, off, 20)
        needle, _ = fp.decode(comp)
        if len(set(needle.tolist())) < 0.5 * len(needle): continue        # near-silence or a held tone
        res = fp.align(needle, hay, min_overlap=len(needle))
        best = res[0]
        second = next((r for r in res if abs(r[1] - best[1]) > 16), None)
        if abs(best[1] * fp.HOP - off) > 0.25 or best[0] > 0.10: continue
        if second is not None and second[0] < 0.30: continue             # repeats within its own context
        # A consumer with a 23.976 fps copy: matching its audio as-is fails, resampling it by 1/PAL first
        # restores the reference timeline. Simulated by slowing the context, then restoring it.
        res_pal = fp.align(needle, hay_pal, min_overlap=len(needle))
        res_fix = fp.align(needle, restored(ctx), min_overlap=len(needle))
        return dict(start=round(a, 3), end=round(a + 20, 3), fingerprint=comp, ber=round(best[0], 3),
                    second=round(second[0], 3) if second else None,
                    ber_pal_unfixed=round(res_pal[0][0], 3), ber_pal_fixed=round(res_fix[0][0], 3),
                    pal_offset_error=round(res_fix[0][1] * fp.HOP - off, 2))
    return None

def restored(ctx):
    """A 23.976 fps copy of the context (slowed, pitch down), sped back up by the consumer."""
    import subprocess, tempfile, os
    with tempfile.TemporaryDirectory() as d:
        slow = os.path.join(d, 'slow.wav')
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-i', ctx, '-af',
                        f'asetrate=11025*{PAL},aresample=11025', '-ac', '1', '-ar', '11025', slow], check=True)
        return fp.raw(slow, rate=1 / PAL)

# The track the windows were cut from: English, except where a file has no English audio.
languages = json.load(open(work / 'anchor-language.json')) if (work / 'anchor-language.json').exists() else {}
for e, ep in episodes.items():
    ep['anchors'] = []
    for c in (20, 50, 80):
        a = anchor_in(ep, c)
        if a:
            a['language'] = languages.get(ep['key'], 'en')
            ep['anchors'].append(a)
        else: ep['notes'].append(f'no usable anchor near {c}%')

out = work / 'results'; out.mkdir(exist_ok=True)
for ep in episodes.values():
    ep.pop('seg', None)
json.dump({f's{season:02d}e{e:02d}': ep for e, ep in sorted(episodes.items())}, open(out / f's{season:02d}.json', 'w'), indent=1)
print('wrote', out / f's{season:02d}.json')
