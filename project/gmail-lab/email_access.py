from gmail_client import get_service
from email_reader import fetch_demo_emails

OWNER_USER = "ton"
EXPECTED_EMAIL = "mailbox-owner-1@example.com"


def read_owned_emails(identity):
    # identity must come from server-side key authentication.
    if not isinstance(identity, dict) or identity.get("user") != OWNER_USER:
        raise PermissionError("mailbox_access_denied")

    service = get_service()
    profile = service.users().getProfile(userId="me").execute()
    actual_email = profile.get("emailAddress", "").casefold()

    if actual_email != EXPECTED_EMAIL.casefold():
        raise PermissionError("connected_mailbox_mismatch")

    return fetch_demo_emails(service)
