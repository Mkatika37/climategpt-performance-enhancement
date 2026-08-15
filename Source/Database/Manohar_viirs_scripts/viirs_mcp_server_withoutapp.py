#!/usr/bin/env python3
"""
VIIRS Fire Detection MCP Server
Provides tools to query satellite thermal hotspot and fire activity data from DuckDB
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

# Enable error logging to stderr for debugging
print("Starting VIIRS MCP Server...", file=sys.stderr)
sys.stderr.flush()

# Initialize MCP server
app = Server("viirs-fire-server")

# Base directory for all VIIRS files (LOCAL PATHS)
BASE_DIR = Path(r".\Source\Database")
DB_FILENAME = "VIIRS_Thermal_Database.duckdb"
DB_PATH = BASE_DIR / DB_FILENAME

# Documentation path (LOCAL PATH)
DOC_PATH = Path(r".\Docs\Satellite_(VIIRS)_Thermal_Hotspots_and_Fire_Activity.md")

# Script directory
SCRIPT_DIR = Path(__file__).resolve().parent

# GHG Emission Constants
GHG_EMISSION_FACTOR_CO2 = 1.37  # kg CO2 per MJ
GHG_EMISSION_FACTOR_CH4 = 0.0048  # kg CH4 per MJ (methane)
GHG_EMISSION_FACTOR_N2O = 0.00020  # kg N2O per MJ (nitrous oxide)
GHG_EMISSION_FACTOR_CO = 0.063  # kg CO per MJ (carbon monoxide)

# Global Warming Potential (100-year horizon)
GWP_CH4 = 28
GWP_N2O = 265

def get_db_connection():
    """Create a connection to the DuckDB database using multiple fallback locations."""
    candidates = []

    # 1) If env var supplied, try it first
    env_path = os.getenv("VIIRS_DUCKDB_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            candidates.append(p / DB_FILENAME)
        else:
            candidates.append(p)

    # 2) PRIMARY: Your local Windows path
    candidates.append(BASE_DIR / DB_FILENAME)

    # 3) Next to this script
    candidates.append(SCRIPT_DIR / DB_FILENAME)

    # 4) Parent directory
    candidates.append(SCRIPT_DIR.parent / DB_FILENAME)

    # 5) Current working directory
    candidates.append(Path.cwd() / DB_FILENAME)

    # Normalize and deduplicate
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

    print("DB connection candidates (in order):", file=sys.stderr)
    for p in candidates:
        print(f"  - {p} -> exists: {p.exists()}", file=sys.stderr)
    sys.stderr.flush()

    chosen = next((p for p in candidates if p.exists()), None)
    if chosen is None:
        attempted = "\n".join(f"  - {p}" for p in candidates)
        msg = (
            f"Database not found. Tried these locations:\n{attempted}\n\n"
            f"Expected location: {BASE_DIR / DB_FILENAME}\n"
            "Ensure the DB file exists or set VIIRS_DUCKDB_PATH env var."
        )
        print("ERROR:", msg, file=sys.stderr)
        sys.stderr.flush()
        raise FileNotFoundError(msg)

    global DB_PATH
    DB_PATH = chosen.resolve()
    print(f"✓ Connecting to DuckDB at: {DB_PATH}", file=sys.stderr)
    sys.stderr.flush()

    return duckdb.connect(str(DB_PATH), read_only=True)

def format_results(results: list, columns: list) -> str:
    """Format query results as a readable string"""
    if not results:
        return "No results found."
    
    output = []
    output.append(f"Found {len(results)} record(s):\n")
    
    for i, row in enumerate(results, 1):
        output.append(f"--- Record {i} ---")
        for col, val in zip(columns, row):
            output.append(f"{col}: {val}")
        output.append("")
    
    return "\n".join(output)

def count_fires(conn, filters: dict = None, group_by: list = None) -> dict:
    """
    Core counting function with flexible filters.
    
    Args:
        conn: DuckDB connection
        filters: Dictionary of filters (e.g., {'acquisition_timestamp': {'min': '2025-10-20 00:00:00'}})
        group_by: Optional list of columns to group by
    
    Returns:
        Dictionary with count results
    """
    # Build SELECT clause
    if group_by:
        group_cols = ", ".join([f'"{col}"' for col in group_by])
        select_clause = f"{group_cols}, COUNT(*) as fire_count"
    else:
        select_clause = "COUNT(*) as fire_count"
    
    sql = f"SELECT {select_clause} FROM VIIRS_Thermal_Records"
    params = []
    
    # Build WHERE clause
    where_clauses = []
    if filters:
        for col, val in filters.items():
            col_q = f'"{col}"'
            if isinstance(val, dict):
                # Range filter: {'min': ..., 'max': ...}
                if "min" in val and "max" in val:
                    where_clauses.append(f"{col_q} BETWEEN ? AND ?")
                    params.extend([val["min"], val["max"]])
                elif "min" in val:
                    where_clauses.append(f"{col_q} >= ?")
                    params.append(val["min"])
                elif "max" in val:
                    where_clauses.append(f"{col_q} <= ?")
                    params.append(val["max"])
            elif isinstance(val, list):
                if len(val) == 0:
                    where_clauses.append("1=0")
                else:
                    placeholders = ", ".join(["?"] * len(val))
                    where_clauses.append(f"{col_q} IN ({placeholders})")
                    params.extend(val)
            else:
                where_clauses.append(f"{col_q} = ?")
                params.append(val)
    
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    
    # Add GROUP BY if specified
    if group_by:
        group_cols = ", ".join([f'"{col}"' for col in group_by])
        sql += f" GROUP BY {group_cols}"
        sql += " ORDER BY fire_count DESC"
    
    # Execute query
    rel = conn.execute(sql, params)
    
    if group_by:
        # Return grouped results
        results = rel.fetchall()
        columns = [desc[0] for desc in conn.description]
        
        grouped_data = []
        total_count = 0
        for row in results:
            record = {}
            for col, val in zip(columns, row):
                record[col] = val
            grouped_data.append(record)
            total_count += record.get('fire_count', 0)
        
        return {
            "total_count": total_count,
            "grouped_results": grouped_data,
            "group_by": group_by,
            "filters_applied": filters if filters else {}
        }
    else:
        # Return simple count
        count = rel.fetchone()[0]
        return {
            "fire_count": int(count),
            "filters_applied": filters if filters else {}
        }

def calculate_ghg_emissions(frp_mw: float, hours_old: float) -> dict:
    """Calculate GHG emissions based on Fire Radiative Power and duration"""
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
    """Helper function to get coordinates"""
    geolocator = Nominatim(user_agent="mcp-geolocator")
    location = geolocator.geocode(place_name)
    if location:
        return location.latitude, location.longitude
    return None, None

def get_bounding_box(place_name: str, buffer_deg: float = 0.5):
    """Helper function to get bounding box"""
    lat, lon = get_coordinates(place_name)
    if lat is None or lon is None:
        return None
    
    return (
        lat - buffer_deg,  # min_lat
        lat + buffer_deg,  # max_lat
        lon - buffer_deg,  # min_lon
        lon + buffer_deg   # max_lon
    )

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for querying VIIRS fire data"""
    return [
        Tool(
            name="describe_viirs_dataset",
            description="Return metadata and documentation URIs for the VIIRS Thermal Fire Dataset.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        # NEW: Count tools using acquisition_timestamp
        Tool(
            name="count_viirs_fires_by_date",
            description=(
                "Count fire detections on a specific date (YYYY-MM-DD format) using acquisition_timestamp. "
                "Use this for queries like: 'how many fires on October 20, 2025'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (e.g., '2025-10-20')"
                    },
                    "min_confidence": {
                        "type": "string",
                        "description": "Minimum confidence level",
                        "enum": ["low", "nominal", "high", "all"],
                        "default": "all"
                    }
                },
                "required": ["date"]
            },
        ),
        Tool(
            name="count_viirs_fires_by_date_range",
            description=(
                "Count fire detections between two dates (both inclusive) using acquisition_timestamp. "
                "Use for: 'fires between October 20 and October 22'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    },
                    "min_confidence": {
                        "type": "string",
                        "enum": ["low", "nominal", "high", "all"],
                        "default": "all"
                    }
                },
                "required": ["start_date", "end_date"]
            },
        ),
        Tool(
            name="count_viirs_fires_by_days",
            description=(
                "Count fire detections from the last N days using acquisition_timestamp. "
                "Use for: 'how many fires in last 7 days', 'fires in last 24 hours'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "number",
                        "description": "Days to look back (e.g., 7, 1, 0.5 for 12 hours)"
                    },
                    "min_confidence": {
                        "type": "string",
                        "enum": ["low", "nominal", "high", "all"],
                        "default": "all"
                    }
                },
                "required": ["days_back"]
            },
        ),
        Tool(
            name="query_recent_fires",
            description="Get recent fire detections within the last N hours. Returns location, intensity, and confidence data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "integer",
                        "description": "Number of hours to look back (e.g., 24 for last day)",
                        "default": 24
                    },
                    "min_confidence": {
                        "type": "string",
                        "description": "Minimum confidence level: 'low' or 'nominal'",
                        "enum": ["low", "nominal"],
                        "default": "nominal"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 100
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="query_fires_by_location",
            description="Query fires within a geographic bounding box (latitude/longitude coordinates)",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_lat": {"type": "number"},
                    "max_lat": {"type": "number"},
                    "min_lon": {"type": "number"},
                    "max_lon": {"type": "number"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "limit": {"type": "integer", "default": 100}
                },
                "required": ["min_lat", "max_lat", "min_lon", "max_lon"]
            }
        ),
        Tool(
            name="query_high_intensity_fires",
            description="Get high-intensity fires based on Fire Radiative Power (FRP) threshold",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_frp": {"type": "number", "default": 20},
                    "hours": {"type": "integer", "default": 72},
                    "limit": {"type": "integer", "default": 50}
                },
                "required": []
            }
        ),
        Tool(
            name="get_fire_statistics",
            description="Get summary statistics about fire detections",
            inputSchema={
                "type": "object",
                "properties": {
                    "time_period_hours": {"type": "integer", "default": 24}
                },
                "required": []
            }
        ),
        Tool(
            name="query_fires_by_date",
            description="Query fires detected on a specific date or date range",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["low", "nominal", "all"], "default": "all"},
                    "limit": {"type": "integer", "default": 100}
                },
                "required": ["start_date"]
            }
        ),
        Tool(
            name="execute_custom_query",
            description="Execute a custom SQL query on the VIIRS fire database. Table name is VIIRS_Thermal_Records.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {"type": "string"}
                },
                "required": ["sql"]
            }
        ),
        Tool(
            name="get_coordinates",
            description="Convert a place name into latitude and longitude.",
            inputSchema={
                "type": "object",
                "properties": {
                    "place_name": {"type": "string"}
                },
                "required": ["place_name"]
            }
        ),
        Tool(
            name="get_bounding_box",
            description="Return a bounding box around a place name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "place_name": {"type": "string"},
                    "buffer_deg": {"type": "number", "default": 0.5}
                },
                "required": ["place_name"]
            }
        ),
        Tool(
            name="query_viirs_by_place",
            description="Query VIIRS fire data using a bounding box around a place name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "place_name": {"type": "string"},
                    "buffer_deg": {"type": "number", "default": 0.5},
                    "limit": {"type": "integer", "default": 100},
                    "min_confidence": {"type": "string", "enum": ["low", "nominal"], "default": "nominal"}
                },
                "required": ["place_name"]
            }
        ),
        Tool(
            name="count_viirs_by_place",
            description="Count fires near a location. Use for 'how many fires near X' queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "place_name": {"type": "string"},
                    "buffer_deg": {"type": "number", "default": 0.5},
                    "min_confidence": {"type": "string", "enum": ["low", "nominal"], "default": "nominal"}
                },
                "required": ["place_name"]
            }
        ),
        Tool(
            name="summarize_viirs_docs",
            description="Summarize the local VIIRS documentation file.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }   
        ),
        Tool(
            name="calculate_fire_ghg_emissions",
            description="Calculate GHG emissions for a single fire.",
            inputSchema={
                "type": "object",
                "properties": {
                    "frp": {"type": "number"},
                    "hours_old": {"type": "number"}
                },
                "required": ["frp", "hours_old"]
            }
        ),
        Tool(
            name="calculate_ghg_emissions_by_location",
            description="Calculate total GHG emissions for fires in a geographic area",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_lat": {"type": "number"},
                    "max_lat": {"type": "number"},
                    "min_lon": {"type": "number"},
                    "max_lon": {"type": "number"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"}
                },
                "required": ["min_lat", "max_lat", "min_lon", "max_lon"]
            }
        ),
        Tool(
            name="calculate_ghg_emissions_by_place",
            description="Calculate total GHG emissions for fires near a location",
            inputSchema={
                "type": "object",
                "properties": {
                    "place_name": {"type": "string"},
                    "buffer_deg": {"type": "number", "default": 0.5},
                    "days_back": {"type": "integer", "default": 7}
                },
                "required": ["place_name"]
            }
        ),
        Tool(
            name="get_ghg_emissions_summary",
            description="Get GHG emissions summary for recent fires",
            inputSchema={
                "type": "object",
                "properties": {
                    "time_period_hours": {"type": "integer", "default": 24}
                }
            }
        )
    ]

