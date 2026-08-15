import os
import sys
import subprocess
import duckdb

# Database file path (use absolute /var paths for server)
DB_PATH = r"/var/TeamPipeline/Database/Aqueduct/Aqueduct_40_Database.duckdb"

# CSV file paths (preprocessed)
CSV_BASELINE_ANNUAL = r"/var/TeamPipeline/Preprocessed/baseline_annual_cleaned.csv"
CSV_BASELINE_MONTHLY = r"/var/TeamPipeline/Preprocessed/Aqueduct_monthly_cleaned.csv"
CSV_FUTURE_ANNUAL = r"/var/TeamPipeline/Preprocessed/aqueduct_future_annual_cleaned.csv"
CSV_REGION_LOOKUP = r"/var/TeamPipeline/Preprocessed/final_clean_region_lookup.csv"

# Preprocessing scripts location on the server (absolute path)
PREPROCESS_SCRIPTS_ROOT = "./Scripts"
PREPROCESS_SCRIPTS = [
    os.path.join(PREPROCESS_SCRIPTS_ROOT, "Aqueduct_Preprocessing_Annual.py"),
    os.path.join(PREPROCESS_SCRIPTS_ROOT, "Aqueduct_Preprocessing_Monthly.py"),
    os.path.join(PREPROCESS_SCRIPTS_ROOT, "Aqueduct_Preprocessing_Future_Annual.py"),
    os.path.join(PREPROCESS_SCRIPTS_ROOT, "lookuptable.py"),
]


def run_preprocessing_scripts():
	"""Invoke the repository preprocessing scripts which read raw files and write preprocessed CSVs.

	The scripts are expected to read from /var/TeamPipeline/Raw and write to /var/TeamPipeline/Preprocessed
	(they already use those paths). We call them here to ensure the preprocessed CSVs exist before loading.
	"""
	env = os.environ.copy()
	# Provide canonical env names (absolute /var paths used on the server)
	env.setdefault("AQUEDUCT_RAW_DIR", "/var/TeamPipeline/Raw")
	env.setdefault("AQUEDUCT_PREP_DIR", "/var/TeamPipeline/Preprocessed")

	for script in PREPROCESS_SCRIPTS:
		if not os.path.exists(script):
			print(f"Preprocessing script not found, skipping: {script}")
			continue
		print(f"Running preprocessing script: {script}")
		try:
			subprocess.run([sys.executable, script], check=True, env=env)
		except subprocess.CalledProcessError as e:
			print(f"Preprocessing script failed: {script}  exit={e.returncode}")


def load_csvs_into_duckdb():
	"""Load the preprocessed CSVs into DuckDB (drop & recreate tables)."""
	# Ensure DB directory exists
	db_dir = os.path.dirname(DB_PATH)
	if db_dir and not os.path.exists(db_dir):
		os.makedirs(db_dir, exist_ok=True)

	con = duckdb.connect(DB_PATH)

	# Drop tables if they exist
	con.execute("DROP TABLE IF EXISTS Baseline_Annual;")
	con.execute("DROP TABLE IF EXISTS Baseline_Monthly;")
	con.execute("DROP TABLE IF EXISTS Future_Annual;")
	con.execute("DROP TABLE IF EXISTS Region_Lookup;")

	# Load CSVs into tables if present
	if os.path.exists(CSV_BASELINE_ANNUAL):
		print(f"Creating Baseline_Annual from {CSV_BASELINE_ANNUAL}")
		con.execute(f"CREATE TABLE Baseline_Annual AS SELECT * FROM read_csv_auto('{CSV_BASELINE_ANNUAL}');")
	else:
		print(f"Preprocessed baseline annual CSV not found: {CSV_BASELINE_ANNUAL}")

	if os.path.exists(CSV_BASELINE_MONTHLY):
		print(f"Creating Baseline_Monthly from {CSV_BASELINE_MONTHLY}")
		con.execute(f"CREATE TABLE Baseline_Monthly AS SELECT * FROM read_csv_auto('{CSV_BASELINE_MONTHLY}');")
	else:
		print(f"Preprocessed baseline monthly CSV not found: {CSV_BASELINE_MONTHLY}")

	if os.path.exists(CSV_FUTURE_ANNUAL):
		print(f"Creating Future_Annual from {CSV_FUTURE_ANNUAL}")
		con.execute(f"CREATE TABLE Future_Annual AS SELECT * FROM read_csv_auto('{CSV_FUTURE_ANNUAL}');")
	else:
		print(f"Preprocessed future annual CSV not found: {CSV_FUTURE_ANNUAL}")

	# Optional Region Lookup
	if os.path.exists(CSV_REGION_LOOKUP):
		print(f"Creating Region_Lookup from {CSV_REGION_LOOKUP}")
		con.execute(f"CREATE TABLE Region_Lookup AS SELECT * FROM read_csv_auto('{CSV_REGION_LOOKUP}');")
	else:
		print(f"Region_Lookup CSV not found at {CSV_REGION_LOOKUP}; skipping")

	con.close()


if __name__ == "__main__":
	# Run preprocessors to ensure fresh preprocessed CSVs are available
	run_preprocessing_scripts()
	# Then load into DuckDB
	load_csvs_into_duckdb()


