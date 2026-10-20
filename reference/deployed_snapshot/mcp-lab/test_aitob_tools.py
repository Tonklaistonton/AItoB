"""Integration checkpoint: invokes real MCP and the existing lab services."""
import asyncio
import json
import sys
from pathlib import Path
from mcp import Client, StdioServerParameters

KEYS = Path("/gateway/credentials")
HR_KEY = (KEYS / "hr.key").read_text().strip()
FINANCE_KEY = (KEYS / "finance.key").read_text().strip()
EXPECTED = {"search_company_docs", "clean_finance_expenses", "search_emails", "read_email"}


def server_for(key):
    return StdioServerParameters(
        command=sys.executable,
        args=["/app/aitob_tools_server.py"],
        env={"AITOB_API_KEY": key}
    )


async def success(client, name, arguments):
    result = await client.call_tool(name, arguments, read_timeout_seconds=120)
    if result.is_error:
        texts = [getattr(block, "text", "") for block in result.content]
        raise AssertionError(name + " failed: " + " ".join(texts))
    assert isinstance(result.structured_content, dict)
    return result.structured_content


async def denied(client, name, arguments):
    result = await client.call_tool(name, arguments, read_timeout_seconds=120)
    assert result.is_error, name + " incorrectly allowed"
    assert result.structured_content is None


async def main():
    async with Client(server_for(HR_KEY)) as client:
        listed = await client.list_tools()
        assert {tool.name for tool in listed.tools} == EXPECTED
        print("PASS: All four MCP tools discovered.", flush=True)

        data = await success(client, "search_company_docs", {"query": "วันลา และ งบ Finance"})
        assert data["count"] == 1
        assert [doc["id"] for doc in data["documents"]] == ["hr-leave"]
        serialized = json.dumps(data, ensure_ascii=False)
        assert "12 วัน" in serialized
        assert "480000" not in serialized
        assert "FIN-DEMO-482" not in serialized
        print("PASS: HR document results contain HR data only.", flush=True)

        await denied(client, "clean_finance_expenses", {})
        await denied(client, "search_emails", {"query": "Canva", "max_results": 1})
        await denied(client, "read_email", {"message_id": "test-message"})
        print("PASS: HR denied Finance CSV and mailbox tools.", flush=True)

    async with Client(server_for(FINANCE_KEY)) as client:
        data = await success(client, "search_company_docs", {"query": "วันลา และ งบ Finance"})
        assert [doc["id"] for doc in data["documents"]] == ["finance-budget"]
        assert "480000" in data["documents"][0]["content"]
        print("PASS: Finance document results contain Finance data only.", flush=True)

        report = await success(client, "clean_finance_expenses", {})
        assert (report["input_rows"], report["cleaned_rows"], report["duplicate_rows"], report["rejected_rows"]) == (6, 3, 1, 2)
        assert report["total_amount"] == "2000.00"
        print("PASS: Finance CSV cleaning returns the verified 2000.00 total.", flush=True)

        found = await success(client, "search_emails", {"query": "from:canva.com", "max_results": 1})
        assert found["count"] == 1
        message_id = found["results"][0]["id"]
        read = await success(client, "read_email", {"message_id": message_id})
        assert read["email"]["id"] == message_id
        assert read["email"]["body"].strip()
        print("PASS: Mailbox owner searches and reads through the unified server.", flush=True)

    async with Client(server_for("")) as client:
        await denied(client, "search_company_docs", {"query": "วันลา"})
        print("PASS: Missing key denied document access.", flush=True)

    print("No LLM calls were made. Finance cleaned output was regenerated.", flush=True)


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=300))