# NEW: Helper functions for counting tools using acquisition_timestamp
async def run_count_fires_by_date(params: dict[str, Any]) -> TextContent:
    """Count fires on a specific date using acquisition_timestamp"""
    date = params["date"]
    min_conf = params.get("min_confidence", "all")
    
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        start_dt = date_obj.strftime('%Y-%m-%d 00:00:00')
        end_dt = date_obj.strftime('%Y-%m-%d 23:59:59')
    except ValueError:
        return TextContent(type="text", text=f"Invalid date format: {date}")
    
    conn = get_db_connection()
    
    filters = {
        'acquisition_timestamp': {'min': start_dt, 'max': end_dt}
    }
    
    if min_conf != "all":
        filters['confidence'] = min_conf
    
    result = count_fires(conn, filters=filters)
    count = result['fire_count']
    
    return TextContent(type="text", text=f"Fires detected on {date}: {count:,} (confidence: {min_conf})")

async def run_count_fires_by_date_range(params: dict[str, Any]) -> TextContent:
    """Count fires between two dates using acquisition_timestamp"""
    start_date = params["start_date"]
    end_date = params["end_date"]
    min_conf = params.get("min_confidence", "all")
    
    try:
        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
        start_dt = start_obj.strftime('%Y-%m-%d 00:00:00')
        end_dt = end_obj.strftime('%Y-%m-%d 23:59:59')
        days_span = (end_obj - start_obj).days + 1
    except ValueError as e:
        return TextContent(type="text", text=f"Invalid date format: {e}")
    
    if end_obj < start_obj:
        return TextContent(type="text", text="End date cannot be before start date")
    
    conn = get_db_connection()
    
    filters = {
        'acquisition_timestamp': {'min': start_dt, 'max': end_dt}
    }
    
    if min_conf != "all":
        filters['confidence'] = min_conf
    
    result = count_fires(conn, filters=filters)
    count = result['fire_count']
    
    return TextContent(type="text", text=(
        f"Fires from {start_date} to {end_date}:\n"
        f"Total: {count:,}\n"
        f"Days: {days_span}\n"
        f"Confidence: {min_conf}"
    ))

