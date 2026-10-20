import asyncio
import json
import sys
from pathlib import Path
from mcp import Client, StdioServerParameters


async def main():
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve().parent / "server.py")]
    )

    async with Client(server) as client:
        result = await client.call_tool("lab_status", {})

        print("Is error:", result.is_error)
        print(
            "Structured result:",
            json.dumps(result.structured_content, ensure_ascii=False)
        )

        assert not result.is_error
        assert result.structured_content == {
            "status": "ready",
            "service": "aitob-mcp-lab"
        }
        print("PASS: lab_status called successfully through MCP.")

        missing = await client.call_tool("missing_tool", {})
        print("Missing tool is error:", missing.is_error)
        assert missing.is_error
        print("PASS: unknown tool returned an MCP tool error.")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=30))
