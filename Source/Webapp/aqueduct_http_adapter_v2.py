#!/usr/bin/env python3
"""
HTTP Adapter for Aqueduct MCP Server
Exposes the Aqueduct MCP server via HTTP for Claude Desktop and other clients
"""

import os
import sys
import json
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add MCP directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
MCP_DIR = SCRIPT_DIR.parent / "MCP"
sys.path.insert(0, str(MCP_DIR))

# Import the Aqueduct MCP server
try:
    from Aqueduct_Server import app as mcp_app
    # Import the tool functions
    from Aqueduct_Server import (
        list_datasets,
        get_dataset_info,
        query_dataset,
        aggregate_dataset,
        set_db_path,
        get_document_text
    )
    print(f"Successfully imported Aqueduct_Server from {MCP_DIR}", file=sys.stderr)
except ImportError as e:
    print(f"ERROR: Failed to import Aqueduct_Server: {e}", file=sys.stderr)
    print(f"MCP_DIR: {MCP_DIR}", file=sys.stderr)
    sys.exit(1)

app = Flask(__name__)
CORS(app)  # Enable CORS

# Create a fake Context class since FastMCP tools expect it
class FakeContext:
    """Fake context object for FastMCP tools that expect a Context parameter"""
    pass

# Map tool names to functions
TOOL_MAP = {
    "list_datasets": list_datasets,
    "get_dataset_info": get_dataset_info,
    "query_dataset": query_dataset,
    "aggregate_dataset": aggregate_dataset,
    "set_db_path": set_db_path,
    "get_document_text": get_document_text
}


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "aqueduct-http-adapter",
        "mcp_server": "Aqueduct_Server.py",
        "available_tools": list(TOOL_MAP.keys())
    })


@app.route('/mcp/tools/list', methods=['POST', 'GET'])
def list_tools_endpoint():
    """List available MCP tools"""
    try:
        # Get tools from the MCP app
        tools = mcp_app.list_tools()

        # Convert to dict format
        tools_dict = []
        for tool in tools:
            tool_dict = {
                "name": tool.name,
                "description": tool.description,
            }
            if hasattr(tool, 'inputSchema'):
                tool_dict["inputSchema"] = tool.inputSchema
            tools_dict.append(tool_dict)

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

    return call_tool_internal(tool_name, arguments)


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

    return call_tool_internal(tool_name, arguments)


def call_tool_internal(tool_name, arguments):
    """Internal function to call a tool"""
    # Get the tool function
    tool_func = TOOL_MAP.get(tool_name)

    if not tool_func:
        return jsonify({
            "error": "Unknown tool",
            "tool": tool_name,
            "available_tools": list(TOOL_MAP.keys())
        }), 404

    try:
        # Create fake context
        context = FakeContext()

        # Call the tool function
        # FastMCP tools expect (context, **kwargs)
        result = tool_func(context, **arguments)

        # Format the result
        if isinstance(result, (dict, list)):
            # Already JSON-serializable
            result_data = result
        elif isinstance(result, str):
            # String result
            result_data = {"text": result}
        else:
            # Try to convert to dict
            try:
                result_data = dict(result) if hasattr(result, '__dict__') else str(result)
            except:
                result_data = str(result)

        return jsonify({
            "tool": tool_name,
            "result": result_data
        })

    except TypeError as e:
        # Handle case where tool doesn't expect context
        try:
            result = tool_func(**arguments)

            if isinstance(result, (dict, list)):
                result_data = result
            elif isinstance(result, str):
                result_data = {"text": result}
            else:
                try:
                    result_data = dict(result) if hasattr(result, '__dict__') else str(result)
                except:
                    result_data = str(result)

            return jsonify({
                "tool": tool_name,
                "result": result_data
            })

        except Exception as e2:
            import traceback
            return jsonify({
                "error": "Tool execution failed",
                "tool": tool_name,
                "detail": str(e2),
                "original_error": str(e),
                "traceback": traceback.format_exc()
            }), 500

    except Exception as e:
        import traceback
        return jsonify({
            "error": "Tool execution failed",
            "tool": tool_name,
            "detail": str(e),
            "traceback": traceback.format_exc()
        }), 500


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Aqueduct MCP HTTP Adapter')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8001, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    print("\n" + "="*60)
    print("Aqueduct MCP HTTP Adapter")
    print("="*60)
    print(f"HTTP Server: http://{args.host}:{args.port}")
    print(f"MCP Server: {MCP_DIR / 'Aqueduct_Server.py'}")
    print(f"\nAvailable Tools: {', '.join(TOOL_MAP.keys())}")
    print("\nEndpoints:")
    print(f"  GET  /health - Health check")
    print(f"  GET  /mcp/tools/list - List available tools")
    print(f"  POST /mcp/call_tool - Call a tool")
    print(f"  POST /mcp/tools/call - Call a tool (MCP format)")
    print("="*60 + "\n")

    app.run(host=args.host, port=args.port, debug=args.debug)

