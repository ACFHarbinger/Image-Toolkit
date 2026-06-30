"""Download WD-EVA02 large tagger v3 to models/wd14/."""
from huggingface_hub import hf_hub_download

REPO = "SmilingWolf/wd-eva02-large-tagger-v3"
OUT = "models/wd14"

for filename in ("model.onnx", "selected_tags.csv"):
    print(f"Downloading {filename}...")
    hf_hub_download(REPO, filename=filename, local_dir=OUT)
    print(f"  ✓ {filename}")

print(f"\nTagger ready at {OUT}/")
