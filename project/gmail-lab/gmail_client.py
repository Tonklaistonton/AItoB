import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE = Path(__file__).resolve().parent
TOKEN_FILE = BASE / "credentials" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_service():
    credentials = Credentials.from_authorized_user_file(
        str(TOKEN_FILE), SCOPES
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

        os.umask(0o077)
        temporary = TOKEN_FILE.with_suffix(".tmp")
        temporary.write_text(credentials.to_json(), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(TOKEN_FILE)

    if not credentials.valid or not credentials.has_scopes(SCOPES):
        raise RuntimeError("Gmail authorization is not valid.")

    return build(
        "gmail", "v1",
        credentials=credentials,
        cache_discovery=False
    )
