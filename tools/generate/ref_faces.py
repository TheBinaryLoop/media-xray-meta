"""Reference face embeddings for an item's cast from TMDB profile photos (local only, never published).
Usage: ref_faces.py WORK KEY  -> WORK/faces/refs/<tmdb id>.npy  (one SFace embedding per usable photo)"""
import json, sys, time, urllib.request
from pathlib import Path
import cv2, numpy as np

work, key = Path(sys.argv[1]), sys.argv[2]
tmdb_key = (work / 'secrets' / 'tmdb').read_text().strip()
models = work / 'faces' / 'models'
detector = cv2.FaceDetectorYN.create(str(models / 'face_detection_yunet_2023mar.onnx'), '', (320, 320), 0.8, 0.3, 5000)
recognizer = cv2.FaceRecognizerSF.create(str(models / 'face_recognition_sface_2021dec.onnx'), '')
photos = work / 'faces' / 'photos'; photos.mkdir(parents=True, exist_ok=True)
refs = work / 'faces' / 'refs'; refs.mkdir(parents=True, exist_ok=True)
last = [0.0]

def get(url, headers=None):
    wait = 0.5 - (time.time() - last[0])
    if wait > 0: time.sleep(wait)
    last[0] = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=30) as r:
        return r.read()

def embed(image):
    h, w = image.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(image)
    if faces is None or len(faces) == 0: return None
    face = max(faces, key=lambda f: f[2] * f[3])        # a profile photo shows its subject largest
    if face[2] < 40: return None
    aligned = recognizer.alignCrop(image, face)
    return recognizer.feature(aligned).flatten()

people = json.loads((work / 'people' / f'{key}.json').read_text())['people']
for k, p in people.items():
    pid = p['tmdb']
    dest = refs / f'{pid}.npy'
    if dest.exists(): continue
    info = json.loads(get(f'https://api.themoviedb.org/3/person/{pid}/images',
                          {'Authorization': 'Bearer ' + tmdb_key, 'Accept': 'application/json'}))
    vectors = []
    for prof in info.get('profiles', [])[:8]:
        f = photos / f"{pid}-{prof['file_path'].strip('/')}"
        if not f.exists():
            f.write_bytes(get('https://image.tmdb.org/t/p/h632' + prof['file_path']))
        img = cv2.imread(str(f))
        if img is None: continue
        v = embed(img)
        if v is not None: vectors.append(v)
    np.save(dest, np.array(vectors, dtype=np.float32).reshape(-1, 128))
    print(k, pid, len(vectors), 'reference faces', flush=True)
