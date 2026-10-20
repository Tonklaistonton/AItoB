import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

os.umask(0o077)

BASE = Path(__file__).resolve().parent
CLIENT_FILE = BASE / "credentials" / "client_secret.json"
TOKEN_FILE = BASE / "credentials" / "token.json"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

if TOKEN_FILE.exists():
    raise SystemExit("token.json already exists; stopped without changes.")

flow = InstalledAppFlow.from_client_secrets_file(
    str(CLIENT_FILE),
    SCOPES,
    autogenerate_code_verifier=True
)

credentials = flow.run_local_server(
    host="127.0.0.1",
    bind_addr="0.0.0.0",
    port=8765,
    open_browser=False,
    timeout_seconds=300,
    prompt="consent",
    success_message="AItoB authorization received. You may close this tab."
)

if not credentials.has_scopes(SCOPES):
    raise RuntimeError("Gmail read permission was not granted.")

if not credentials.refresh_token:
    raise RuntimeError("No refresh token received; token was not saved.")

with TOKEN_FILE.open("x", encoding="utf-8") as file:
    file.write(credentials.to_json())

print("PASS: Gmail OAuth token saved on Mac.")
print("PASS: Read permission and refresh token are available.")
print("No email messages have been fetched.")
