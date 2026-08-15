import duckdb

# Database file path
DB_PATH = r"C:\Users\iruka\Aqueduct_40_Database.duckdb"

# CSV file paths
CSV_BASELINE_ANNUAL = r"C:\Users\iruka\baseline_annual_cleaned.csv"
CSV_BASELINE_MONTHLY = r"C:\Users\iruka\Aqueduct_monthly_cleaned.csv"
CSV_FUTURE_ANNUAL = r"C:\Users\iruka\aqueduct_future_annual_cleaned.csv"
# NEW: Assume lookup file is located here
CSV_REGION_LOOKUP = r"C:\Users\iruka\final_clean_region_lookup.csv" 

# ----------------------------------------------------------------------

# Connect to (or create) the DuckDB database using the local path
con = duckdb.connect(DB_PATH)

# Drop tables if they exist
con.execute("DROP TABLE IF EXISTS Baseline_Annual;")
con.execute("DROP TABLE IF EXISTS Baseline_Monthly;")
con.execute("DROP TABLE IF EXISTS Future_Annual;")
con.execute("DROP TABLE IF EXISTS Region_Lookup;") # DROP NEW LOOKUP TABLE

# Load CSVs into tables

# Baseline Annual
con.execute(f"CREATE TABLE Baseline_Annual AS SELECT * FROM read_csv_auto('{CSV_BASELINE_ANNUAL}');")

# Baseline Monthly
con.execute(f"CREATE TABLE Baseline_Monthly AS SELECT * FROM read_csv_auto('{CSV_BASELINE_MONTHLY}');")

# Future Annual
con.execute(f"CREATE TABLE Future_Annual AS SELECT * FROM read_csv_auto('{CSV_FUTURE_ANNUAL}');")

# NEW: Load Region Lookup Table (Assumes the CSV contains 'pfaf_id' and 'region_name')
con.execute(f"CREATE TABLE Region_Lookup AS SELECT * FROM read_csv_auto('{CSV_REGION_LOOKUP}');")

# Close the connection
con.close()


