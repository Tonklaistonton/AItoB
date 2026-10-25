import json
import secrets
from pathlib import Path

KEY_FILE = Path(__file__).resolve().parent / "credentials" / "keys.json"
KEYS = json.loads(KEY_FILE.read_text())


def authenticate(header):
    if not isinstance(header, str):
        return None
    scheme, separator, token = header.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token:
        return None

    supplied = token.encode("utf-8")
    for key, identity in KEYS.items():
        if secrets.compare_digest(supplied, key.encode("utf-8")):
            return dict(identity)

    return None
