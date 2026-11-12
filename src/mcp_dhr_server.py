import asyncio
import sqlite3
import os
from typing import Any, List
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

DB_PATH = os.getenv("DB_PATH", "medregulator.sqlite")
mcp_server = Server("medregulator-dhr-mcp")

@mcp_server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="lookup_dhr_lot",
            description="Retrieve Device History Record (DHR), UDI, assembly line, and supplier details by lot number.",
            inputSchema={
                "type": "object",
                "properties": {"lot_number": {"type": "string"}},
                "required": ["lot_number"],
            },
        ),
        Tool(
            name="search_historical_capas",
            description="Retrieve past CAPAs and root causes matching a device component name.",
            inputSchema={
                "type": "object",
                "properties": {"component_name": {"type": "string"}},
                "required": ["component_name"],
            },
        ),
    ]

@mcp_server.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        if name == "lookup_dhr_lot":
            cur.execute("SELECT * FROM device_history_records WHERE lot_number = ?", (arguments["lot_number"],))
            row = cur.fetchone()
            result = dict(row) if row else {"error": f"Lot {arguments['lot_number']} not found."}
            return [TextContent(type="text", text=str(result))]

        elif name == "search_historical_capas":
            cur.execute("SELECT * FROM historical_capas WHERE component_name LIKE ?", (f"%{arguments['component_name']}%",))
            rows = [dict(r) for r in cur.fetchall()]
            return [TextContent(type="text", text=str(rows))]

        raise ValueError(f"Unknown MCP tool: {name}")
    finally:
        conn.close()

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await mcp_server.run(read_stream, write_stream, mcp_server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())