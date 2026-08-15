#!/bin/bash
# Start both HTTP adapters on the OpenStack server
# Run this on the OpenStack server via SSH

set -e

echo "=========================================="
echo "HTTP Adapters Startup Script"
echo "=========================================="
echo ""

# Step 1: Kill any existing adapter processes
echo "[1/3] Checking for existing adapter processes..."
VIIRS_PIDS=$(pgrep -f "viirs_http_adapter_v2.py" || true)
AQUEDUCT_PIDS=$(pgrep -f "aqueduct_http_adapter_v2.py" || true)

if [ -n "$VIIRS_PIDS" ]; then
    echo "  → Stopping existing VIIRS adapter (PIDs: $VIIRS_PIDS)"
    kill $VIIRS_PIDS 2>/dev/null || true
    sleep 1
fi

if [ -n "$AQUEDUCT_PIDS" ]; then
    echo "  → Stopping existing Aqueduct adapter (PIDs: $AQUEDUCT_PIDS)"
    kill $AQUEDUCT_PIDS 2>/dev/null || true
    sleep 1
fi

# Check if ports are still in use and force kill if needed
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  → Port 8000 still in use, force killing..."
    kill -9 $(lsof -ti:8000) 2>/dev/null || true
    sleep 1
fi

if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  → Port 8001 still in use, force killing..."
    kill -9 $(lsof -ti:8001) 2>/dev/null || true
    sleep 1
fi

echo "  ✓ Ports 8000 and 8001 are now available"
echo ""

# Step 2: Setup environment
echo "[2/3] Setting up environment..."

# Navigate to project directory
cd /srv/github/GMU_DAEN_2025_02_D

# Activate virtual environment
source .venv/bin/activate

# Set database path for VIIRS
export VIIRS_DUCKDB_PATH=/srv/viirs_database/VIIRS_Thermal_Database.duckdb

# Navigate to Webapp directory
cd Source/Webapp

# Install flask-cors if not already installed
pip install flask-cors 2>/dev/null || true

echo "  ✓ Environment ready"
echo ""

# Step 3: Start adapters
echo "[3/3] Starting HTTP adapters..."

# Start both adapters in the background
python viirs_http_adapter_v2.py --host 0.0.0.0 --port 8000 &
VIIRS_PID=$!

python aqueduct_http_adapter_v2.py --host 0.0.0.0 --port 8001 &
AQUEDUCT_PID=$!

echo "  ✓ VIIRS HTTP adapter started (PID: $VIIRS_PID)"
echo "  ✓ Aqueduct HTTP adapter started (PID: $AQUEDUCT_PID)"
echo ""
echo "=========================================="
echo "HTTP Adapters Running"
echo "=========================================="
echo "  VIIRS:    http://YOUR_SERVER_IP:8000"
echo "  Aqueduct: http://YOUR_SERVER_IP:8001"
echo ""
echo "  SSH Tunnel Command (run on local machine):"
echo "  ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_USERNAME@YOUR_SERVER_IP -N"
echo ""
echo "Press Ctrl+C to stop both servers"
echo "=========================================="

# Function to kill both processes on exit
cleanup() {
    echo ""
    echo "Stopping HTTP adapters..."
    kill $VIIRS_PID 2>/dev/null || true
    kill $AQUEDUCT_PID 2>/dev/null || true
    echo "Stopped"
    exit 0
}

# Register cleanup function
trap cleanup SIGINT SIGTERM

# Wait for both processes
wait

