import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError
from mail_tools_server import execute_search

KEYS = Path("/gateway/credentials")
HR_KEY = (KEYS / "hr.key").read_text().strip()
OWNER_KEY = (KEYS / "finance.key").read_text().strip()


def check_denied_before_network():
    with patch.dict(os.environ, {"AITOB_API_KEY": HR_KEY}):
        with patch("mail_tools_server.call_backend") as backend:
            try:
                execute_search("from:canva.com", 3)
            except ToolError as error:
                assert str(error) == "mailbox_access_denied"
            else:
                raise AssertionError("HR was incorrectly allowed")
            backend.assert_not_called()

    print("PASS: HR denied before contacting Gmail backend.", flush=True)


async def check_case(label, key, limit, expected_error):
    server = StdioServerParameters(
        command=sys.executable,
        args=["/app/mail_tools_server.py"],
        env={"AITOB_API_KEY": key}
    )

    async with Client(server) as client:
        tools = await client.list_tools()
        tool = next(item for item in tools.tools if item.name == "search_emails")
        assert set(tool.input_schema["properties"]) == {
            "query", "max_results"
        }

        result = await client.call_tool(
            "search_emails",
            {"query": "from:canva.com", "max_results": limit},
            read_timeout_seconds=120
        )
        assert result.is_error == expected_error

        if expected_error:
            assert result.structured_content is None
            print("PASS:", label, "denied through MCP.", flush=True)
            return

        data = result.structured_content
        assert isinstance(data, dict)
        assert data["scope_label"] == "AItoB-Demo"
        assert data["count"] == len(data["results"])
        assert 1 <= data["count"] <= limit

        print(json.dumps(data, ensure_ascii=False, indent=2))
        print("PASS: Owner searched Gmail through MCP.", flush=True)


async def main():
    check_denied_before_network()
    await check_case("Missing key", "", 3, True)
    await check_case("Invalid key", "wrong-key", 3, True)
    await check_case("HR", HR_KEY, 3, True)
    await check_case("Excessive limit", OWNER_KEY, 100, True)
    await check_case("Owner", OWNER_KEY, 3, False)


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=180))
