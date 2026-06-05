import urllib.request
import os

base_url = "https://raw.githubusercontent.com/justadudewhohacks/face-api.js/master/weights/"
files = [
    "tiny_face_detector_model-weights_manifest.json",
    "tiny_face_detector_model-shard1"
]

out_dir = os.path.join(os.path.dirname(__file__), "frontend", "static", "models")
os.makedirs(out_dir, exist_ok=True)

for file in files:
    out_path = os.path.join(out_dir, file)
    print(f"Downloading {file}...")
    try:
        urllib.request.urlretrieve(base_url + file, out_path)
        print(f"Saved to {out_path}")
    except Exception as e:
        print(f"Failed to download {file}: {e}")
