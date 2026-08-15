# GMU_DAEN_2025_02_D

# Development Helpers

**Running Python Scripts in uv:**
uv venv  
uv pip sync pyproject.toml
uv pip compile pyproject.toml > requirements.lock.txt
uv pip install --requirement requirements.lock.txt
source .venv/bin/activate  
python yourcodehere.py  
deactivate  

**Manual Sync to Git**
cd /srv/github/GMU_DAEN_2025_02_D  
git pull origin main  

_If you're updating the server's git and hit permissions errors, you may need to run:_  
sudo chown -R youruser /srv/github/GMU_DAEN_2025_02_D  

# Climate GPT Pipeline Team Server and Github Folder Structure

- **Server Files**
  - viirs_database
    - VIIRS_Thermal_Database.duckdb
  - aqueduct_raw_data
    - Aqueduct40_baseline_annual_y2023m07d05.csv
    - Aqueduct40_baseline_monthly_y2023m07d05.csv
    - Aqueduct40_future_annual_y2023m07d05.csv
  - aqueduct_preprocessed
    - baseline_annual_cleaned.csv
    - Aqueduct_monthly_cleaned.csv
    - aqueduct_future_annual_cleaned.csv
  - aqueduct_db
    - Aqueduct_40_Database.duckdb

- **GMU_DAEN_2025_02_D/** - Github Structure
  - README.md  
  - pyproject.toml  
  - requirements.txt  
  - .gitignore  
  - .venv/
  - **EDA Notebooks/**
    - Thermal_Hotspots_Fire_Activity.ipynb
    - Baseline_preprocessing_annual.ipynb
    - Aqueduct_preprocessing_monthly.ipynb
    - Aqueduct_preprocessing_future_annual.ipynb
  - **MCP/**
    - VIIRS_Thermal_MCP_Server.py
    - Aqueduct_40_MCP_Server.py 
  - **Scripts/**
    - Aqueduct_Preprocessing_Future_Annual.py
    - Aqueduct_Preprocessing_Monthly.py
    - Aqueduct_Preprocessing_Annual.py
  - **Source/**
    - __init__.py  
    - **database/**
      - viirs_thermal_etl_script.py  
      - DuckDB_Aqueduct_Data_loader.py  
      - duckdb_utils.py — This is where our MCP tools will live   
  - **tests/**
    - VIIRS_Thermal_Validation_queries.py — Example SQL pulls  
    - test_aqueduct.py — Example SQL pulls  
  - **Docs/** — This is where we point MCP tools to for metadata  
    - Satellite _(VIIRS)_Thermal_Hotspots_and_Fire_Activity.md  - Created from VIIRS data webpage
    - data_dictionary_country-rankings.md — Pulled from Aqueduct Data Dictionary  
    - data_dictionary_water-risk-atlas.md — Pulled from Aqueduct Data Dictionary  

