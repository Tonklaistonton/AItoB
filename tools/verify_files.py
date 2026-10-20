import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/"SHA256SUMS.json").read_text(encoding="utf-8"))
for name,wanted in manifest.items():
 path=(root/name).resolve()
 if root not in path.parents:raise SystemExit("Unsafe manifest path")
 if hashlib.sha256(path.read_bytes()).hexdigest()!=wanted:raise SystemExit("FAIL "+name)
print("PASS",len(manifest),"files verified")
