import requests
import pandas as pd
import duckdb
import hashlib
import os
import glob
import re
from datetime import datetime, timezone, date

# RSS Feed Status URL - NEW
RSS_STATUS_URL = "https://livingatlasoftheworld.s3.amazonaws.com/MonitorPage/rss/b8f4033069f141729ffb298b7418b653.rss"

# ------------------------
# 0. RSS FEED STATUS CHECK - NEW FUNCTION
# ------------------------
def check_rss_feed_status(rss_url: str) -> bool:
    """
    Check if VIIRS RSS feed indicates the service is live.
    """
    try:
        response = requests.get(rss_url, timeout=10)
        if response.status_code == 200:
            print("RSS feed is live")
            return True
        else:
            print(f"RSS feed returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"RSS feed is down or unreachable. Error: {e}")
        return False


# ------------------------
# 1. EXTRACTION (REST API Pull)
# ------------------------
def extract_viirs_data(api_url: str) -> pd.DataFrame:
    """
    Extract VIIRS hotspots from ArcGIS REST API.
    """
    # ADDED: Pagination logic to get all records
    all_records = []
    offset = 0
    # Use a page size safely under the server maxRecordCount (server reports 16000).
    # We choose 15000 to avoid server-side caps and still fetch large chunks.
    batch_size = 15000
    
    while True:
        params = {
            "f": "json",
            "where": "1=1",
            "outFields": "*",
            "resultOffset": offset,
            "resultRecordCount": batch_size,
            # enforce a stable ordering for pagination
            "orderByFields": "OBJECTID ASC"
        }
        r = requests.get(api_url, params=params)
        r.raise_for_status()
        data = r.json()

        if "features" in data:
            records = [f["attributes"] for f in data["features"]]
        else:
            print("DEBUG unexpected response keys:", data.keys())
            raise ValueError("API response missing 'features'")
        
       
        if len(records) == 0:
            break

        all_records.extend(records)

        # Debug/logging to trace progress
        print(f"Pulled {len(records)} records (offset {offset}, batch_size {batch_size})")

        # If returned fewer than requested, we've reached the end
        if len(records) < batch_size:
            break

        # Advance offset by number of records returned (safer if server caps page size)
        offset += len(records)

    return pd.DataFrame(all_records)


# ------------------------
# 2. TRANSFORMATION
# ------------------------
def transform_viirs_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean & normalize VIIRS data for MCP compatibility.
    """
    if df.empty:
        print("  WARNING: Empty dataframe provided to transform")
        return df
    # Rename columns for clarity
    rename_map = {
        "OBJECTID": "object_id",
        "latitude": "latitude",
        "longitude": "longitude",
        "bright_ti4": "brightness_temp_i4",
        "bright_ti5": "brightness_temp_i5",
        "frp": "frp_mw",
        "acq_date": "acquisition_date",
        "acq_time": "acquisition_time",
        "confidence": "confidence",
        "satellite": "satellite",
        "daynight": "day_night"
    }
    df = df.rename(columns=rename_map)

    # Convert epoch → ISO timestamp
    def parse_datetime(row):
        try:
            ts = int(row["acquisition_time"])
            if ts > 1e12:  # epoch ms
                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            else:          # epoch s
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.isoformat()
        except Exception as e:
            print("DEBUG timestamp parse failed:", row.get("acquisition_time"), e)
            return None

    if "acquisition_time" in df.columns:
        df["acquisition_timestamp"] = df.apply(parse_datetime, axis=1)
    else:
        df["acquisition_timestamp"] = None

    # Confidence filter
    df = df[df['confidence'].isin(['nominal', 'high'])]
 

    # Remove incomplete rows
    df = df.dropna(subset=["latitude", "longitude", "acquisition_timestamp"])

 
    def generate_uid(row):
        uid_str = f"{row['latitude']}_{row['longitude']}_{row['acquisition_date']}_{row['acquisition_time']}_{row['satellite']}"
        return hashlib.md5(uid_str.encode()).hexdigest()
    df["uid"] = df.apply(generate_uid, axis=1)

    keep_cols = [
        "uid", "latitude", "longitude",
        "brightness_temp_i4", "brightness_temp_i5", "frp_mw",
        "acquisition_timestamp", "satellite", "version", "confidence", "day_night","hours_old"
    ]
    return df[[c for c in keep_cols if c in df.columns]]


# ------------------------
# 3. LOADING (DuckDB)
# ------------------------
def load_to_duckdb(df: pd.DataFrame):
    """
    Store the cleaned dataframe into DuckDB.
    """
    if df.empty:
        print("  INFO: No records to load (empty dataframe)")
        return
    
    conn = duckdb.connect("/srv/viirs_database/VIIRS_Thermal_Database.duckdb")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS VIIRS_Thermal_Records (
        uid VARCHAR,
        latitude DOUBLE,
        longitude DOUBLE,
        brightness_temp_i4 DOUBLE,
        brightness_temp_i5 DOUBLE,
        frp_mw DOUBLE,
        acquisition_timestamp TIMESTAMP,
        satellite VARCHAR,
        version VARCHAR,
        confidence VARCHAR,
        day_night VARCHAR,
        hours_old DOUBLE
    )
    """)
    existing_uids = set([row[0] for row in conn.execute("SELECT uid FROM VIIRS_Thermal_Records").fetchall()])
    df = df[~df['uid'].isin(existing_uids)]
    if not df.empty:
        conn.execute("INSERT INTO VIIRS_Thermal_Records SELECT * FROM df")
    conn.close()

def export_df_with_date(df, base_name="VIIRS_Cleaned_Data", folder_path="."):
    today_str = date.today().strftime("%Y-%m-%d")
    # If this is the VIIRS cleaned export, always save to the centralized logs dir on the server
    if base_name == "VIIRS_Cleaned_Data":
        folder_path = os.getenv("VIIRS_ETL_LOG_DIR", "/var/TeamPipeline/Logs/VIIRS_ETL")
    # Ensure output directory exists
    os.makedirs(folder_path, exist_ok=True)

    # Find existing exports for today and compute next PX number
    pattern = os.path.join(folder_path, f"{base_name}_{today_str}_P*.csv")
    existing = glob.glob(pattern)

    if not existing:
        pull_num = 1
    else:
        nums = []
        for p in existing:
            m = re.search(r"_P(\d+)\.csv$", p)
            if m:
                try:
                    nums.append(int(m.group(1)))
                except ValueError:
                    continue
        pull_num = max(nums) + 1 if nums else 1

    filename = f"{base_name}_{today_str}_P{pull_num}.csv"
    full_path = os.path.join(folder_path, filename)
    df.to_csv(full_path, index=False)
    print(f"Exported to: {full_path}")


# ------------------------
# FUNCTION CALLS
# ------------------------
if __name__ == "__main__":
    # NEW: Check RSS feed status first
    check_rss_feed_status(RSS_STATUS_URL)
    
    # API URL
    api_url = "https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/Satellite_VIIRS_Thermal_Hotspots_and_Fire_Activity/FeatureServer/0/query"
    
    #Extract
    raw_data = extract_viirs_data(api_url)
    #Transform
    clean_data = transform_viirs_data(raw_data)
    #Log
    export_df_with_date(clean_data, base_name="VIIRS_Cleaned_Data", folder_path="/srv/viirs_logs")
    #Load
    load_to_duckdb(clean_data)


