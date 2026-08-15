import os
from pathlib import Path
import duckdb
from pprint import pprint

# Database filename
DB_FILENAME = "VIIRS_Thermal_Database.duckdb"

# Build candidate DB locations in preferred order:
# 1) VIIRS_DUCKDB_PATH env var (file or directory)
# 2) Local test copy in Source/MCP next to the server script
# 3) Server location /srv/viirs_database
# 4) CWD
candidates = []
env_path = os.getenv("VIIRS_DUCKDB_PATH")
if env_path:
    p = Path(env_path)
    if p.is_dir():
        candidates.append(p / DB_FILENAME)
    else:
        candidates.append(p)

# local test copy in repository Source/MCP
repo_root = Path(__file__).resolve().parent.parent
local_test = repo_root / "Source" / "MCP" / DB_FILENAME
candidates.append(local_test)

# canonical server path
candidates.append(Path("/srv/viirs_database") / DB_FILENAME)

# current working directory
candidates.append(Path.cwd() / DB_FILENAME)

# pick the first existing candidate
chosen = next((p for p in candidates if p.exists()), None)
if chosen is None:
    # fallback to server path string (same as previous behavior)
    chosen = Path("/srv/viirs_database") / DB_FILENAME

print(f"Using DuckDB at: {chosen}")
conn = duckdb.connect(str(chosen))

print("DESCRIBE VIIRS_Thermal_Records:")
describe = conn.execute("DESCRIBE VIIRS_Thermal_Records").fetchall()
pprint(describe)

print(conn.execute("SELECT * FROM  VIIRS_Thermal_Records LIMIT 30").fetchdf())

print("\nRow count")
print(conn.execute("SELECT COUNT(*) FROM VIIRS_Thermal_Records").fetchone())

# Min and Max acquisition_timestamp
print("\nDate range validation")
print(conn.execute("""
    SELECT 
        MIN(acquisition_timestamp) AS min_date,
        MAX(acquisition_timestamp) AS max_date
    FROM VIIRS_Thermal_Records
""").fetchdf())

# Duplicate Check
print("\nCheck for Duplicates")
print(conn.execute("""
    SELECT *, COUNT(*) AS dup_count
    FROM VIIRS_Thermal_Records
    GROUP BY ALL
    HAVING COUNT(*) > 1
""").fetchdf())

# Fires near Los Angeles, CA
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 33.55 AND 34.55
      AND longitude BETWEEN -118.75 AND -117.75
""").fetchdf())

# Fires near Edmonton, Alberta
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 53.05 AND 54.05
      AND longitude BETWEEN -113.99 AND -112.99
""").fetchdf())

# Fires near Miami, Florida
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 25.26 AND 26.26
      AND longitude BETWEEN -80.69 AND -79.69
""").fetchdf())

# Fires near Houston, Texas
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 29.26 AND 30.26
      AND longitude BETWEEN -95.87 AND -94.87
""").fetchdf())

# Fires near Phoenix, Arizona
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 32.95 AND 33.95
      AND longitude BETWEEN -112.57 AND -111.57
""").fetchdf())

# Fires near Seattle, Washington
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 47.11 AND 48.11
      AND longitude BETWEEN -122.83 AND -121.83
""").fetchdf())

# Fires near Hamburg, Germany
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 53.05 AND 54.05
      AND longitude BETWEEN 9.50 AND 10.50
""").fetchdf())

# Fires near Denver, Colorado
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 39.24 AND 40.24
      AND longitude BETWEEN -105.49 AND -104.49
""").fetchdf())

# Fires near San Francisco, California
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 37.27 AND 38.27
      AND longitude BETWEEN -122.92 AND -121.92
""").fetchdf())

# Fires near Portland, Oregon
print(conn.execute("""
    SELECT COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN 45.02 AND 46.02
      AND longitude BETWEEN -123.18 AND -122.18
