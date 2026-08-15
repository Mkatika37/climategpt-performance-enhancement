#!/usr/bin/env python3
"""
VIIRS Fire Detection MCP Server with ClimateGPT Integration
Provides tools to query satellite fire data AND get AI-powered climate analysis
"""

import asyncio
import duckdb
import sys
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timedelta

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio
from geopy.geocoders import Nominatim

# Import ClimateGPT client
from climategpt_client import get_climate_gpt_client

# Enable error logging
print("Starting VIIRS MCP Server with ClimateGPT...", file=sys.stderr)
sys.stderr.flush()

# Initialize MCP server
app = Server("viirs-fire-server")

# Initialize ClimateGPT client
climate_gpt = get_climate_gpt_client()

# Database configuration
DB_FILENAME = os.getenv("VIIRS_DUCKDB_PATH", "VIIRS_Thermal_Database.duckdb")
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = Path(DB_FILENAME)

# GHG Emission Constants
GHG_EMISSION_FACTOR_CO2 = 1.37
GHG_EMISSION_FACTOR_CH4 = 0.0048
GHG_EMISSION_FACTOR_N2O = 0.00020
GHG_EMISSION_FACTOR_CO = 0.063
GWP_CH4 = 28
GWP_N2O = 265

def get_db_connection():
    """Create a connection to the DuckDB database"""
    candidates = []
    
    env_path = os.getenv("VIIRS_DUCKDB_PATH")
    if env_path:
        candidates.append(Path(env_path))
    
    candidates.append(Path(DB_FILENAME))
    candidates.append(SCRIPT_DIR / DB_FILENAME)
    candidates.append(SCRIPT_DIR.parent / DB_FILENAME)
    candidates.append(Path.cwd() / DB_FILENAME)
    
    seen = set()
    cleaned = []
    for p in candidates:
        try:
            rp = p.resolve()
        except Exception:
            rp = p
        if str(rp) not in seen:
            cleaned.append(p)
            seen.add(str(rp))
    candidates = cleaned
    
    chosen = next((p for p in candidates if p.exists()), None)
    if chosen is None:
        attempted = "\n".join(f"  - {p}" for p in candidates)
        msg = f"Database not found. Tried:\n{attempted}"
        raise FileNotFoundError(msg)
    
    global DB_PATH
    DB_PATH = chosen.resolve()
    print(f"Connected to DuckDB at: {DB_PATH}", file=sys.stderr)
    
    return duckdb.connect(str(DB_PATH), read_only=True)

def format_results(results: list, columns: list) -> str:
    """Format query results as readable string"""
    if not results:
        return "No results found."
    
    output = [f"Found {len(results)} record(s):\n"]
    
    for i, row in enumerate(results, 1):
        output.append(f"--- Record {i} ---")
        for col, val in zip(columns, row):
            output.append(f"{col}: {val}")
        output.append("")
    
    return "\n".join(output)

def calculate_ghg_emissions(frp_mw: float, hours_old: float) -> dict:
    """Calculate GHG emissions based on FRP and duration"""
    total_energy_mj = frp_mw * hours_old * 3600
    
    co2_kg = total_energy_mj * GHG_EMISSION_FACTOR_CO2
    ch4_kg = total_energy_mj * GHG_EMISSION_FACTOR_CH4
    n2o_kg = total_energy_mj * GHG_EMISSION_FACTOR_N2O
    co_kg = total_energy_mj * GHG_EMISSION_FACTOR_CO
    
    ch4_co2e = ch4_kg * GWP_CH4
    n2o_co2e = n2o_kg * GWP_N2O
    total_co2e = co2_kg + ch4_co2e + n2o_co2e
    
    return {
        "frp_mw": frp_mw,
        "duration_hours": hours_old,
        "total_energy_mj": round(total_energy_mj, 2),
        "co2_kg": round(co2_kg, 2),
        "ch4_kg": round(ch4_kg, 4),
        "n2o_kg": round(n2o_kg, 4),
        "co_kg": round(co_kg, 2),
        "total_co2e_kg": round(total_co2e, 2),
        "total_co2e_tonnes": round(total_co2e / 1000, 4)
    }

