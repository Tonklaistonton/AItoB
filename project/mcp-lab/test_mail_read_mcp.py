import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError
from mail_tools_server import execute_read

KEYS = Path("/gateway/credentials")
HR_KEY = (KEYS / "hr.key").read_text().strip()
OWNER_KEY = (KEYS / "finance.key").read_text().strip()


def server_for(key):
    return StdioServerParameters(
        command=sys.executable,
        args=["/app/mail_tools_server.py"],
        env={"AITOB_API_KEY": key}
    )


def check_local_denial():
    with patch.dict(os.environ, {"AITOB_API_KEY": HR_KEY}):
        with patch("mail_tools_server.urllib.request.urlopen") as network:
            try:
                execute_read("test-message")
            except ToolError as error:
                assert str(error) == "mailbox_access_denied"
            else:
                raise AssertionError("HR was incorrectly allowed")
            network.assert_not_called()

    print("PASS: HR denied before backend request.", flush=True)


async def check_denied(label, key):
    async with Client(server_for(key)) as client:
        result = await client.call_tool(
            "read_email", {"message_id": "test-message"}
        )
        assert result.is_error
        assert result.structured_content is None
        print("PASS:", label, "cannot read through MCP.", flush=True)


async def check_owner():
    async with Client(server_for(OWNER_KEY)) as client:
        listed = await client.list_tools()
        by_name = {tool.name: tool for tool in listed.tools}
        assert {"search_emails", "read_email"} <= set(by_name)
        assert set(by_name["read_email"].input_schema["properties"]) == {
            "message_id"
        }
        print("PASS: Both mail tools discovered.", flush=True)

        searched = await client.call_tool(
            "search_emails",
            {"query": "from:canva.com", "max_results": 1},
            read_timeout_seconds=120
        )
        assert not searched.is_error
        data = searched.structured_content
        assert isinstance(data, dict)
        assert len(data["results"]) == 1

        message_id = data["results"][0]["id"]
        read = await client.call_tool(
            "read_email",
            {"message_id": message_id},
            read_timeout_seconds=120
        )
        assert not read.is_error

        result = read.structured_content
        assert isinstance(result, dict)
        assert result["scope_label"] == "AItoB-Demo"
        email = result["email"]
        assert email["id"] == message_id
        assert email["body"].strip()
        assert len(email["body"]) <= 2000

        print("Subject:", repr(email["subject"]))
        print("Body characters:", len(email["body"]))
        print("Truncated:", email["truncated"])
        print("PASS: Owner searched then read through MCP.", flush=True)


async def main():
    check_local_denial()
    await check_denied("Missing key", "")
    await check_denied("HR", HR_KEY)
    await check_owner()
    print("No LLM calls were made.", flush=True)


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=300))