async def run_count_fires_by_days(params: dict[str, Any]) -> TextContent:
    """Count fires from last N days using acquisition_timestamp"""
    days_back = params["days_back"]
    min_conf = params.get("min_confidence", "all")
    
    cutoff_dt = datetime.now() - timedelta(days=days_back)
    cutoff_str = cutoff_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    conn = get_db_connection()
    
    filters = {
        'acquisition_timestamp': {'min': cutoff_str}
    }
    
    if min_conf != "all":
        filters['confidence'] = min_conf
    
    result = count_fires(conn, filters=filters)
    count = result['fire_count']
    
    return TextContent(type="text", text=(
        f"Fires in last {days_back} days:\n"
        f"Total: {count:,}\n"
        f"Cutoff: {cutoff_str}\n"
        f"Confidence: {min_conf}"
    ))

async def run_get_coordinates(params: dict[str, Any]) -> TextContent:
    place_name = params["place_name"]
    geolocator = Nominatim(user_agent="mcp-geolocator")
    location = geolocator.geocode(place_name)

    if location:
        return TextContent(type="text", text=f"Latitude: {location.latitude}, Longitude: {location.longitude}")
    else:
        return TextContent(type="text", text=f"Could not find coordinates for '{place_name}'.")

async def run_get_bounding_box(params: dict[str, Any]) -> TextContent:
    place_name = params["place_name"]
    buffer_deg = params.get("buffer_deg", 0.5)

    lat, lon = get_coordinates(place_name)
    if lat is None or lon is None:
        return TextContent(type="text", text=f"Could not find coordinates for '{place_name}'.")

    min_lat = lat - buffer_deg
    max_lat = lat + buffer_deg
    min_lon = lon - buffer_deg
    max_lon = lon + buffer_deg

    return TextContent(type="text", text=(
        f"Bounding box for '{place_name}' with buffer {buffer_deg}°:\n"
        f"Latitude: {min_lat} to {max_lat}\n"
        f"Longitude: {min_lon} to {max_lon}"
    ))

