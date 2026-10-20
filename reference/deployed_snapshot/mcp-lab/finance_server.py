import csv
import os
import sys

sys.path.insert(0, "/gateway")

from auth import authenticate
from workflow import clean_expenses
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("AItoB Finance")


def execute_expenses():
    key = os.environ.get("AITOB_API_KEY", "")
    identity = authenticate("Bearer " + key)

    if identity is None:
        raise ToolError("invalid_or_missing_api_key")

    if (
        identity.get("team") != "Finance"
        or identity.get("role") != "finance_reader"
    ):
        raise ToolError("finance_workflow_access_denied")

    try:
        return clean_expenses(identity)
    except (OSError, ValueError, csv.Error):
        raise ToolError("workflow_file_or_format_error") from None


@mcp.tool(structured_output=True)
def clean_finance_expenses() -> dict[str, object]:
    """Clean the fixed Finance expenses CSV and return verified totals."""
    return execute_expenses()


if __name__ == "__main__":
    mcp.run(transport="stdio")