def get_coordinates(place_name: str):
    """Get lat/lon coordinates from place name"""
    geolocator = Nominatim(user_agent="mcp-geolocator")
    location = geolocator.geocode(place_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def get_bounding_box(place_name: str, buffer_deg: float = 0.5):
    """Get bounding box around place name"""
    lat, lon = get_coordinates(place_name)
    if lat is None or lon is None:
        return None
    
    return (
        lat - buffer_deg,
        lat + buffer_deg,
        lon - buffer_deg,
        lon + buffer_deg
    )

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools including ClimateGPT integration"""
    return [
        # ... (keep all your existing tools) ...
        
        # NEW CLIMATEGPT TOOLS
        Tool(
            name="ask_climategpt_about_fires",
            description="Ask ClimateGPT to analyze fire data or answer climate-related questions about wildfire patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Your question about fires, climate impacts, or wildfire patterns"
                    },
                    "fire_context": {
                        "type": "string",
                        "description": "Optional: Fire data context to provide (e.g., from previous query results)"
                    }
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="get_fire_climate_analysis",
            description="Get ClimateGPT's analysis of recent fires in a specific location with climate context",
            inputSchema={
                "type": "object",
                "properties": {
                    "place_name": {
                        "type": "string",
                        "description": "Location name (e.g., 'California', 'Amazon', 'Australia')"
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back",
                        "default": 7
                    }
                },
                "required": ["place_name"]
            }
        ),
        Tool(
            name="explain_ghg_emissions_impact",
            description="Get ClimateGPT to explain the climate impact of calculated GHG emissions from fires",
            inputSchema={
                "type": "object",
                "properties": {
                    "emissions_summary": {
                        "type": "string",
                        "description": "Summary of GHG emissions (from previous calculations)"
                    }
                },
                "required": ["emissions_summary"]
            }
        ),
        
        # Keep all your existing tools below...
        Tool(
            name="describe_viirs_dataset",
            description="Return metadata and documentation URIs for the VIIRS Thermal Fire Dataset.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        # ... (all your other existing tools)
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls including ClimateGPT integration"""
    try:
        # NEW CLIMATEGPT TOOLS
        if name == "ask_climategpt_about_fires":
            question = arguments["question"]
            fire_context = arguments.get("fire_context", "")
            
            if fire_context:
                response = climate_gpt.analyze_fire_data(fire_context, question)
            else:
                response = climate_gpt.query(
                    question,
                    system_prompt="You are ClimateGPT, specialized in wildfire and climate science."
                )
            
            if response:
                return [TextContent(f"ClimateGPT Analysis:\n\n{response}")]
            else:
                return [TextContent("Error: Could not get response from ClimateGPT")]
        
        elif name == "get_fire_climate_analysis":
            place_name = arguments["place_name"]
            days_back = arguments.get("days_back", 7)
            
            # Get fire data for the location
            bbox = get_bounding_box(place_name, buffer_deg=0.5)
            if bbox is None:
                return [TextContent(f"Could not resolve location '{place_name}'.")]
            
            min_lat, max_lat, min_lon, max_lon = bbox
            conn = get_db_connection()
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            query = f"""
                SELECT COUNT(*) as fire_count, 
                       AVG(frp) as avg_frp, 
                       MAX(frp) as max_frp,
                       SUM(frp) as total_frp
                FROM fires
                WHERE latitude BETWEEN {min_lat} AND {max_lat}
                AND longitude BETWEEN {min_lon} AND {max_lon}
                AND acq_date >= '{start_date.strftime('%Y-%m-%d')}'
            """
            
            results = conn.execute(query).fetchone()
            conn.close()
            
            if not results or results[0] == 0:
                fire_summary = f"No fires detected near {place_name} in the last {days_back} days."
            else:
                fire_count, avg_frp, max_frp, total_frp = results
                fire_summary = (
                    f"Fire Activity near {place_name} (last {days_back} days):\n"
                    f"- Total detections: {fire_count}\n"
                    f"- Average FRP: {avg_frp:.2f} MW\n"
                    f"- Maximum FRP: {max_frp:.2f} MW\n"
                    f"- Total FRP: {total_frp:.2f} MW"
                )
            
            # Get ClimateGPT analysis
            analysis = climate_gpt.analyze_fire_data(fire_summary)
            
            if analysis:
                output = f"{fire_summary}\n\n=== ClimateGPT Analysis ===\n\n{analysis}"
                return [TextContent(output)]
            else:
                return [TextContent(f"{fire_summary}\n\n(Could not get ClimateGPT analysis)")]
        
        elif name == "explain_ghg_emissions_impact":
            emissions_summary = arguments["emissions_summary"]
            
            explanation = climate_gpt.explain_ghg_emissions({"summary": emissions_summary})
            
            if explanation:
                return [TextContent(f"=== Climate Impact Explanation ===\n\n{explanation}")]
            else:
                return [TextContent("Error: Could not get explanation from ClimateGPT")]
        
        # ALL YOUR EXISTING TOOLS CONTINUE HERE
        # (Keep all your existing tool implementations exactly as they are)
        
        else:
            return [TextContent(f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(f"Error: {str(e)}")]

async def main():
    """Run the MCP server"""
    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise

if __name__ == "__main__":
    asyncio.run(main())


