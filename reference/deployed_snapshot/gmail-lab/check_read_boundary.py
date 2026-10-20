import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "/gateway")

from gmail_read import read_message_for_key
from email_access import EXPECTED_EMAIL

key = Path("/gateway/credentials/finance.key").read_text().strip()

with patch("gmail_read.get_service") as connect:
    service = connect.return_value
    users = service.users.return_value

    users.getProfile.return_value.execute.return_value = {
        "emailAddress": EXPECTED_EMAIL
    }
    users.labels.return_value.list.return_value.execute.return_value = {
        "labels": [{"id": "allowed-label", "name": "AItoB-Demo"}]
    }

    get_message = users.messages.return_value.get
    get_message.return_value.execute.return_value = {
        "labelIds": ["another-label"]
    }

    status, result = read_message_for_key(
        "Bearer " + key,
        {"message_id": "test-message"}
    )

    assert status == 403
    assert "email" not in result
    get_message.assert_called_once_with(
        userId="me", id="test-message", format="minimal"
    )

print("PASS: Message outside allowed label denied before full body fetch.")