async def run_query_viirs_by_place(params: dict[str, Any]) -> TextContent:
    place_name = params["place_name"]
    buffer_deg = params.get("buffer_deg", 0.5)
    limit = params.get("limit", 100)
    min_conf = params.get("min_confidence", "nominal")

    bbox = get_bounding_box(place_name, buffer_deg)
    if bbox is None:
        return TextContent(type="text", text=f"Could not resolve location '{place_name}'.")

    min_lat, max_lat, min_lon, max_lon = bbox
    conn = get_db_connection()

    query = f"""
        SELECT uid, latitude, longitude, brightness_temp_i4, brightness_temp_i5, frp_mw,
               confidence, acquisition_timestamp, satellite
        FROM VIIRS_Thermal_Records
        WHERE latitude BETWEEN {min_lat} AND {max_lat}
            AND longitude BETWEEN {min_lon} AND {max_lon}
            AND confidence = '{min_conf}'
        ORDER BY frp_mw DESC
        LIMIT {limit}
    """
    results = conn.execute(query).fetchall()
    columns = [desc[0] for desc in conn.description]
    return TextContent(type="text", text=format_results(results, columns))

async def run_count_viirs_by_place(params: dict[str, Any]) -> TextContent:
    """Return a count of VIIRS records within a bounding box for a named place."""
    place_name = params["place_name"]
    buffer_deg = params.get("buffer_deg", 0.5)
    min_conf = params.get("min_confidence", "nominal")

    bbox = get_bounding_box(place_name, buffer_deg)
    if bbox is None:
        return TextContent(type="text", text=f"Could not resolve location '{place_name}'.")

    min_lat, max_lat, min_lon, max_lon = bbox
    conn = get_db_connection()

    query = f"""
        SELECT COUNT(*) as cnt
        FROM VIIRS_Thermal_Records
        WHERE latitude BETWEEN {min_lat} AND {max_lat}
          AND longitude BETWEEN {min_lon} AND {max_lon}
          AND confidence = '{min_conf}'
    """

    try:
        cnt = conn.execute(query).fetchone()[0]
    except Exception as e:
        return TextContent(type="text", text=f"Error executing count query: {e}")

    return TextContent(type="text", text=f"Count of matching VIIRS detections: {cnt}")

