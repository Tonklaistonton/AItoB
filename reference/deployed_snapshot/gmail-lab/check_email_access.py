import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "/gateway")

from auth import authenticate
from email_access import read_owned_emails

denied_users = [
    None,
    {"user": "may", "team": "HR", "role": "hr_reader"},
    {
        "user": "another-finance-user",
        "team": "Finance",
        "role": "finance_reader"
    }
]

with patch("email_access.get_service") as connect:
    for identity in denied_users:
        try:
            read_owned_emails(identity)
        except PermissionError as error:
            assert str(error) == "mailbox_access_denied"
        else:
            raise AssertionError("Non-owner was incorrectly allowed")
    connect.assert_not_called()

print("PASS: Non-owners denied before Gmail connection.")

owner = {"user": "ton", "team": "Finance", "role": "finance_reader"}

with patch("email_access.get_service") as connect:
    with patch("email_access.fetch_demo_emails") as fetch:
        connect.return_value.users.return_value.getProfile.return_value \
            .execute.return_value = {"emailAddress": "other@example.invalid"}

        try:
            read_owned_emails(owner)
        except PermissionError as error:
            assert str(error) == "connected_mailbox_mismatch"
        else:
            raise AssertionError("Wrong Google account was allowed")

        fetch.assert_not_called()

print("PASS: Wrong Google account denied before fetching emails.")

key = Path("/gateway/credentials/finance.key").read_text().strip()
identity = authenticate("Bearer " + key)
assert identity is not None
assert identity["user"] == "ton"

emails = read_owned_emails(identity)
assert 1 <= len(emails) <= 5

print("PASS: Authenticated owner can read the labeled sample.")
print("Emails available:", len(emails))
print("No LLM calls were made.")
