"""MCP Server for VIIRS DuckDB Dataset Access."""

import asyncio
import json
import logging
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from viirs_duckdb_handler import VIIRSDuckDBHandler, VIIRSConfig

# ------------------------py
# Configure logging
# ------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------
# Define fallback NotificationOptions (for old SDKs)
# ------------------------
try:
    from mcp.types import NotificationOptions
except ImportError:
    class NotificationOptions:
        def __init__(self):
            self.tools_changed = None

# ------------------------
# Initialize server + handler
# ------------------------
server = Server("viirs-dataset-mcp")
handler = VIIRSDuckDBHandler(VIIRSConfig())


# ------------------------
# Tool Definitions
# ------------------------
@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="list_viirs_datasets",
            description="List all available VIIRS DuckDB tables",
            inputSchema={
                "type": "object",
                "properties": {
                    "schemas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of schemas to include, e.g., ['main']",
                    }
                },
            },
        ),
        Tool(
            name="get_viirs_dataset_info",
            description="Get information about the VIIRS thermal records table",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_name": {
                        "type": "string",
                        "description": "Table name (default: VIIRS_Thermal_Records)",
                    }
                },
            },
        ),
        Tool(
            name="query_viirs_data",
            description="Query VIIRS thermal hotspot data with filters (date range, location, confidence, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_name": {"type": "string", "description": "Table name (default: VIIRS_Thermal_Records)"},
                    "filters": {
                        "type": "object",
                        "description": "Filters: latitude/longitude ranges, date ranges, confidence levels, satellite names",
                        "additionalProperties": True,
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of columns to select",
                    },
                    "limit": {"type": "integer", "minimum": 1, "description": "Max number of records to return"},
                },
            },
        ),
        Tool(
            name="get_viirs_summary",
            description="Get summary statistics for VIIRS thermal data (fire counts, temperature stats, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_name": {"type": "string", "description": "Table name (default: VIIRS_Thermal_Records)"},
                },
            },
        ),
        Tool(
            name="set_viirs_db_path",
            description="Change the VIIRS DuckDB database path and reconnect",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_path": {"type": "string", "description": "Path to VIIRS .duckdb file"},
                    "read_only": {"type": "boolean", "description": "Open in read-only mode (default true)"},
                },
                "required": ["db_path"],
            },
        ),
    ]


# ------------------------
# Tool Logic
# ------------------------
@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    global handler
    try:
        if name == "list_viirs_datasets":
            schemas = arguments.get("schemas")
            datasets = handler.get_available_datasets(schema_filter=schemas)
            result = {"datasets": datasets, "count": len(datasets)}
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "get_viirs_dataset_info":
            dataset_name = arguments.get("dataset_name", "VIIRS_Thermal_Records")
            info = handler.get_dataset_info(dataset_name)
            if info is None:
                return [TextContent(type="text", text=f"Error: '{dataset_name}' not found")]
            return [TextContent(type="text", text=json.dumps(info, indent=2))]

        if name == "query_viirs_data":
            dataset_name = arguments.get("dataset_name", "VIIRS_Thermal_Records")
            filters = arguments.get("filters")
            columns = arguments.get("columns")
            limit = arguments.get("limit", 100)
            result = handler.query_dataset(dataset_name, filters=filters, columns=columns, limit=limit)
            if result is None:
                return [TextContent(type="text", text=f"Error: '{dataset_name}' not found")]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "get_viirs_summary":
            dataset_name = arguments.get("dataset_name", "VIIRS_Thermal_Records")
            summary = handler.get_dataset_summary(dataset_name)
            if summary is None:
                return [TextContent(type="text", text=f"Error: '{dataset_name}' not found")]
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        if name == "set_viirs_db_path":
            cfg = VIIRSConfig(
                db_path=arguments.get("db_path"),
                read_only=arguments.get("read_only", True),
            )

            if handler:
                try:
                    handler.close()
                except Exception as e:
                    logger.warning(f"Failed to close previous handler: {e}")

            handler = VIIRSDuckDBHandler(cfg)

            try:
                datasets = handler.get_available_datasets()
                return [TextContent(type="text", text=json.dumps({
                    "ok": True,
                    "db_path": cfg.db_path,
                    "tables_found": len(datasets)
                }, indent=2))]
            except Exception as e:
                return [TextContent(type="text", text=json.dumps({"ok": False, "error": str(e)}, indent=2))]

        return [TextContent(type="text", text=f"Error: unknown tool '{name}'")]

    except Exception as e:
        logger.exception("Error in tool call: %s", name)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


# ------------------------
# Main entry point
# ------------------------
async def main():
    logger.info("Starting VIIRS Dataset MCP Server...")

    try:
        datasets = handler.get_available_datasets()
        logger.info(f"Connected to DuckDB: {handler.config.db_path} | Tables: {len(datasets)} found.")
    except Exception as e:
        logger.warning(f"Startup check failed: {e}")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="viirs-dataset-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities=None,
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())


