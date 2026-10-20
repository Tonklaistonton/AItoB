import base64
import re
from email.message import Message
from html.parser import HTMLParser

LABEL_NAME = "AItoB-Demo"
MAX_BODY_CHARS = 2000


class HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.hidden += 1
        if tag in ("br", "p", "div", "tr", "li"):
            self.text.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head") and self.hidden:
            self.hidden -= 1
        if tag in ("p", "div", "tr", "li"):
            self.text.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


def headers_of(part):
    return {
        item["name"].lower(): item["value"]
        for item in part.get("headers", [])
    }


def extract_text(payload):
    plain = []
    html = []

    def visit(part):
        headers = headers_of(part)
        disposition = headers.get("content-disposition", "").lower()
        if part.get("filename") or disposition.startswith("attachment"):
            return

        mime = part.get("mimeType", "").lower()
        if mime.startswith("multipart/"):
            for child in part.get("parts", []):
                visit(child)
            return

        encoded = part.get("body", {}).get("data")
        if mime not in ("text/plain", "text/html") or not encoded:
            return

        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        message = Message()
        message["Content-Type"] = headers.get("content-type", mime)
        charset = message.get_content_charset() or "utf-8"
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            text = raw.decode("utf-8", errors="replace")

        (plain if mime == "text/plain" else html).append(text)

    visit(payload)

    if plain:
        text = "\n".join(plain)
        kind = "plain"
    elif html:
        parser = HTMLText()
        parser.feed("\n".join(html))
        text = "\n".join(parser.text)
        kind = "html"
    else:
        return "", "empty"

    text = re.sub(r"[\u034f\u200b-\u200f\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip(), kind


def fetch_demo_emails(service):
    labels = service.users().labels().list(
        userId="me"
    ).execute().get("labels", [])

    label = next(
        (item for item in labels if item["name"] == LABEL_NAME),
        None
    )
    if label is None:
        raise RuntimeError("AItoB-Demo label not found.")

    references = service.users().messages().list(
        userId="me",
        labelIds=[label["id"]],
        maxResults=5,
        includeSpamTrash=False
    ).execute().get("messages", [])

    emails = []
    for reference in references:
        message_id = reference["id"]

        minimal = service.users().messages().get(
            userId="me", id=message_id, format="minimal"
        ).execute()
        if label["id"] not in minimal.get("labelIds", []):
            continue

        message = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()
        if label["id"] not in message.get("labelIds", []):
            continue

        payload = message.get("payload", {})
        headers = headers_of(payload)
        body, kind = extract_text(payload)

        emails.append({
            "id": message_id,
            "subject": headers.get("subject", "")[:300],
            "from": headers.get("from", "")[:300],
            "date": headers.get("date", "")[:100],
            "body": body[:MAX_BODY_CHARS],
            "body_kind": kind,
            "truncated": len(body) > MAX_BODY_CHARS
        })

    return emails
