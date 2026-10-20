from auth import authenticate
from email_access import OWNER_USER, EXPECTED_EMAIL
from email_reader import LABEL_NAME
from gmail_client import get_service
from google.auth.exceptions import GoogleAuthError
from googleapiclient.errors import HttpError


def search_for_key(authorization, arguments):
    identity = authenticate(authorization)
    if identity is None:
        return 401, {"error": "invalid_or_missing_api_key"}

    if identity.get("user") != OWNER_USER:
        return 403, {"error": "mailbox_access_denied"}

    if (
        not isinstance(arguments, dict)
        or set(arguments) != {"query", "max_results"}
    ):
        return 400, {"error": "invalid_search_arguments"}

    query = arguments["query"]
    limit = arguments["max_results"]

    if (
        not isinstance(query, str)
        or not 1 <= len(query.strip()) <= 300
        or type(limit) is not int
        or not 1 <= limit <= 5
    ):
        return 400, {"error": "invalid_search_arguments"}

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

        response = service.users().messages().list(
            userId="me",
            labelIds=[label["id"]],
            q=query.strip(),
            maxResults=limit,
            includeSpamTrash=False
        ).execute()

        references = response.get("messages", [])
        return 200, {
            "results": [
                {"id": item["id"], "thread_id": item["threadId"]}
                for item in references
            ],
            "count": len(references),
            "scope_label": LABEL_NAME
        }

    except (GoogleAuthError, HttpError, OSError, ValueError, RuntimeError):
        return 502, {"error": "gmail_search_failed"}
