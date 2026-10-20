import re
from auth import authenticate
from email_access import OWNER_USER, EXPECTED_EMAIL
from email_reader import (
    LABEL_NAME, MAX_BODY_CHARS, extract_text, headers_of
)
from gmail_client import get_service
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError


def read_message_for_key(authorization, arguments):
    identity = authenticate(authorization)
    if identity is None:
        return 401, {"error": "invalid_or_missing_api_key"}
    if identity.get("user") != OWNER_USER:
        return 403, {"error": "mailbox_access_denied"}

    if (
        not isinstance(arguments, dict)
        or set(arguments) != {"message_id"}
    ):
        return 400, {"error": "invalid_read_arguments"}

    message_id = arguments["message_id"]
    if (
        not isinstance(message_id, str)
        or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", message_id) is None
    ):
        return 400, {"error": "invalid_message_id"}

    try:
        service = get_service()
        profile = service.users().getProfile(userId="me").execute()
        if (
            profile.get("emailAddress", "").casefold()
            != EXPECTED_EMAIL.casefold()
        ):
            return 403, {"error": "connected_mailbox_mismatch"}

        labels = service.users().labels().list(
            userId="me"
        ).execute().get("labels", [])
        label = next(
            (item for item in labels if item["name"] == LABEL_NAME),
            None
        )
        if label is None:
            return 404, {"error": "allowed_label_not_found"}

        minimal = service.users().messages().get(
            userId="me", id=message_id, format="minimal"
        ).execute()

        if label["id"] not in minimal.get("labelIds", []):
            return 403, {"error": "email_outside_allowed_label"}

        message = service.users().messages().get(
            userId="me", id=message_id, format="full"
        ).execute()

        if label["id"] not in message.get("labelIds", []):
            return 403, {"error": "email_outside_allowed_label"}

        payload = message.get("payload", {})
        headers = headers_of(payload)
        body, kind = extract_text(payload)
        if not body:
            return 422, {"error": "email_text_unavailable"}

        return 200, {
            "email": {
                "id": message_id,
                "subject": headers.get("subject", "")[:300],
                "from": headers.get("from", "")[:300],
                "date": headers.get("date", "")[:100],
                "body": body[:MAX_BODY_CHARS],
                "body_kind": kind,
                "truncated": len(body) > MAX_BODY_CHARS
            },
            "scope_label": LABEL_NAME
        }

    except HttpError as error:
        if error.resp.status == 404:
            return 404, {"error": "email_not_found"}
        return 502, {"error": "gmail_read_failed"}
    except (GoogleAuthError, OSError, ValueError, RuntimeError):
        return 502, {"error": "gmail_read_failed"}