async def run_describe_viirs_dataset(_: dict[str, Any]) -> TextContent:
    conn = get_db_connection()
    df = conn.execute("SELECT * FROM VIIRS_Thermal_Records LIMIT 1").fetchdf()

    dataset_name = "NASA LANCE VIIRS Thermal Fire Dataset (375m NRT)"
    rows = conn.execute("SELECT COUNT(*) FROM VIIRS_Thermal_Records").fetchone()[0]
    columns = list(df.columns)
    dtypes = {col: str(df[col].dtype) for col in columns}

    description = (
        "NASA LANCE VIIRS Thermal Fire Dataset (375m NRT)."
        "This data set is updated from the NASA FIRMS system every 24 hours."
        "Each row represents a detected hotspot pixel from the VIIRS sensor. "
        "Key fields include:\n"
        "- latitude, longitude: location of detection center of 375m fire pixel\n"
        "- bright_Ti4: VIIRS I-4 channel brightness temperature of the fire pixel measured in Kelvin\n"
        "- bright_Ti5: VIIRS I-5 channel brightness temperature of the fire pixel measured in Kelvin\n"
        "- confidence: detection confidence where only 'nominal' or 'high' appear in this data\n"
        "- frp: fire radiative power in MW megawatts\n"
        "- daynight: whether detection occurred during day D or night N\n"
        "- acq_date, acq_time: timestamp of detection\n"
        "- satellite: N= Suomi National Polar-orbiting Partnership (Suomi NPP), N20=NOAA-20 (designated JPSS-1 prior to launch), N21=NOAA-21 (designated JPSS-2 prior to launch)\n"
        "- hours_old: hours since detection\n"
    )

    uris = [
        str(DOC_PATH),
        "https://www.earthdata.nasa.gov/data/instruments/viirs/viirs-i-band-375-m-active-fire-data"
    ]

    metadata = {
        "name": dataset_name,
        "rows": rows,
        "columns": columns,
        "dtypes": dtypes,
        "description": description,
        "uris": uris,
    }

    output = [
        f" Dataset: {metadata['name']}",
        f" Rows: {metadata['rows']}",
        f" Columns: {', '.join(metadata['columns'])}",
        f" Documentation: {', '.join(metadata['uris'])}",
        "\n Description:\n" + metadata["description"]
    ]
    return TextContent(type="text", text="\n".join(output))

async def run_summarize_viirs_docs(_: dict[str, Any]) -> TextContent:
    if not DOC_PATH.exists():
        return TextContent(type="text", text=f"Documentation file not found at: {DOC_PATH}")

    try:
        content = DOC_PATH.read_text(encoding="utf-8")
    except Exception as e:
        return TextContent(type="text", text=f"Error reading documentation file: {e}")

    lines = content.splitlines()
    summary_lines = []
    for line in lines:
        if line.strip().startswith("#") or line.strip().startswith("##"):
            summary_lines.append(line.strip())
        elif "VIIRS" in line or "fire" in line.lower():
            summary_lines.append(line.strip())

    summary = "\n".join(summary_lines[:20])
    return TextContent(type="text", text=f"Summary of VIIRS Documentation:\n\n{summary}")

