#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Validation script: Counts of VIIRS fires near different countries (no time filters)

• Uses DuckDB database: VIIRS_Thermal_Database.duckdb
• Table: VIIRS_Thermal_Records
• Columns: latitude, longitude, frp_mw, brightness_temp_i4, brightness_temp_i5, acquisition_timestamp, confidence, satellite
• Default buffer: ±5° around each country centroid
• Outputs direct counts for single-country and comparison prompts
"""

import duckdb
from geopy.geocoders import Nominatim
from typing import Tuple, Optional

# ====================================
# CONFIGURATION
# ====================================
DB_PATH = r"C:\Users\ASUS\GMU_DAEN_2025_02_D\Source\Database\VIIRS_Thermal_Database.duckdb"
TABLE = "VIIRS_Thermal_Records"
DEFAULT_BUFFER = 5.0  # degrees around country center
COL_LAT, COL_LON = "latitude", "longitude"

# Initialize geocoder
_geocoder = Nominatim(user_agent="viirs-country-validation")

# ====================================
# GEO HELPERS
# ====================================
def geocode_center(place: str) -> Optional[Tuple[float, float]]:
    """Get approximate (lat, lon) for a country."""
    loc = _geocoder.geocode(place)
    if not loc:
        print(f"⚠ Could not resolve {place}")
        return None
    return (loc.latitude, loc.longitude)

def bbox_from_center(lat: float, lon: float, buffer_deg: float = DEFAULT_BUFFER):
    """Return (min_lat, max_lat, min_lon, max_lon) for a given center + buffer."""
    return (lat - buffer_deg, lat + buffer_deg, lon - buffer_deg, lon + buffer_deg)

# ====================================
# DATABASE HELPERS
# ====================================
def count_fires(conn, bbox) -> int:
    """Return fire count in given lat/lon bounding box."""
    min_lat, max_lat, min_lon, max_lon = bbox
    sql = f"""
        SELECT COUNT(*)
        FROM {TABLE}
        WHERE {COL_LAT} BETWEEN {min_lat} AND {max_lat}
          AND {COL_LON} BETWEEN {min_lon} AND {max_lon}
    """
    return conn.execute(sql).fetchone()[0]

# ====================================
# MAIN LOGIC
# ====================================
def count_near_country(conn, country: str) -> int:
    center = geocode_center(country)
    if not center:
        return -1
    bbox = bbox_from_center(*center)
    return count_fires(conn, bbox)

def compare_two_countries(conn, a: str, b: str):
    a_count = count_near_country(conn, a)
    b_count = count_near_country(conn, b)
    if a_count == -1 or b_count == -1:
        return "Geocode failed"
    if a_count > b_count:
        winner = a
    elif b_count > a_count:
        winner = b
    else:
        winner = "Equal"
    return f"{a}: {a_count}, {b}: {b_count} → Winner: {winner}"

# ====================================
# EXECUTION
# ====================================
if __name__ == "__main__":
    conn = duckdb.connect(DB_PATH, read_only=True)

    # ---- Single-country prompts ----
    countries = [
        "India", "Brazil", "Australia", "United States", "Canada", "China", "Russia",
        "Indonesia", "South Africa", "Mexico", "Argentina", "Saudi Arabia", "Spain",
        "Italy", "Turkey", "Greece", "Nigeria", "Egypt", "Kenya", "Japan", "Pakistan",
        "Iran", "Vietnam", "Thailand", "Germany", "France", "Chile", "Peru",
        "Ethiopia", "Bangladesh", "United Kingdom", "Malaysia", "Colombia",
        "Myanmar", "Sudan", "Zambia", "Madagascar", "Nepal", "Tanzania", "Poland"
    ]

    for c in countries:
        n = count_near_country(conn, c)
        if n >= 0:
            print(f"How many fires are near {c}? {n}")
        else:
            print(f"How many fires are near {c}? Could not resolve location.")

    # ---- Country comparisons ----
    comparisons = [
        ("India", "China"),
        ("Brazil", "Argentina"),
        ("Australia", "Indonesia"),
        ("United States", "Canada"),
        ("Russia", "South Africa"),
        ("Mexico", "Brazil"),
        ("Turkey", "Greece"),
        ("Nigeria", "Kenya"),
        ("Saudi Arabia", "Iran"),
        ("Spain", "Italy"),
        ("France", "Germany"),
        ("Argentina", "Chile"),
        ("India", "Indonesia"),
        ("Pakistan", "Bangladesh"),
        ("Egypt", "Sudan"),
        ("Vietnam", "Thailand"),
        ("Ethiopia", "Kenya"),
        ("United Kingdom", "France"),
        ("Nigeria", "South Africa"),
        ("Australia", "New Zealand"),
    ]

    for a, b in comparisons:
        result = compare_two_countries(conn, a, b)
        print(f"Which country has more fires — {a} or {b}? {result}")

    conn.close()