""").fetchdf())

city_coords = {
    "Nairobi": ( -1.2921, 36.8219),
    "Vancouver": (49.2827, -123.1207),
    "Jakarta": (-6.2088, 106.8456),
    "Rome": (41.9028, 12.4964),
    "Cairo": (30.0444, 31.2357),
    "Buenos Aires": (-34.6037, -58.3816),
    "Mumbai": (19.0760, 72.8777),
    "Chicago": (41.8781, -87.6298),
    "Lima": (-12.0464, -77.0428),
    "Tokyo": (35.6895, 139.6917),
    "Kinshasa": (-4.4419, 15.2663),
    "Berlin": (52.5200, 13.4050),
    "Bangkok": (13.7563, 100.5018),
    "Toronto": (43.6532, -79.3832),
    "Accra": (5.6037, -0.1870),
    "Sydney": (-33.8688, 151.2093),
    "Mexico City": (19.4326, -99.1332),
    "Moscow": (55.7558, 37.6173),
    "Tehran": (35.6892, 51.3890),
    "Cape Town": (-33.9249, 18.4241)
}

def fire_count_query(city_name, lat, lon, buffer=1.0):
    return f"""
    SELECT
        '{city_name}' AS city,
        COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN {lat - buffer} AND {lat + buffer}
      AND longitude BETWEEN {lon - buffer} AND {lon + buffer}
      AND hours_old <= 24
    """

# List of city pairs from your questions
city_pairs = [
    ("Nairobi", "Vancouver"),
    ("Jakarta", "Rome"),
    ("Cairo", "Buenos Aires"),
    ("Mumbai", "Chicago"),
    ("Lima", "Tokyo"),
    ("Kinshasa", "Berlin"),
    ("Bangkok", "Toronto"),
    ("Accra", "Sydney"),
    ("Mexico City", "Moscow"),
    ("Tehran", "Cape Town")
]

# Run and compare fire counts
for city1, city2 in city_pairs:
    lat1, lon1 = city_coords[city1]
    lat2, lon2 = city_coords[city2]
    
    query1 = fire_count_query(city1, lat1, lon1)
    query2 = fire_count_query(city2, lat2, lon2)
    
    result = conn.execute(f"{query1} UNION ALL {query2}").fetchdf()
    print(f"\n🔥 {city1} vs {city2}")
    print(result)

country_coords = {
    "India": (22.0, 78.0),
    "China": (35.0, 103.0),
    "Brazil": (-10.0, -55.0),
    "Argentina": (-34.0, -64.0),
    "Australia": (-25.0, 133.0),
    "Indonesia": (-2.0, 118.0),
    "United States": (39.0, -98.0),
    "Canada": (56.0, -106.0),
    "Russia": (60.0, 90.0),
    "South Africa": (-30.0, 25.0),
    "Mexico": (23.0, -102.0),
    "Turkey": (39.0, 35.0),
    "Greece": (39.0, 22.0),
    "Nigeria": (10.0, 8.0),
    "Kenya": (0.5, 37.5),
    "Saudi Arabia": (24.0, 45.0),
    "Iran": (32.0, 53.0),
    "Spain": (40.0, -4.0),
    "Italy": (42.0, 12.0),
    "France": (46.0, 2.0),
    "Germany": (51.0, 10.0),
    "Chile": (-33.0, -71.0),
    "Pakistan": (30.0, 70.0),
    "Bangladesh": (24.0, 90.0),
    "Egypt": (26.0, 30.0),
    "Sudan": (15.0, 30.0),
    "Vietnam": (14.0, 108.0),
    "Thailand": (15.0, 101.0),
    "Ethiopia": (9.0, 40.0),
    "United Kingdom": (54.0, -2.0),
    "New Zealand": (-41.0, 174.0)
}

def fire_count_query(country, lat, lon, buffer=5.0, hours=168):
    return f"""
    SELECT
        '{country}' AS country,
        COUNT(*) AS fire_count
    FROM VIIRS_Thermal_Records
    WHERE latitude BETWEEN {lat - buffer} AND {lat + buffer}
      AND longitude BETWEEN {lon - buffer} AND {lon + buffer}
      AND hours_old <= {hours}
    """

country_pairs = [
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
    ("Australia", "New Zealand")
]

for c1, c2 in country_pairs:
    lat1, lon1 = country_coords[c1]
    lat2, lon2 = country_coords[c2]
    
    q1 = fire_count_query(c1, lat1, lon1)
    q2 = fire_count_query(c2, lat2, lon2)
    
    result = conn.execute(f"{q1} UNION ALL {q2}").fetchdf()
    print(f"\n🔥 {c1} vs {c2}")
    print(result)

conn.close()
