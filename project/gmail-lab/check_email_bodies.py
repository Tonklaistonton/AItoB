from gmail_client import get_service
from email_reader import fetch_demo_emails

emails = fetch_demo_emails(get_service())
assert 1 <= len(emails) <= 5, "No labeled emails available."

for index, email in enumerate(emails, start=1):
    assert email["body"].strip(), "An email has no supported text body."
    assert len(email["body"]) <= 2000

    print("Email", index)
    print("Subject:", repr(email["subject"]))
    print("Body type:", email["body_kind"])
    print("Body characters:", len(email["body"]))
    print("Truncated:", email["truncated"])
    print()

print("PASS: Labeled email bodies extracted successfully.")
print("No LLM calls or attachment downloads were made.")
