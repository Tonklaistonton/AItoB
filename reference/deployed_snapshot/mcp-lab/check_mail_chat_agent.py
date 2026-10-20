"""Run in the lab container. No model calls or Gmail access."""
import asyncio
from pathlib import Path
from unittest.mock import patch
import mail_chat_agent as agent


async def main():
    hr_key = Path("/gateway/credentials/hr.key").read_text().strip()
    with patch("mail_chat_agent.post_turn") as model:
        try:
            await agent.run_agent(hr_key, "อ่านอีเมลให้หน่อย")
        except PermissionError as error:
            assert str(error) == "mailbox_access_denied"
        else:
            raise AssertionError("HR incorrectly allowed")
        model.assert_not_called()
    print("PASS: HR denied before model call and MCP connection.")

    bad_calls = [
        {"function": {"name": "run_shell", "arguments": {}}},
        {"function": {"name": "search_emails", "arguments": {"query": "Canva", "max_results": 1, "role": "Finance"}}},
        {"function": {"name": "search_emails", "arguments": {"query": "Canva", "max_results": 100}}},
        {"function": {"name": "read_email", "arguments": {"message_id": "not-searched"}}},
    ]
    for call in bad_calls:
        try:
            agent.validate_call(call, set())
        except RuntimeError:
            pass
        else:
            raise AssertionError("Unsafe tool call accepted")
    print("PASS: Unknown tools, identity arguments, excessive limits and unsearched IDs rejected.")

    sources = {}
    data = agent.prepare_result("read_email", {"message_id": "abc"}, {
        "scope_label": "AItoB-Demo", "email": {
            "id": "abc", "subject": "Demo", "from": "Demo", "date": "",
            "body": "x" * 1800, "truncated": False
        }
    }, {"abc"}, sources)
    assert len(data["email"]["body"]) == 1000
    assert data["email"]["truncated"] is True
    assert sources["abc"]["truncated"] is True
    print("PASS: Context excerpt is bounded and truncation is preserved.")
    print("No LLM or Gmail calls were made.")


if __name__ == "__main__":
    asyncio.run(main())
