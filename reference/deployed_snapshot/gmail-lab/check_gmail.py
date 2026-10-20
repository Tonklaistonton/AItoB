from gmail_client import get_service

LABEL_NAME = "AItoB-Demo"

service = get_service()
response = service.users().labels().list(userId="me").execute()
labels = response.get("labels", [])

selected = next(
    (label for label in labels if label["name"] == LABEL_NAME),
    None
)

if selected is None:
    raise SystemExit("STOP: Create the AItoB-Demo label in Gmail first.")

print("PASS: Gmail API connected and AItoB-Demo label found.")

response = service.users().messages().list(
    userId="me",
    labelIds=[selected["id"]],
    maxResults=5,
    includeSpamTrash=False
).execute()

messages = response.get("messages", [])
print("Messages selected for this sample:", len(messages))

if not messages:
    raise SystemExit("STOP: Apply AItoB-Demo to at least one email.")

print("PASS: Labeled email sample is available.")
print("Email subjects and bodies have not been fetched.")
