#!/bin/bash

# Set paths
SCRIPT_DIR="./Source/Database"
LOG_FILE="/var/TeamPipeline/Logs/viirs_etl.log"

# Activate virtual environment
source ./.venv/bin/activate

# Run the ETL script
cd $SCRIPT_DIR
python viirs_thermal_etl_script_checks.py >> $LOG_FILE 2>&1


# Add timestamp

echo "ETL completed at $(date)" >> $LOG_FILE




