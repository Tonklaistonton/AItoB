import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError
from finance_server import execute_expenses

CREDENTIALS = Path("/gateway/credentials")
HR_KEY = (CREDENTIALS / "hr.key").read_text().strip()
FINANCE_KEY = (CREDENTIALS / "finance.key").read_text().strip()


def check_hr_stops_before_tool():
    with patch.dict(os.environ, {"AITOB_API_KEY": HR_KEY}):
        with patch("finance_server.clean_expenses") as tool:
            try:
                execute_expenses()
            except ToolError as error:
                assert str(error) == "finance_workflow_access_denied"
                tool.assert_not_called()
            else:
                raise AssertionError("HR was incorrectly allowed")

    print("PASS: MCP handler denies HR before CSV tool.")


async def check_session(label, key, expected_error):
    server = StdioServerParameters(
        command=sys.executable,
        args=["/app/finance_server.py"],
        env={"AITOB_API_KEY": key}
    )

    async with Client(server) as client:
        listed = await client.list_tools()
        tool = next(
            item for item in listed.tools
            if item.name == "clean_finance_expenses"
        )
        assert not tool.input_schema.get("properties", {})

        result = await client.call_tool("clean_finance_expenses", {})
        assert result.is_error == expected_error

        if expected_error:
            assert result.structured_content is None
            print("PASS:", label, "denied through MCP.")
        else:
            report = result.structured_content
            assert report["input_rows"] == 6
            assert report["cleaned_rows"] == 3
            assert report["duplicate_rows"] == 1
            assert report["rejected_rows"] == 2
            assert report["total_amount"] == "2000.00"
            print(json.dumps(report, ensure_ascii=False, indent=2))
            print("PASS: Finance CSV tool works through MCP.")


async def main():
    check_hr_stops_before_tool()
    await check_session("Missing key", "", True)
    await check_session("Invalid key", "wrong-key", True)
    await check_session("HR", HR_KEY, True)
    await check_session("Finance", FINANCE_KEY, False)


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=60))
