#!/usr/bin/env python3
"""
HTTP Adapter for VIIRS MCP Server
Exposes the VIIRS MCP server via HTTP for Claude Desktop and other clients
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

# Add MCP directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
MCP_DIR = SCRIPT_DIR.parent / "MCP"
sys.path.insert(0, str(MCP_DIR))

# Import the VIIRS MCP server
try:
    import viirs_mcp_server as viirs
    print(f"Successfully imported viirs_mcp_server from {MCP_DIR}", file=sys.stderr)
except ImportError as e:
    print(f"ERROR: Failed to import viirs_mcp_server: {e}", file=sys.stderr)
    print(f"MCP_DIR: {MCP_DIR}", file=sys.stderr)
    print(f"sys.path: {sys.path[:3]}", file=sys.stderr)
    sys.exit(1)

app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Set database path if not already set
if not os.environ.get("VIIRS_DUCKDB_PATH"):
    os.environ["VIIRS_DUCKDB_PATH"] = "/srv/viirs_database/VIIRS_Thermal_Database.duckdb"
    print(f"Set VIIRS_DUCKDB_PATH to {os.environ['VIIRS_DUCKDB_PATH']}", file=sys.stderr)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "viirs-http-adapter",
        "mcp_server": "viirs_mcp_server.py",
        "database": os.environ.get("VIIRS_DUCKDB_PATH", "not set")
    })


@app.route('/mcp/tools/list', methods=['POST', 'GET'])
async def list_tools():
    """List available MCP tools"""
    try:
        # Call the async list_tools function
        tools = await viirs.list_tools()

        # Convert Tool objects to dict
        tools_dict = []
        for tool in tools:
            tools_dict.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema
            })

        return jsonify({
            "tools": tools_dict
        })
    except Exception as e:
        import traceback
        return jsonify({
            "error": "Failed to list tools",
            "detail": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route('/mcp/call_tool', methods=['POST'])
def call_tool():
    """
    Call an MCP tool
    Expects JSON: {"tool": "tool_name", "arguments": {...}}
    """
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({"error": "Invalid JSON", "detail": str(e)}), 400

    tool_name = data.get("tool")
    arguments = data.get("arguments", {})

    if not tool_name:
        return jsonify({"error": "Missing 'tool' field"}), 400

    try:
        # Create new event loop for this request
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Call the async call_tool function
            result = loop.run_until_complete(viirs.call_tool(tool_name, arguments))

            # Convert TextContent objects to plain dict
            result_data = []
            for item in result:
                if hasattr(item, 'text'):
                    result_data.append({
                        "type": "text",
                        "text": item.text
                    })
                elif hasattr(item, 'content'):
                    result_data.append({
                        "type": "text",
                        "text": item.content
                    })
                else:
                    result_data.append({
                        "type": "text",
                        "text": str(item)
                    })

            return jsonify({
                "tool": tool_name,
                "result": result_data
            })

        finally:
            loop.close()

    except Exception as e:
        import traceback
        return jsonify({
            "error": "Tool execution failed",
            "tool": tool_name,
            "detail": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route('/mcp/tools/call', methods=['POST'])
def tools_call():
    """
    Alternative endpoint matching MCP protocol
    Expects JSON: {"name": "tool_name", "arguments": {...}}
    """
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({"error": "Invalid JSON", "detail": str(e)}), 400

    tool_name = data.get("name")
    arguments = data.get("arguments", {})

    if not tool_name:
        return jsonify({"error": "Missing 'name' field"}), 400

    # Forward to call_tool
    return call_tool_internal(tool_name, arguments)


def call_tool_internal(tool_name, arguments):
    """Internal function to call a tool"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(viirs.call_tool(tool_name, arguments))

            result_data = []
            for item in result:
                if hasattr(item, 'text'):
                    result_data.append({"type": "text", "text": item.text})
                elif hasattr(item, 'content'):
                    result_data.append({"type": "text", "text": item.content})
                else:
                    result_data.append({"type": "text", "text": str(item)})

            return jsonify({
                "content": result_data
            })

        finally:
            loop.close()

    except Exception as e:
        import traceback
        return jsonify({
            "error": {"code": -32603, "message": str(e)},
            "traceback": traceback.format_exc()
        }), 500


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='VIIRS MCP HTTP Adapter')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    print("\n" + "="*60)
    print("VIIRS MCP HTTP Adapter")
    print("="*60)
    print(f"HTTP Server: http://{args.host}:{args.port}")
    print(f"MCP Server: {MCP_DIR / 'viirs_mcp_server.py'}")
    print(f"Database: {os.environ.get('VIIRS_DUCKDB_PATH', 'Not set')}")
    print("\nEndpoints:")
    print(f"  GET  /health - Health check")
    print(f"  GET  /mcp/tools/list - List available tools")
    print(f"  POST /mcp/call_tool - Call a tool")
    print(f"  POST /mcp/tools/call - Call a tool (MCP format)")
    print("="*60 + "\n")

    app.run(host=args.host, port=args.port, debug=args.debug)

