"""Offline checks in the Mac lab container: no model or Gmail requests."""
import asyncio
from pathlib import Path
from unittest.mock import patch
import aitob_agent as agent
from aitob_agent_policy import eligible_tool_names


async def main():
    hr = {"user": "may", "team": "HR", "role": "hr_reader"}
    finance = {"user": "ton", "team": "Finance", "role": "finance_reader"}
    assert eligible_tool_names(hr) == {"search_company_docs"}
    assert eligible_tool_names(finance) == set(agent.ALLOWED)
    other_finance = {"user": "another-finance", "team": "Finance", "role": "finance_reader"}
    assert eligible_tool_names(other_finance) == {"search_company_docs", "clean_finance_expenses"}
    print("PASS: HR, Finance and mailbox ownership expose the correct tool sets.")

    with patch("aitob_agent.post_turn") as model:
        try:
            await agent.run_agent("wrong-key", "วันลามีกี่วัน")
        except PermissionError:
            pass
        else:
            raise AssertionError("Invalid key allowed")
        model.assert_not_called()
    print("PASS: Invalid key denied before model call and MCP connection.")

    for name, arguments in [
        ("clean_finance_expenses", {}),
        ("search_emails", {"query": "Canva", "max_results": 1}),
        ("read_email", {"message_id": "abc"}),
    ]:
        try:
            agent.validate_call({"function": {"name": name, "arguments": arguments}},
                                {"abc"}, eligible_tool_names(hr))
        except RuntimeError:
            pass
        else:
            raise AssertionError("HR tool request incorrectly allowed")
    print("PASS: HR tool calls outside the permission set are rejected.")

    try:
        agent.validate_call({"function": {"name": "search_company_docs", "arguments": {
            "query": "วันลา", "role": "Finance"}}}, set(), eligible_tool_names(hr))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Extra identity argument allowed")
    print("PASS: Extra role arguments are rejected.")
    print("No LLM, Gmail or CSV operations were performed.")


if __name__ == "__main__":
    asyncio.run(main())
