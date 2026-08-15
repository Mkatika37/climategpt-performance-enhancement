import duckdb

# --- Connect to your DuckDB file ---
DB_PATH = r"C:\Users\ASUS\GMU_DAEN_2025_02_D\Source\Database\VIIRS_Thermal_Database.duckdb"
conn = duckdb.connect(DB_PATH, read_only=True)

# ---------- Helper functions ----------
def count_in_last(interval_literal: str) -> int:
    """Count detections in the last X time (e.g., '24 hours', '7 days')."""
    return conn.execute(f"""
        SELECT COUNT(*) 
        FROM VIIRS_Thermal_Records
        WHERE acquisition_timestamp >= now() - INTERVAL '{interval_literal}'
    """).fetchone()[0]

def count_frp_over(threshold: float) -> int:
    """Count detections with Fire Radiative Power greater than threshold (MW)."""
    return conn.execute(f"""
        SELECT COUNT(*)
        FROM VIIRS_Thermal_Records
        WHERE frp_mw IS NOT NULL AND frp_mw > {threshold}
    """).fetchone()[0]

def count_confidence_in_last(conf_level: str, interval_literal: str) -> int:
    """Count detections by confidence (e.g., 'high', 'nominal') within time range."""
    return conn.execute(f"""
        SELECT COUNT(*)
        FROM VIIRS_Thermal_Records
        WHERE confidence = '{conf_level}'
          AND acquisition_timestamp >= now() - INTERVAL '{interval_literal}'
    """).fetchone()[0]

def count_on_date(date_literal: str) -> int:
    """Count detections on a specific date (YYYY-MM-DD)."""
    return conn.execute(f"""
        SELECT COUNT(*)
        FROM VIIRS_Thermal_Records
        WHERE DATE(acquisition_timestamp) = DATE '{date_literal}'
    """).fetchone()[0]

def count_between_dates(start_date: str, end_date: str) -> int:
    """Count detections between two dates (inclusive)."""
    return conn.execute(f"""
        SELECT COUNT(*)
        FROM VIIRS_Thermal_Records
        WHERE DATE(acquisition_timestamp) BETWEEN DATE '{start_date}' AND DATE '{end_date}'
    """).fetchone()[0]


# ---------- Time-window counts ----------
print("\n=== Time-window fire detection counts ===")
print("How many fires VIIRS fire detections from the last 7 days:", count_in_last('7 days'))
print("How many fire detections from the last 24 hours:", count_in_last('24 hours'))
print("How many fires detected in the last 48 hours:", count_in_last('48 hours'))
print("How many fires from the last 3 days:", count_in_last('3 days'))
print("What are the number of fire detections from the last 12 hours:", count_in_last('12 hours'))
print("How many fires from the last 72 hours:", count_in_last('72 hours'))
print("How many fire activity in the last 5 days:", count_in_last('5 days'))
print("What are the number of fires detected in the last 36 hours:", count_in_last('36 hours'))
print("How many fires from the last 2 weeks:", count_in_last('14 days'))
print("What are the number of fire detections from the last 6 hours:", count_in_last('6 hours'))

# ---------- FRP threshold counts ----------
print("\n=== FRP threshold counts (entire dataset) ===")
print("How many fires with FRP greater than 20 MW:", count_frp_over(20))
print("How many high-intensity fires with FRP above 50 MW:", count_frp_over(50))
print("How many fires with Fire Radiative Power exceeding 30 MW:", count_frp_over(30))
print("How many extremely intense fires with FRP over 100 MW:", count_frp_over(100))
print("What are the number of fires with FRP greater than 40 MW:", count_frp_over(40))
print("What are the number of fires with Fire Radiative Power above 60 MW:", count_frp_over(60))
print("How many fires with FRP exceeding 25 MW:", count_frp_over(25))
print("How many fires with FRP greater than 75 MW:", count_frp_over(75))
print("What are the number of high-intensity fires with FRP above 35 MW:", count_frp_over(35))
print("What are the number of fires with Fire Radiative Power over 45 MW:", count_frp_over(45))

# ---------- Confidence + time-window counts ----------
print("\n=== Confidence-based detections ===")
print("How many high-confidence fire detections from the last 24 hours:", count_confidence_in_last('high', '24 hours'))
print("How many nominal confidence fires from the last 48 hours:", count_confidence_in_last('nominal', '48 hours'))
print("How many high-confidence fires from the last week:", count_confidence_in_last('high', '7 days'))
print("How many nominal confidence detections from the last 3 days:", count_confidence_in_last('nominal', '3 days'))
print("How many high-confidence fires in the last 72 hours:", count_confidence_in_last('high', '72 hours'))
print("How many nominal confidence fires from the last 12 hours:", count_confidence_in_last('nominal', '12 hours'))
print("How many high-confidence fire detections from the last 5 days:", count_confidence_in_last('high', '5 days'))
print("How many nominal confidence fires from the last 36 hours:", count_confidence_in_last('nominal', '36 hours'))
print("How many high-confidence fires from the last 2 days:", count_confidence_in_last('high', '2 days'))
print("How many nominal confidence detections from the last 6 hours:", count_confidence_in_last('nominal', '6 hours'))

# ---------- Date-specific counts (UPDATED) ----------
print("\n=== Date-based fire detection counts (UPDATED) ===")
print("How many fires detected on 2025-10-18:", count_on_date('2025-10-18'))
print("How many fires detected on 2025-10-19:", count_on_date('2025-10-19'))
print("How many fires detected on 2025-10-20:", count_on_date('2025-10-20'))
print("How many fires detected on 2025-10-21:", count_on_date('2025-10-21'))
print("How many fires detected on 2025-10-22:", count_on_date('2025-10-22'))
print("How many fires detected on 2025-10-23:", count_on_date('2025-10-23'))
print("How many fires detected on 2025-10-24:", count_on_date('2025-10-24'))
print("How many fires detected between 2025-10-18 to 2025-10-20:", count_between_dates('2025-10-18', '2025-10-20'))
print("How many fires detected between 2025-10-20 to 2025-10-22:", count_between_dates('2025-10-20', '2025-10-22'))
print("How many fires detected between 2025-10-18 to 2025-10-24:", count_between_dates('2025-10-18', '2025-10-24'))

# ---------- Close connection ----------
conn.close()

