# 0001: LINE Webhook Integration via Direct SQLite and Human-in-the-Loop Open WebUI

## Context
Customers contact AItoB through a LINE Official Account. We require incoming customer messages to appear directly inside Open WebUI with pre-generated AI draft answers, while enforcing strict Human-in-the-Loop (HITL) oversight so no unapproved AI hallucinations are sent to customers.

## Decision
1. **Direct SQLite Synchronization**: The `line-bot` service receives webhooks, verifies HMAC signatures fail-closed, queries the local assistant service for a draft, and inserts/updates chat records directly in `webui.db` mounted via the shared `webui-data` volume. This avoids patching the Open WebUI application server source code on container updates.
2. **Left-Aligned Customer Presentation**: Incoming customer inquiries and AI drafts are stored under the `assistant` role on the left side of the chat. The admin's reply is typed into Open WebUI's native input box and appears on the right side under the `user` role, maintaining standard messaging orientation.
3. **Draft Auto-Prefill**: Custom frontend assets (`loader.js`) detect open LINE cases and automatically populate the chat input textarea with the AI draft, allowing the admin to edit or send in one click.
4. **Outbound Push API**: Admin submissions are routed through `aitob_openwebui_pipe.py` to `line-bot:8003/api/reply`, which pushes the approved message to the customer using LINE Messaging API.

## Consequences
- Open WebUI container can be rebuilt or updated without losing custom LINE routes.
- Webhook traffic does not bypass internal security boundaries or expose unauthenticated endpoints.
- Outbound messages consume LINE push quota when reply tokens expire (>60 seconds).