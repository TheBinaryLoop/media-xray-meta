"""Recognise the credited cast in an item's frames (1 per second) and turn the hits into appearances.
Usage: faces.py WORK KEY [THRESHOLD MARGIN]  -> WORK/faces/results/KEY.json

Each detected face is compared with the reference embeddings of the item's own cast only (cosine
similarity, best photo per person). A face is labelled when the best person clears THRESHOLD and beats the
runner-up by MARGIN. Faces are then clustered within the item, and a cluster whose confident labels agree
lends that label to its unlabelled members (profile shots, partial occlusion). Appearances are runs of a
person's labelled frames with gaps of at most GAP seconds."""
import json, sys
from pathlib import Path
import cv2, numpy as np

work, key = Path(sys.argv[1]), sys.argv[2]
THRESHOLD = float(sys.argv[3]) if len(sys.argv) > 3 else 0.45
MARGIN = float(sys.argv[4]) if len(sys.argv) > 4 else 0.08
GAP, MIN_FRAMES = 4, 2
models = work / 'faces' / 'models'
detector = cv2.FaceDetectorYN.create(str(models / 'face_detection_yunet_2023mar.onnx'), '', (320, 320), 0.85, 0.3, 5000)
recognizer = cv2.FaceRecognizerSF.create(str(models / 'face_recognition_sface_2021dec.onnx'), '')

people = json.loads((work / 'people' / f'{key}.json').read_text())['people']
names, refs = [], []
for k, p in people.items():
    f = work / 'faces' / 'refs' / f"{p['tmdb']}.npy"
    if not f.exists(): continue
    v = np.load(f)
    if len(v):
        names.append(k); refs.append(v / np.linalg.norm(v, axis=1, keepdims=True))

MODE = 'keyframes' if (work / 'faces' / 'keyframes' / key / 'times.txt').exists() else 'frames'

def frame_list():
    """(image, time) pairs: keyframes with their logged times, or 1-per-second frames."""
    if MODE == 'keyframes':
        d = work / 'faces' / 'keyframes' / key
        for line in (d / 'times.txt').read_text().split('\n'):
            if line.strip():
                n, t = line.split()
                yield d / f'{int(n) + 1:05d}.jpg', float(t)
    else:
        for f in sorted((work / 'faces' / 'frames' / key).glob('*.jpg')):
            yield f, int(f.stem) - 0.5              # frame N of fps=1 is centred on second N - 0.5

cache = work / 'faces' / 'embeddings' / f'{key}.{MODE}.npz'
cache.parent.mkdir(parents=True, exist_ok=True)
if cache.exists():
    z = np.load(cache); times, boxes, feats = z['times'], z['boxes'], z['feats']
else:
    times, boxes, feats = [], [], []
    for f, t in frame_list():
        img = cv2.imread(str(f)); h, w = img.shape[:2]
        detector.setInputSize((w, h))
        _, faces = detector.detect(img)
        for face in faces if faces is not None else []:
            if face[2] < 36 or face[3] < 36: continue  # too small to recognise reliably
            v = recognizer.feature(recognizer.alignCrop(img, face)).flatten()
            times.append(t); boxes.append(face[:4]); feats.append(v / np.linalg.norm(v))
    times, boxes, feats = np.array(times), np.array(boxes).reshape(-1, 4), np.array(feats).reshape(-1, 128)
    np.savez(cache, times=times, boxes=boxes, feats=feats)

# Similarity of every face to every cast member: the best of that member's photos.
sims = np.stack([(feats @ r.T).max(axis=1) for r in refs], axis=1) if len(feats) and refs else np.zeros((len(feats), 0))
order = np.argsort(-sims, axis=1)
best = sims[np.arange(len(sims)), order[:, 0]]
second = sims[np.arange(len(sims)), order[:, 1]] if sims.shape[1] > 1 else np.zeros(len(sims))
label = np.where((best >= THRESHOLD) & (best - second >= MARGIN), order[:, 0], -1)
direct = label.copy()

# Cluster faces of this item (greedy, cosine >= 0.55 to the cluster centre) and spread confident labels.
clusters, centres = [], []
for i in np.argsort(times):
    if centres:
        c = np.array(centres) @ feats[i]
        j = int(np.argmax(c))
        if c[j] >= 0.55:
            clusters[j].append(i); centres[j] = centres[j] + (feats[i] - centres[j]) / len(clusters[j]); continue
    clusters.append([i]); centres.append(feats[i].copy())
spread = 0
for members in clusters:
    votes = [direct[i] for i in members if direct[i] >= 0]
    if len(votes) < 3: continue
    top = max(set(votes), key=votes.count)
    if votes.count(top) / len(votes) < 0.8: continue    # a mixed cluster lends nothing
    for i in members:
        if label[i] < 0 and sims[i, top] >= THRESHOLD - 0.12:
            label[i] = top; spread += 1

appearances = []
if MODE == 'keyframes':
    # A keyframe starts a shot; a face found there stands for the shot, up to the next keyframe (8 s at most).
    kf = sorted(set(t for _, t in frame_list()))
    nxt = {a: min(b, a + 8.0) for a, b in zip(kf, kf[1:] + [kf[-1] + 4.0])}
    for p in range(len(names)):
        spans = sorted((t, nxt[t]) for t in set(times[label == p].tolist()))
        merged = []
        for a, b in spans:
            if merged and a - merged[-1][1] <= 1.0: merged[-1][1] = max(merged[-1][1], b); merged[-1][2] += 1
            else: merged.append([a, b, 1])
        for a, b, n in merged:
            if b - a < 1.0: continue
            conf = float(np.mean(sims[(label == p) & (times >= a) & (times < b), p]))
            appearances.append({'who': names[p], 'from': a, 'to': b, 'frames': n, 'similarity': round(conf, 3)})
else:
  for p in range(len(names)):
    ts = sorted(set(times[label == p].tolist()))
    run = []
    for t in ts + [None]:
        if run and (t is None or t - run[-1] > GAP):
            if len(run) >= MIN_FRAMES:
                conf = float(np.mean(sims[(label == p) & (times >= run[0]) & (times <= run[-1]), p]))
                appearances.append({'who': names[p], 'from': max(0.0, run[0] - 0.5), 'to': run[-1] + 0.5,
                                    'frames': len(run), 'similarity': round(conf, 3)})
            run = []
        if t is not None: run.append(t)
out = work / 'faces' / 'results'; out.mkdir(exist_ok=True)
(out / f'{key}.{MODE}.json').write_text(json.dumps({'appearances': sorted(appearances, key=lambda a: a['from']),
                                             'faces': len(feats), 'labelled_direct': int((direct >= 0).sum()),
                                             'labelled_spread': spread, 'threshold': THRESHOLD, 'margin': MARGIN,
                                             'per_frame': [[float(t), names[l] if l >= 0 else None, round(float(b), 3)]
                                                           for t, l, b in zip(times, label, best)]}, indent=0))
print(key, len(feats), 'faces,', int((direct >= 0).sum()), 'recognised,', spread, 'by cluster,', len(appearances), 'appearances')
