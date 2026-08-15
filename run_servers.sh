#!/bin/bash
# Navigate to project root where uv is installed
cd /srv/github/GMU_DAEN_2025_02_D
source .venv/bin/activate
# Navigate to MCP folder
cd Source/MCP
# Launch aqueduct MCP
echo "Starting aqueduct_MCP..."
nohup python Aqueduct_Server.py &
# Launch viirs MCP
echo "Starting viirs_MCP..."
nohup python viirs_mcp_server.py &
# Wait for both to finish (optional)
wait
