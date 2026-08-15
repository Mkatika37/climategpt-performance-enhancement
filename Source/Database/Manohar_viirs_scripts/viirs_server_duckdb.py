"""MCP Server for VIIRS DuckDB Dataset Access."""

import asyncio
import json
import logging
from typing import Any, Dict, List
from datetime import datetime, timedelta

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from viirs_duckdb_handler import VIIRSDuckDBHandler, VIIRSConfig

# ------------------------
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
            description="Get information about the VIIRS thermal records table (schema, row count, columns, data types)",
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
            name="count_viirs_fires_by_date",
            description=(
                "Count fire detections on a specific date (YYYY-MM-DD format). "
                "Use this for queries like: 'how many fires on October 20, 2025', "
                "'fires detected on 2025-10-20', 'fire count for specific date'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (e.g., '2025-10-20')"
                    },
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional columns to group by"
                    },
                    "additional_filters": {
                        "type": "object",
                        "description": "Optional additional filters (e.g., {'confidence': 'high'})",
                        "additionalProperties": True
                    }
                },
                "required": ["date"]
            },
        ),
        Tool(
            name="count_viirs_fires_by_date_range",
            description=(
                "Count fire detections between two dates (both dates inclusive). "
                "Use this for queries like: 'fires between October 20 and October 22', "
                "'how many fires from 2025-10-20 to 2025-10-22', 'fires detected between two dates'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format (e.g., '2025-10-20')"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format (e.g., '2025-10-22')"
                    },
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional columns to group by"
                    },
                    "additional_filters": {
                        "type": "object",
                        "description": "Optional additional filters (e.g., {'confidence': 'high'})",
                        "additionalProperties": True
                    }
                },
                "required": ["start_date", "end_date"]
            },
        ),
        Tool(
            name="count_viirs_fires_by_days",
            description=(
                "Count fire detections from the last N days based on when they were detected (acquisition_timestamp). "
                "Use this for queries like: 'how many fires in last 7 days', 'fires detected in last 24 hours', "
                "'count fires from last 3 days', etc. Returns only counts, not full records."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "number",
                        "description": "Number of days to look back (e.g., 7 for last week, 1 for last 24 hours, 0.5 for last 12 hours)"
                    },
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional columns to group by for breakdown (e.g., ['satellite'], ['confidence'])"
                    },
                    "additional_filters": {
                        "type": "object",
                        "description": "Optional additional filters (e.g., {'confidence': 'high', 'satellite': 'NOAA-20'})",
                        "additionalProperties": True
                    }
                },
                "required": ["days_back"]
            },
        ),
        Tool(
            name="count_viirs_fires",
            description=(
                "Count fire detections with custom filters. "
                "For time-based queries, use 'count_viirs_fires_by_days', 'count_viirs_fires_by_date', or 'count_viirs_fires_by_date_range' instead. "
                "This tool is for advanced filtering with acquisition_timestamp ranges (YYYY-MM-DD format), "
                "location bounds, confidence levels, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_name": {
                        "type": "string",
                        "description": "Table name (default: VIIRS_Thermal_Records)"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Filters: acquisition_timestamp ranges, latitude/longitude ranges, confidence levels, satellite names",
                        "additionalProperties": True,
                    },
                    "group_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional columns to group by for breakdown",
                    },
                },
            },
        ),
        Tool(
            name="query_viirs_data",
            description="Query VIIRS thermal hotspot data and return actual fire detection records with filters. Use this when you need detailed record information, not just counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_name": {
                        "type": "string",
                        "description": "Table name (default: VIIRS_Thermal_Records)"
                    },
                    "filters": {
                        "type": "object",
                        "description": "Filters: latitude/longitude ranges, date ranges, confidence levels, satellite names, etc.",
                        "additionalProperties": True,
                    },
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of columns to select. If not provided, returns all columns.",
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                        "description": "Max number of records to return (default: 100, max: 1000)"
                    },
                },
            },
        ),
        Tool(
            name="get_viirs_summary",
            description="Get summary statistics for VIIRS thermal data including numeric stats (avg/min/max temps, FRP), categorical breakdowns (satellite counts, confidence distribution), etc.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_name": {
                        "type": "string",
                        "description": "Table name (default: VIIRS_Thermal_Records)"
                    },
                },
            },
        ),
        Tool(
            name="set_viirs_db_path",
            description="Change the VIIRS DuckDB database path and reconnect. Use this if you need to switch to a different database file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "db_path": {
                        "type": "string",
                        "description": "Full path to VIIRS .duckdb file"
                    },
                    "read_only": {
                        "type": "boolean",
                        "description": "Open in read-only mode (default: true)"
                    },
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
            result = {
                "datasets": datasets,
                "count": len(datasets),
                "message": f"Found {len(datasets)} table(s) in the VIIRS database"
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_viirs_dataset_info":
            dataset_name = arguments.get("dataset_name", "VIIRS_Thermal_Records")
            info = handler.get_dataset_info(dataset_name)
            if info is None:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Dataset '{dataset_name}' not found",
                        "message": "Use list_viirs_datasets to see available tables"
                    }, indent=2)
                )]
            return [TextContent(type="text", text=json.dumps(info, indent=2))]

        elif name == "count_viirs_fires_by_date":
            date = arguments.get("date")
            group_by = arguments.get("group_by")
            additional_filters = arguments.get("additional_filters")
            
            if not date:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Date parameter is required in YYYY-MM-DD format"
                    }, indent=2)
                )]
            
            result = handler.count_fires_by_date(
                "VIIRS_Thermal_Records",
                date=date,
                group_by=group_by,
                additional_filters=additional_filters
            )
            
            if result is None:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "Dataset not found"}, indent=2)
                )]
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "count_viirs_fires_by_date_range":
            start_date = arguments.get("start_date")
            end_date = arguments.get("end_date")
            group_by = arguments.get("group_by")
            additional_filters = arguments.get("additional_filters")
            
            if not start_date or not end_date:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": "Both start_date and end_date parameters are required in YYYY-MM-DD format"
                    }, indent=2)
                )]
            
            result = handler.count_fires_by_date_range(
                "VIIRS_Thermal_Records",
                start_date=start_date,
                end_date=end_date,
                group_by=group_by,
                additional_filters=additional_filters
            )
            
            if result is None:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "Dataset not found"}, indent=2)
                )]
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "count_viirs_fires_by_days":
            days_back = arguments.get("days_back", 7)
            group_by = arguments.get("group_by")
            additional_filters = arguments.get("additional_filters")
            
            result = handler.count_fires_by_days(
                "VIIRS_Thermal_Records",
                days_back=days_back,
                group_by=group_by,
                additional_filters=additional_filters
            )
            
            if result is None:
                return [TextContent(
                    type="text",
                    text=json.dumps({"error": "Dataset not found"}, indent=2)
                )]
            
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "count_viirs_fires":
            dataset_name = arguments.get("dataset_name", "VIIRS_Thermal_Records")
            filters = arguments.get("filters")
            group_by = arguments.get("group_by")
            
            result = handler.count_fires(dataset_name, filters=filters, group_by=group_by)
            if result is None:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Dataset '{dataset_name}' not found"
                    }, indent=2)
                )]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "query_viirs_data":
            dataset_name = arguments.get("dataset_name", "VIIRS_Thermal_Records")
            filters = arguments.get("filters")
            columns = arguments.get("columns")
            limit = arguments.get("limit", 100)
            
            # Enforce maximum limit to prevent excessive data transfer
            if limit > 1000:
                limit = 1000
            
            result = handler.query_dataset(
                dataset_name,
                filters=filters,
                columns=columns,
                limit=limit
            )
            if result is None:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Dataset '{dataset_name}' not found"
                    }, indent=2)
                )]
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_viirs_summary":
            dataset_name = arguments.get("dataset_name", "VIIRS_Thermal_Records")
            summary = handler.get_dataset_summary(dataset_name)
            if summary is None:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Dataset '{dataset_name}' not found"
                    }, indent=2)
                )]
            return [TextContent(type="text", text=json.dumps(summary, indent=2))]

        elif name == "set_viirs_db_path":
            new_db_path = arguments.get("db_path")
            read_only = arguments.get("read_only", True)
            
            cfg = VIIRSConfig(
                db_path=new_db_path,
                read_only=read_only,
            )

            # Close existing handler
            if handler:
                try:
                    handler.close()
                except Exception as e:
                    logger.warning(f"Failed to close previous handler: {e}")

            # Create new handler with new config
            handler = VIIRSDuckDBHandler(cfg)

            try:
                # Test connection by listing datasets
                datasets = handler.get_available_datasets()
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": True,
                        "db_path": cfg.db_path,
                        "read_only": cfg.read_only,
                        "tables_found": len(datasets),
                        "message": f"Successfully connected to database with {len(datasets)} table(s)"
                    }, indent=2)
                )]
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e),
                        "message": "Failed to connect to the specified database"
                    }, indent=2)
                )]

        else:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": f"Unknown tool: '{name}'",
                    "message": "Use list_tools to see available tools"
                }, indent=2)
            )]

    except Exception as e:
        logger.exception(f"Error in tool call '{name}': {e}")
        return [TextContent(
            type="text",
            text=json.dumps({
                "error": str(e),
                "tool": name,
                "arguments": arguments
            }, indent=2)
        )]


# ------------------------
# Main entry point
# ------------------------
async def main():
    logger.info("Starting VIIRS Dataset MCP Server...")

    # Test database connection on startup
    try:
        datasets = handler.get_available_datasets()
        logger.info(f"✓ Connected to DuckDB: {handler.config.db_path}")
        logger.info(f"✓ Found {len(datasets)} table(s): {', '.join(datasets)}")
    except Exception as e:
        logger.warning(f"⚠ Startup check failed: {e}")
        logger.warning("  Server will start anyway, but database may not be accessible")

    # Start MCP server
    async with stdio_server() as (read_stream, write_stream):
        logger.info("✓ MCP server is ready and listening for requests...")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="viirs-dataset-mcp",
                server_version="0.5.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities=None,
                ),
            ),
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        raise


