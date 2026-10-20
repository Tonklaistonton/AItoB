import asyncio
import json
import sys
from pathlib import Path
from mcp import Client, StdioServerParameters


async def main():
    server_file = Path(__file__).resolve().parent / "server.py"
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(server_file)]
    )

    async with Client(server) as client:
        result = await client.list_tools()

        for tool in result.tools:
            print("Tool:", tool.name)
            print("Description:", tool.description)
            print(
                "Input schema:",
                json.dumps(tool.input_schema, ensure_ascii=False)
            )

        assert any(tool.name == "lab_status" for tool in result.tools)
        print("PASS: MCP client discovered lab_status.")


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=30))
