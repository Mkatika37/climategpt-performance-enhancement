#!/bin/bash

# Navigate to project root where uv is installed
cd .
source .venv/bin/activate

# Navigate to adapter folder
cd Source/Webapp

# Launch aqueduct adapter
echo "Starting aqueduct_http_adapter..."
python aqueduct_http_adapter.py &

# Launch viirs adapter
echo "Starting viirs_http_adapter..."
python viirs_http_adapter.py &

# Wait for both to finish (optional)
wait


