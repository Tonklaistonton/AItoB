from mcp.server import MCPServer

mcp = MCPServer("AItoB Lab")


@mcp.tool()
def lab_status() -> dict[str, str]:
    """Return basic lab status without reading business data."""
    return {
        "status": "ready",
        "service": "aitob-mcp-lab"
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
