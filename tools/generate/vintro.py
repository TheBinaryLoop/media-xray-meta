"""Frame-accurate intro boundaries: the run of frames an episode shares with the rest of its season."""
import numpy as np, statistics as st
from pathlib import Path

FPS = 25.0
W, H = 32, 18

def load(path):
    x = np.frombuffer(Path(path).read_bytes(), dtype=np.uint8)
    x = x[: len(x) // (W * H) * (W * H)].reshape(-1, W * H).astype(np.float32)
    mean = x.mean(axis=1); std = x.std(axis=1)
    z = (x - mean[:, None]) / (std[:, None] + 1e-6)
    z /= np.sqrt(W * H)
    return dict(z=z, mean=mean, std=std)

def sim(a, i, b, j):
    """Similarity of frame i of a and frame j of b in [-1, 1]; flat frames (black, fades) compare by level."""
    fa, fb = a['std'][i] < 4, b['std'][j] < 4
    if fa or fb:
        return 1.0 if fa and fb and abs(a['mean'][i] - b['mean'][j]) < 8 else 0.0
    return float(a['z'][i] @ b['z'][j])

def lag(a, b, c0, c1):
    """Frame lag L so that a[i] ~ b[i+L] over the core [c0, c1), searched over every lag."""
    za, zb = a['z'][c0:c1], b['z']
    best = (-2.0, None)
    for L in range(-c0, len(zb) - c1 + 1):
        s = float((za * zb[c0 + L:c1 + L]).sum(axis=1).mean())
        if s > best[0]: best = (s, L)
    return best

def shared_run(a, b, L, c0, c1, threshold=0.85, gap=3):
    n = len(a['z'])
    ok = np.array([0 <= i + L < len(b['z']) and sim(a, i, b, i + L) >= threshold for i in range(n)])
    centre = (c0 + c1) // 2
    if not ok[centre]: return None
    i = centre
    while i > 0:
        k = i - 1; misses = 0
        while k >= 0 and not ok[k] and misses < gap: k -= 1; misses += 1
        if k >= 0 and ok[k]: i = k
        else: break
    j = centre
    while j < n - 1:
        k = j + 1; misses = 0
        while k < n and not ok[k] and misses < gap: k += 1; misses += 1
        if k < n and ok[k]: j = k
        else: break
    return i, j + 1

def boundaries(thumbs, windows, is_starts, core=(5.0, 20.0), min_core_sim=0.8):
    """thumbs: {ep: loaded}, windows: {ep: window start s}, is_starts: {ep: Intro Skipper start s}.
    Returns {ep: (start, end, partners_agreeing, partners)}."""
    out = {}
    for e, a in thumbs.items():
        c0 = int((is_starts[e] - windows[e] + core[0]) * FPS); c1 = int((is_starts[e] - windows[e] + core[1]) * FPS)
        starts, ends = [], []
        partners = [f for f in thumbs if f != e]
        same = 0   # partners showing the same title sequence at all; a season can switch versions midway
        for f in partners:
            s, L = lag(a, thumbs[f], c0, c1)
            if L is None or s < min_core_sim: continue
            same += 1
            r = shared_run(a, thumbs[f], L, c0, c1)
            if r is None: continue
            j = r[1]
            # Black matches black, so the shared run stops where the shorter of the two black gaps ends.
            # Carry on through this episode's own black (thumbnails are full range, so black is 0): the intro
            # ends where its content starts to fade in.
            while j < len(a['z']) and a['std'][j] < 0.5 and a['mean'][j] < 0.5: j += 1
            starts.append(windows[e] + r[0] / FPS); ends.append(windows[e] + j / FPS)
        if starts:
            # A partner showing another version of the sequence shares only part of it, so the median can
            # belong to the wrong version. The boundary is the outermost value that two partners agree on.
            def supported(values, pick):
                ok = [v for v in values if sum(abs(v - w) <= 0.25 for w in values) >= 2]
                return pick(ok) if ok else st.median(values)
            out[e] = (supported(starts, min), supported(ends, max), len(starts), same,
                      max(starts) - min(starts), max(ends) - min(ends))
        else:
            out[e] = (None, None, 0, same, None, None)
    return out
