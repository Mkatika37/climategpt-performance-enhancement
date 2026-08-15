#!/usr/bin/env python3
"""
ClimateGPT MCP Integration Script
Connects local MCP servers to ClimateGPT API for answering questions
"""

import json
import subprocess
import sys
import requests
from typing import Dict, Any, List, Optional

# ClimateGPT API Configuration
CLIMATEGPT_URL = "https://erasmus.ai/models/climategpt_8b_test/v1/chat/completions"
CLIMATEGPT_AUTH = ("ai", "4climate")
CLIMATEGPT_MODEL = "/cache/climategpt_8b_test"

# MCP Server Paths - Windows Paths
VIIRS_SERVER_PATH = r"C:\Users\sthut\OneDrive\Desktop\CAPSTONE\GMU_DAEN_2025_02_D\Source\MCP\viirs_mcp_server.py"
DUCKDB_SERVER_PATH = r"C:\Users\sthut\OneDrive\Desktop\CAPSTONE\GMU_DAEN_2025_02_D\Source\MCP\Aqueduct_Server.py"

class MCPClient:
    """Client to interact with local MCP servers via stdio"""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.process = None
        self.request_id = 0
    
    def start(self):
        """Start the MCP server process"""
        self.process = subprocess.Popen(
            [sys.executable, self.server_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        print(f"Started MCP server: {self.server_path}", file=sys.stderr)
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server"""
        if not self.process:
            self.start()
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self.request_id
        }
        
        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json)
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if not response_line:
            stderr_output = self.process.stderr.read()
            raise Exception(f"MCP server error: {stderr_output}")
        
        response = json.loads(response_line)
        
        if "error" in response:
            raise Exception(f"MCP tool error: {response['error']}")
        
        return response.get("result")
    
    def list_tools(self) -> List[Dict]:
        """List available tools from the MCP server"""
        if not self.process:
            self.start()
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": self.request_id
        }
        
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json)
        self.process.stdin.flush()
        
        response_line = self.process.stdout.readline()
        response = json.loads(response_line)
        
        return response.get("result", {}).get("tools", [])
    
    def close(self):
        """Close the MCP server process"""
        if self.process:
            self.process.terminate()
            self.process.wait()


def query_climategpt_simple(question: str) -> str:
    """
    Simple query to ClimateGPT without tool calling
    Use this when you just want a direct answer
    """
    payload = {
        "model": CLIMATEGPT_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful climate analysis assistant."},
            {"role": "user", "content": question}
        ]
    }
    
    response = requests.post(
        CLIMATEGPT_URL,
        auth=CLIMATEGPT_AUTH,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60
    )
    
    response.raise_for_status()
    result = response.json()
    
    return result["choices"][0]["message"]["content"]


def query_with_mcp_data(question: str, mcp_data: str) -> str:
    """
    Query ClimateGPT with pre-fetched MCP data
    This is the recommended approach for your use case
    """
    payload = {
        "model": CLIMATEGPT_MODEL,
        "messages": [
            {"role": "system", "content": "You are a climate analysis assistant with access to fire detection and climate datasets."},
            {"role": "user", "content": f"Here is relevant data:\n\n{mcp_data}\n\nQuestion: {question}"}
        ]
    }
    
    response = requests.post(
        CLIMATEGPT_URL,
        auth=CLIMATEGPT_AUTH,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=60
    )
    
    response.raise_for_status()
    result = response.json()
    
    return result["choices"][0]["message"]["content"]


# ========== EXAMPLE USAGE PATTERNS ==========

def example_1_recent_fires():
    """Example: Ask about recent high-intensity fires"""
    print("\n=== Example 1: Recent High-Intensity Fires ===")
    
    # Step 1: Get data from MCP server
    viirs_client = MCPClient(VIIRS_SERVER_PATH)
    fire_data = viirs_client.call_tool(
        "query_high_intensity_fires",
        {"min_frp": 30, "hours": 48, "limit": 20}
    )
    viirs_client.close()
    
    # Step 2: Format the data
    mcp_data = json.dumps(fire_data, indent=2)
    
    # Step 3: Ask ClimateGPT to analyze it
    question = "Analyze these high-intensity fires. What patterns do you see in terms of location and intensity?"
    answer = query_with_mcp_data(question, mcp_data)
    
    print(f"\nQuestion: {question}")
    print(f"\nAnswer: {answer}")


def example_2_fires_by_location():
    """Example: Ask about fires in a specific location"""
    print("\n=== Example 2: Fires in Texas ===")
    
    # Step 1: Get data from MCP server
    viirs_client = MCPClient(VIIRS_SERVER_PATH)
    fire_data = viirs_client.call_tool(
        "query_viirs_by_place",
        {"place_name": "Texas", "buffer_deg": 2.0, "limit": 50}
    )
    viirs_client.close()
    
    # Step 2: Ask ClimateGPT
    mcp_data = json.dumps(fire_data, indent=2)
    question = "What can you tell me about fire activity in Texas based on this data? Are there any concerning trends?"
    answer = query_with_mcp_data(question, mcp_data)
    
    print(f"\nQuestion: {question}")
    print(f"\nAnswer: {answer}")


def example_3_ghg_emissions():
    """Example: Calculate and analyze GHG emissions"""
    print("\n=== Example 3: GHG Emissions Analysis ===")
    
    # Step 1: Get emissions data
    viirs_client = MCPClient(VIIRS_SERVER_PATH)
    emissions_data = viirs_client.call_tool(
        "calculate_ghg_emissions_by_place",
        {"place_name": "California", "buffer_deg": 2.0, "days_back": 7}
    )
    viirs_client.close()
    
    # Step 2: Ask ClimateGPT to interpret
    mcp_data = json.dumps(emissions_data, indent=2)
    question = "Based on these GHG emissions from fires, what is the environmental impact? How does this compare to typical emission sources?"
    answer = query_with_mcp_data(question, mcp_data)
    
    print(f"\nQuestion: {question}")
    print(f"\nAnswer: {answer}")


def example_4_datasets():
    """Example: Query DuckDB datasets"""
    print("\n=== Example 4: Climate Datasets ===")
    
    # Step 1: List available datasets
    duckdb_client = MCPClient(DUCKDB_SERVER_PATH)
    datasets = duckdb_client.call_tool("list_datasets", {})
    
    # Step 2: Get info about first dataset (if any)
    if datasets:
        dataset_info = duckdb_client.call_tool(
            "get_dataset_info",
            {"dataset_name": datasets[0]}
        )
        duckdb_client.close()
        
        # Step 3: Ask ClimateGPT about it
        mcp_data = json.dumps(dataset_info, indent=2)
        question = "What kind of climate data is available in this dataset? What analyses could we perform?"
        answer = query_with_mcp_data(question, mcp_data)
        
        print(f"\nQuestion: {question}")
        print(f"\nAnswer: {answer}")
    else:
        print("No datasets available")
        duckdb_client.close()


def interactive_mode():
    """Interactive mode for asking custom questions"""
    print("\n=== Interactive Mode ===")
    print("Choose data source:")
    print("1. VIIRS Fire Data")
    print("2. DuckDB Climate Datasets")
    print("3. Direct question (no data)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        print("\nAvailable VIIRS tools:")
        print("- query_recent_fires")
        print("- query_viirs_by_place")
        print("- query_high_intensity_fires")
        print("- calculate_ghg_emissions_by_place")
        
        tool_name = input("\nEnter tool name: ").strip()
        print("\nEnter arguments as JSON (e.g., {\"place_name\": \"Texas\"})")
        args_json = input("Arguments: ").strip()
        arguments = json.loads(args_json)
        
        viirs_client = MCPClient(VIIRS_SERVER_PATH)
        data = viirs_client.call_tool(tool_name, arguments)
        viirs_client.close()
        
        mcp_data = json.dumps(data, indent=2)
        question = input("\nYour question: ").strip()
        answer = query_with_mcp_data(question, mcp_data)
        
    elif choice == "2":
        duckdb_client = MCPClient(DUCKDB_SERVER_PATH)
        datasets = duckdb_client.call_tool("list_datasets", {})
        print(f"\nAvailable datasets: {datasets}")
        
        tool_name = input("\nEnter tool name (e.g., query_dataset): ").strip()
        args_json = input("Arguments (JSON): ").strip()
        arguments = json.loads(args_json)
        
        data = duckdb_client.call_tool(tool_name, arguments)
        duckdb_client.close()
        
        mcp_data = json.dumps(data, indent=2)
        question = input("\nYour question: ").strip()
        answer = query_with_mcp_data(question, mcp_data)
        
    else:
        question = input("\nYour question: ").strip()
        answer = query_climategpt_simple(question)
    
    print(f"\nAnswer:\n{answer}")


def main():
    """Main entry point"""
    print("ClimateGPT MCP Integration Tool")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "example1":
            example_1_recent_fires()
        elif mode == "example2":
            example_2_fires_by_location()
        elif mode == "example3":
            example_3_ghg_emissions()
        elif mode == "example4":
            example_4_datasets()
        else:
            print(f"Unknown mode: {mode}")
    else:
        print("\nUsage:")
        print("  python script.py example1    # Recent fires")
        print("  python script.py example2    # Fires by location")
        print("  python script.py example3    # GHG emissions")
        print("  python script.py example4    # Climate datasets")
        print("  python script.py interactive # Interactive mode")
        print("\nOr run without arguments for this help message")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        interactive_mode()
    else:
        main()
