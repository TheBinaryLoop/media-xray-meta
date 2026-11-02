"""Chromaprint helpers: raw fingerprints, decoding, and alignment."""
import ctypes, json, subprocess, tempfile, os
import numpy as np

HOP = 1365 / 11025          # seconds between fingerprint items (algorithm 2)
_lib = ctypes.CDLL("libchromaprint.so.1")

def raw(path, start=None, length=None, rate=None):
    """Raw fingerprint of a file, or of [start, start+length) of it. rate resamples speed (e.g. PAL)."""
    with tempfile.TemporaryDirectory() as d:
        src = path
        if start is not None or length is not None or rate is not None:
            src = os.path.join(d, "cut.wav")
            cmd = ["ffmpeg", "-nostdin", "-loglevel", "error"]
            if start is not None: cmd += ["-ss", f"{start:.3f}"]
            if length is not None: cmd += ["-t", f"{length:.3f}"]
            cmd += ["-i", path]
            if rate is not None:
                # Play faster/slower like a speed-changed release: pitch and tempo move together.
                cmd += ["-af", f"asetrate=11025*{rate},aresample=11025"]
            cmd += ["-ac", "1", "-ar", "11025", src]
            subprocess.run(cmd, check=True)
        out = subprocess.run(["fpcalc", "-raw", "-json", "-length", "0", src], check=True, capture_output=True, text=True).stdout
        return np.array(json.loads(out)["fingerprint"], dtype=np.int64).astype(np.uint32)

def compressed(path, start, length):
    with tempfile.TemporaryDirectory() as d:
        clip = os.path.join(d, "clip.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{length:.3f}",
                        "-i", path, "-ac", "1", "-ar", "11025", clip], check=True)
        out = subprocess.run(["fpcalc", "-json", "-length", "0", clip], check=True, capture_output=True, text=True).stdout
        return json.loads(out)["fingerprint"]

def decode(encoded):
    fp = ctypes.POINTER(ctypes.c_uint32)(); size = ctypes.c_int(); algo = ctypes.c_int()
    data = encoded.encode()
    if not _lib.chromaprint_decode_fingerprint(data, len(data), ctypes.byref(fp), ctypes.byref(size), ctypes.byref(algo), 1):
        raise ValueError("cannot decode fingerprint")
    result = np.array(fp[: size.value], dtype=np.uint32)
    _lib.chromaprint_dealloc(fp)
    return result, algo.value

def bits(a, b):
    return np.bitwise_count(np.bitwise_xor(a, b)).astype(np.int32)

def align(needle, hay, min_overlap=40):
    """Every offset of needle within hay (hay index of needle[0]) with its bit error rate, best first."""
    results = []
    for off in range(-(len(needle) - min_overlap), len(hay) - min_overlap + 1):
        a0, b0 = max(0, -off), max(0, off)
        n = min(len(needle) - a0, len(hay) - b0)
        if n < min_overlap: continue
        results.append((bits(needle[a0:a0 + n], hay[b0:b0 + n]).mean() / 32, off, n))
    results.sort()
    return results

def matched_run(a, b, off, threshold=10, smooth=9):
    """Longest run of items where a[i] matches b[i+off]; returns (start, end) indices into a, end exclusive."""
    a0, b0 = max(0, -off), max(0, off)
    n = min(len(a) - a0, len(b) - b0)
    err = bits(a[a0:a0 + n], b[b0:b0 + n])
    k = np.ones(smooth) / smooth
    good = np.convolve(err, k, mode="same") <= threshold
    best, cur, start = (0, 0), 0, 0
    for i, g in enumerate(good):
        if g:
            if cur == 0: start = i
            cur += 1
            if cur > best[1] - best[0]: best = (start, i + 1)
        else: cur = 0
    return best[0] + a0, best[1] + a0
