import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, "/gateway")

from auth import authenticate
from gmail_search import search_for_key
from gmail_read import read_message_for_key
from email_access import OWNER_USER, read_owned_emails
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError


def read_for_key(authorization):
    identity = authenticate(authorization)
    if identity is None:
        return 401, {"error": "invalid_or_missing_api_key"}

    if identity.get("user") != OWNER_USER:
        return 403, {"error": "mailbox_access_denied"}

    try:
        emails = read_owned_emails(identity)
    except PermissionError:
        return 403, {"error": "mailbox_access_denied_or_mismatch"}
    except (GoogleAuthError, HttpError, OSError, ValueError, RuntimeError):
        return 502, {"error": "gmail_access_failed"}

    return 200, {
        "identity": identity,
        "emails": emails,
        "count": len(emails)
    }


class GmailBackend(BaseHTTPRequestHandler):
    def reply(self, status, result):
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path in ("/search", "/read"):
            authorization = self.headers.get("Authorization", "")
            identity = authenticate(authorization)
            if identity is None:
                self.reply(401, {"error": "invalid_or_missing_api_key"})
                return
            if identity.get("user") != OWNER_USER:
                self.reply(403, {"error": "mailbox_access_denied"})
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError()
                arguments = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                self.reply(400, {"error": "invalid_request_body"})
                return

            handler = search_for_key if self.path == "/search" else read_message_for_key
            status, result = handler(authorization, arguments)
            self.reply(status, result)
            return

        if self.path != "/emails":
            self.reply(404, {"error": "not_found"})
            return

        status, result = read_for_key(
            self.headers.get("Authorization", "")
        )
        self.reply(status, result)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8001), GmailBackend)
    print("READY: Gmail backend on container port 8001", flush=True)
    server.serve_forever()
