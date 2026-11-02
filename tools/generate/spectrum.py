"""Sample-level boundaries of audio shared between episodes."""
import subprocess, numpy as np

RATE = 11025
FRAME = int(0.05 * RATE)   # 50 ms

def pcm(path):
    out = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(RATE), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(out, dtype=np.float32)

def lag(a, b, a0, a1, guess, search):
    """Sample lag L maximising the correlation of a[a0:a1] with b[a0+L : a1+L], within guess±search."""
    seg = a[a0:a1]
    lo = max(0, a0 + guess - search); hi = min(len(b), a1 + guess + search)
    win = b[lo:hi]
    if len(win) < len(seg): return None, 0.0
    n = 1 << int(np.ceil(np.log2(len(win) + len(seg))))
    corr = np.fft.irfft(np.fft.rfft(win, n) * np.conj(np.fft.rfft(seg, n)), n)[: len(win) - len(seg) + 1]
    # Normalise by the energy of each window of b so loud passages do not win by volume.
    csum = np.concatenate([[0], np.cumsum(win.astype(np.float64) ** 2)])
    energy = np.sqrt(csum[len(seg):] - csum[:-len(seg)]) * np.sqrt((seg.astype(np.float64) ** 2).sum()) + 1e-9
    norm = corr / energy
    k = int(np.argmax(norm))
    return lo + k - a0, float(norm[k])

def shared(a, b, L, threshold=0.8):
    """Per-50ms-frame normalised correlation of a[t] with b[t+L]; returns the frame mask over a."""
    frames = len(a) // FRAME
    mask = np.zeros(frames, dtype=bool)
    for f in range(frames):
        s = f * FRAME; t = s + L
        if t < 0 or t + FRAME > len(b): continue
        x = a[s:s + FRAME].astype(np.float64); y = b[t:t + FRAME].astype(np.float64)
        d = np.sqrt((x * x).sum() * (y * y).sum())
        mask[f] = d > 1e-6 and (x * y).sum() / d >= threshold
    return mask

def run_around(mask, centre, gap=4):
    """The run of True frames containing centre, bridging gaps of up to `gap` frames (quiet beats)."""
    if not mask[centre]: return None
    i = centre
    while True:
        j = i - 1
        while j >= 0 and not mask[j] and i - j <= gap: j -= 1
        if j >= 0 and mask[j] and i - j <= gap + 1: i = j
        else: break
    k = centre
    while True:
        j = k + 1
        while j < len(mask) and not mask[j] and j - k <= gap: j += 1
        if j < len(mask) and mask[j] and j - k <= gap + 1: k = j
        else: break
    return i, k + 1

HOPS = 0.05

def spec(x, n_fft=1024):
    """Log-magnitude spectrogram, one row per 50 ms, unit-normalised rows over 100 Hz-4 kHz."""
    hop = int(HOPS * RATE)
    frames = (len(x) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(frames)[:, None]
    m = np.abs(np.fft.rfft(x[idx] * np.hanning(n_fft), axis=1))
    freqs = np.fft.rfftfreq(n_fft, 1 / RATE)
    m = np.log1p(m[:, (freqs >= 100) & (freqs <= 4000)] * 100)
    m -= m.mean(axis=1, keepdims=True)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-9
    return m

def frame_lag(A, B, a0, a1, search):
    """Frame lag L maximising mean similarity of A[a0:a1] with B[a0+L:a1+L], |L| <= search around 0."""
    best = (-2.0, 0)
    for L in range(-search, search + 1):
        if a0 + L < 0 or a1 + L > len(B): continue
        s = float((A[a0:a1] * B[a0 + L:a1 + L]).sum(axis=1).mean())
        best = max(best, (s, L))
    return best[1], best[0]

def similarity(A, B, L):
    out = np.full(len(A), -1.0)
    for i in range(len(A)):
        j = i + L
        if 0 <= j < len(B): out[i] = float(A[i] @ B[j])
    return out