@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    conn = None
    try:
        print(f"DEBUG: call_tool invoked: {name}", file=sys.stderr)
        sys.stderr.flush()
        conn = get_db_connection()

        # NEW: Date-based counting tools
        if name == "count_viirs_fires_by_date":
            return [await run_count_fires_by_date(arguments)]
        if name == "count_viirs_fires_by_date_range":
            return [await run_count_fires_by_date_range(arguments)]
        if name == "count_viirs_fires_by_days":
            return [await run_count_fires_by_days(arguments)]
        
        # Original tools
        if name == "get_coordinates":
            return [await run_get_coordinates(arguments)]
        if name == "get_bounding_box":
            return [await run_get_bounding_box(arguments)]
        if name == "query_viirs_by_place":
            return [await run_query_viirs_by_place(arguments)]
        if name == "count_viirs_by_place":
            return [await run_count_viirs_by_place(arguments)]
        if name == "describe_viirs_dataset":
            return [await run_describe_viirs_dataset(arguments)]
        if name == "summarize_viirs_docs":
            return [await run_summarize_viirs_docs(arguments)]

        if name == "query_recent_fires":
            hours = arguments.get("hours", 24)
            min_confidence = arguments.get("min_confidence", "nominal")
            limit = arguments.get("limit", 100)
            
            query = f"""
                SELECT latitude, longitude, brightness_temp_i4, brightness_temp_i5, frp_mw,
                       confidence, acquisition_timestamp, hours_old, satellite
                FROM VIIRS_Thermal_Records
                WHERE hours_old <= {hours}
                AND confidence = '{min_confidence}'
                ORDER BY acquisition_timestamp DESC
                LIMIT {limit}
            """
            
            results = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]

            if not results:
                return [TextContent(type="text", text="Database does not have records for this time period")]

            output = format_results(results, columns)
            return [TextContent(type="text", text=output)]
        
        elif name == "query_fires_by_location":
            min_lat = arguments["min_lat"]
            max_lat = arguments["max_lat"]
            min_lon = arguments["min_lon"]
            max_lon = arguments["max_lon"]
            start_date = arguments.get("start_date")
            end_date = arguments.get("end_date")
            limit = arguments.get("limit", 100)
            
            query = f"""
                SELECT latitude, longitude, brightness_temp_i4, frp_mw, confidence,
                       acquisition_timestamp, hours_old
                FROM VIIRS_Thermal_Records
                WHERE latitude BETWEEN {min_lat} AND {max_lat}
                AND longitude BETWEEN {min_lon} AND {max_lon}
            """
            
            if start_date:
                query += f" AND DATE(acquisition_timestamp) >= '{start_date}'"
            if end_date:
                query += f" AND DATE(acquisition_timestamp) <= '{end_date}'"
            
            query += f" ORDER BY acquisition_timestamp DESC LIMIT {limit}"
            
            results = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]
            
            output = format_results(results, columns)
            return [TextContent(text=output)]
        
        elif name == "query_high_intensity_fires":
            min_frp = arguments.get("min_frp", 20)
            hours = arguments.get("hours", 72)
            limit = arguments.get("limit", 50)
            
            query = f"""
                SELECT latitude, longitude, frp_mw, brightness_temp_i4, brightness_temp_i5,
                       confidence, acquisition_timestamp, hours_old
                FROM VIIRS_Thermal_Records
                WHERE frp_mw >= {min_frp}
                AND hours_old <= {hours}
                ORDER BY frp_mw DESC
                LIMIT {limit}
            """
            
            results = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]
            
            output = format_results(results, columns)
            return [TextContent(text=output)]
        
        elif name == "get_fire_statistics":
            hours = arguments.get("time_period_hours", 24)
            
            query = f"""
                SELECT 
                    COUNT(*) as total_detections,
                    AVG(frp_mw) as avg_frp,
                    MAX(frp_mw) as max_frp,
                    MIN(frp_mw) as min_frp,
                    AVG(brightness_temp_i4) as avg_brightness,
                    COUNT(CASE WHEN confidence = 'nominal' THEN 1 END) as nominal_confidence,
                    COUNT(CASE WHEN confidence = 'low' THEN 1 END) as low_confidence,
                    COUNT(CASE WHEN day_night = 'D' THEN 1 END) as day_detections,
                    COUNT(CASE WHEN day_night = 'N' THEN 1 END) as night_detections
                FROM VIIRS_Thermal_Records
                WHERE hours_old <= {hours}
            """
            
            results = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]
            
            output = ["=== FIRE DETECTION STATISTICS ===\n"]
            output.append(f"Time Period: Last {hours} hours\n")
            
            if results and results[0]:
                row = results[0]
                for col, val in zip(columns, row):
                    output.append(f"{col}: {val}")
            
            return [TextContent(text="\n".join(output))]
        
        elif name == "query_fires_by_date":
            start_date = arguments["start_date"]
            end_date = arguments.get("end_date", start_date)
            confidence = arguments.get("confidence", "all")
            limit = arguments.get("limit", 100)
            
            query = f"""
                SELECT latitude, longitude, brightness_temp_i4, frp_mw, confidence,
                       acquisition_timestamp, hours_old, satellite
                FROM VIIRS_Thermal_Records
                WHERE DATE(acquisition_timestamp) BETWEEN '{start_date}' AND '{end_date}'
            """
            
            if confidence != "all":
                query += f" AND confidence = '{confidence}'"
            
            query += f" ORDER BY acquisition_timestamp DESC LIMIT {limit}"
            
            results = conn.execute(query).fetchall()
            columns = [desc[0] for desc in conn.description]
            
            output = format_results(results, columns)
            return [TextContent(text=output)]
        
        elif name == "execute_custom_query":
            sql = arguments["sql"].strip()
            if not sql.upper().startswith("SELECT"):
                return [TextContent(text="Error: Only SELECT queries are allowed for security reasons.")]

            results = conn.execute(sql).fetchall()
            columns = [desc[0] for desc in conn.description]

            output = format_results(results, columns)
            return [TextContent(text=output)]
        
        # GHG EMISSIONS TOOLS
        elif name == "calculate_fire_ghg_emissions":
            frp = arguments["frp"]
            hours_old = arguments["hours_old"]
            
            emissions = calculate_ghg_emissions(frp, hours_old)
            
            output = [
                "=== GHG EMISSIONS CALCULATION ===\n",
                f"Fire Radiative Power: {emissions['frp_mw']} MW",
                f"Duration: {emissions['duration_hours']} hours",
                f"Total Energy Released: {emissions['total_energy_mj']:,.2f} MJ\n",
                "--- Emissions by Gas ---",
                f"CO2 (Carbon Dioxide): {emissions['co2_kg']:,.2f} kg",
                f"CH4 (Methane): {emissions['ch4_kg']:.4f} kg",
                f"N2O (Nitrous Oxide): {emissions['n2o_kg']:.4f} kg",
                f"CO (Carbon Monoxide): {emissions['co_kg']:,.2f} kg\n",
                "--- CO2 Equivalent (100-year GWP) ---",
                f"Total CO2e: {emissions['total_co2e_kg']:,.2f} kg ({emissions['total_co2e_tonnes']:.4f} tonnes)",
                f"\nNote: Calculations based on Wooster et al. (2005) emission factors"
            ]
            
            return [TextContent(text="\n".join(output))]
        
        elif name == "calculate_ghg_emissions_by_location":
            min_lat = arguments["min_lat"]
            max_lat = arguments["max_lat"]
            min_lon = arguments["min_lon"]
            max_lon = arguments["max_lon"]
            start_date = arguments.get("start_date")
            end_date = arguments.get("end_date")
            
            query = f"""
                SELECT frp_mw, hours_old, latitude, longitude, acquisition_timestamp
                FROM VIIRS_Thermal_Records
                WHERE latitude BETWEEN {min_lat} AND {max_lat}
                AND longitude BETWEEN {min_lon} AND {max_lon}
                AND frp_mw IS NOT NULL
                AND hours_old IS NOT NULL
            """
            
            if start_date:
                query += f" AND DATE(acquisition_timestamp) >= '{start_date}'"
            if end_date:
                query += f" AND DATE(acquisition_timestamp) <= '{end_date}'"
            
            results = conn.execute(query).fetchall()
            
            if not results:
                return [TextContent(text="No fire records found in the specified area.")]
            
            total_co2 = 0
            total_ch4 = 0
            total_n2o = 0
            total_co = 0
            total_co2e = 0
            total_energy = 0
            
            for row in results:
                frp, hours_old = row[0], row[1]
                emissions = calculate_ghg_emissions(frp, hours_old)
                total_co2 += emissions['co2_kg']
                total_ch4 += emissions['ch4_kg']
                total_n2o += emissions['n2o_kg']
                total_co += emissions['co_kg']
                total_co2e += emissions['total_co2e_kg']
                total_energy += emissions['total_energy_mj']
            
            output = [
                "=== REGIONAL GHG EMISSIONS SUMMARY ===\n",
                f"Geographic Bounds:",
                f"  Latitude: {min_lat}° to {max_lat}°",
                f"  Longitude: {min_lon}° to {max_lon}°",
                f"Number of Fire Detections: {len(results)}",
                f"Total Energy Released: {total_energy:,.2f} MJ\n",
                "--- Total Emissions ---",
                f"CO2: {total_co2:,.2f} kg ({total_co2/1000:.2f} tonnes)",
                f"CH4: {total_ch4:,.2f} kg ({total_ch4/1000:.4f} tonnes)",
                f"N2O: {total_n2o:,.2f} kg ({total_n2o/1000:.4f} tonnes)",
                f"CO: {total_co:,.2f} kg ({total_co/1000:.2f} tonnes)\n",
                "--- Total CO2 Equivalent ---",
                f"Total CO2e: {total_co2e:,.2f} kg ({total_co2e/1000:.2f} tonnes)",
                f"\nAverage per fire: {total_co2e/len(results):.2f} kg CO2e"
            ]
            
            return [TextContent(text="\n".join(output))]
        
        elif name == "calculate_ghg_emissions_by_place":
            place_name = arguments["place_name"]
            buffer_deg = arguments.get("buffer_deg", 0.5)
            days_back = arguments.get("days_back", 7)
            
            bbox = get_bounding_box(place_name, buffer_deg)
            if bbox is None:
                return [TextContent(type="text", text=f"Could not resolve location '{place_name}'.")]
            
            min_lat, max_lat, min_lon, max_lon = bbox
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            query = f"""
                SELECT frp_mw, hours_old, latitude, longitude, acquisition_timestamp
                FROM VIIRS_Thermal_Records
                WHERE latitude BETWEEN {min_lat} AND {max_lat}
                AND longitude BETWEEN {min_lon} AND {max_lon}
                AND frp_mw IS NOT NULL
                AND hours_old IS NOT NULL
                AND acquisition_timestamp >= '{start_date.strftime('%Y-%m-%d')}'
            """
            
            results = conn.execute(query).fetchall()
            
            if not results:
                return [TextContent(type="text", text=f"No fire records found near '{place_name}' in the last {days_back} days.")]
            
            total_co2 = 0
            total_ch4 = 0
            total_n2o = 0
            total_co = 0
            total_co2e = 0
            total_energy = 0
            
            for row in results:
                frp, hours_old = row[0], row[1]
                emissions = calculate_ghg_emissions(frp, hours_old)
                total_co2 += emissions['co2_kg']
                total_ch4 += emissions['ch4_kg']
                total_n2o += emissions['n2o_kg']
                total_co += emissions['co_kg']
                total_co2e += emissions['total_co2e_kg']
                total_energy += emissions['total_energy_mj']
            
            output = [
                f"=== GHG EMISSIONS FOR {place_name.upper()} ===\n",
                f"Location: {place_name}",
                f"Center: {(min_lat+max_lat)/2:.4f}°, {(min_lon+max_lon)/2:.4f}°",
                f"Search Radius: ±{buffer_deg}°",
                f"Time Period: Last {days_back} days",
                f"Number of Fire Detections: {len(results)}",
                f"Total Energy Released: {total_energy:,.2f} MJ\n",
                "--- Total Emissions ---",
                f"CO2: {total_co2:,.2f} kg ({total_co2/1000:.2f} tonnes)",
                f"CH4: {total_ch4:,.2f} kg ({total_ch4/1000:.4f} tonnes)",
                f"N2O: {total_n2o:,.2f} kg ({total_n2o/1000:.4f} tonnes)",
                f"CO: {total_co:,.2f} kg ({total_co/1000:.2f} tonnes)\n",
                "--- Total CO2 Equivalent ---",
                f"Total CO2e: {total_co2e:,.2f} kg ({total_co2e/1000:.2f} tonnes)",
                f"\nAverage per fire: {total_co2e/len(results):.2f} kg CO2e"
            ]
            
            return [TextContent("\n".join(output))]
        
        elif name == "get_ghg_emissions_summary":
            hours = arguments.get("time_period_hours", 24)
            
            query = f"""
                SELECT frp_mw, hours_old
                FROM VIIRS_Thermal_Records
                WHERE hours_old <= {hours}
                AND frp_mw IS NOT NULL
                AND hours_old IS NOT NULL
            """
            
            results = conn.execute(query).fetchall()
            
            if not results:
                return [TextContent(type="text", text=f"No fire records found in the last {hours} hours.")]
            
            total_co2 = 0
            total_ch4 = 0
            total_n2o = 0
            total_co = 0
            total_co2e = 0
            total_energy = 0
            
            for row in results:
                frp, hours_old = row[0], row[1]
                emissions = calculate_ghg_emissions(frp, hours_old)
                total_co2 += emissions['co2_kg']
                total_ch4 += emissions['ch4_kg']
                total_n2o += emissions['n2o_kg']
                total_co += emissions['co_kg']
                total_co2e += emissions['total_co2e_kg']
                total_energy += emissions['total_energy_mj']
            
            output = [
                "=== GHG EMISSIONS SUMMARY ===\n",
                f"Time Period: Last {hours} hours",
                f"Number of Fires: {len(results)}",
                f"Total Energy Released: {total_energy:,.2f} MJ\n",
                "--- Total Emissions ---",
                f"CO2: {total_co2:,.2f} kg ({total_co2/1000:.2f} tonnes)",
                f"CH4: {total_ch4:,.2f} kg ({total_ch4/1000:.4f} tonnes)",
                f"N2O: {total_n2o:,.2f} kg ({total_n2o/1000:.4f} tonnes)",
                f"CO: {total_co:,.2f} kg ({total_co/1000:.2f} tonnes)\n",
                "--- Total CO2 Equivalent ---",
                f"Total CO2e: {total_co2e:,.2f} kg ({total_co2e/1000:.2f} tonnes)",
                f"\nAverage per fire: {total_co2e/len(results):.2f} kg CO2e"
            ]
            
            return [TextContent(type="text", text="\n".join(output))]
        
        else:
            return [TextContent(text=f"Unknown tool: {name}")]
    
    except Exception as e:
        print(f"ERROR in call_tool('{name}'): {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        return [TextContent(text=f"Error executing query: {str(e)}")]

    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            print("WARNING: failed to close DB connection", file=sys.stderr)
            sys.stderr.flush()

async def main():
    """Run the MCP server"""
    try:
        print("Initializing MCP server stdio...", file=sys.stderr)
        sys.stderr.flush()

        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            print("MCP server streams created, starting server...", file=sys.stderr)
            sys.stderr.flush()

            try:
                init_opts = app.create_initialization_options()
            except Exception as e:
                init_opts = None
                print(f"DEBUG: Failed to create initialization options: {e}", file=sys.stderr)
            print(f"DEBUG: initialization options: {init_opts}", file=sys.stderr)
            sys.stderr.flush()

            print("DEBUG: calling app.run()", file=sys.stderr)
            sys.stderr.flush()
            try:
                await app.run(read_stream, write_stream, init_opts)
                print("DEBUG: app.run() returned normally", file=sys.stderr)
                sys.stderr.flush()
            except Exception as e:
                print(f"ERROR: app.run() raised an exception: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                sys.stderr.flush()
                raise
    except Exception as e:
        print(f"ERROR in main: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise

if __name__ == "__main__":
    try:
        print("DEBUG: Attempting to run app.run_stdio_async()", file=sys.stderr)
        sys.stderr.flush()
        asyncio.run(app.run_stdio_async())
    except AttributeError:
        try:
            print("DEBUG: run_stdio_async not available, falling back to main()", file=sys.stderr)
            sys.stderr.flush()
            asyncio.run(main())
        except Exception as e:
            print(f"FATAL ERROR in fallback run: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            sys.exit(1)
    except Exception as e:
        print(f"FATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)


