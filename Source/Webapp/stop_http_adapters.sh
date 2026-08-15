#!/bin/bash
# Stop HTTP adapters on the OpenStack server

echo "=========================================="
echo "Stopping HTTP Adapters"
echo "=========================================="
echo ""

# Find and kill VIIRS adapter
VIIRS_PIDS=$(pgrep -f "viirs_http_adapter_v2.py" || true)
if [ -n "$VIIRS_PIDS" ]; then
    echo "Stopping VIIRS adapter (PIDs: $VIIRS_PIDS)..."
    kill $VIIRS_PIDS 2>/dev/null || true
    sleep 1

    # Force kill if still running
    VIIRS_PIDS=$(pgrep -f "viirs_http_adapter_v2.py" || true)
    if [ -n "$VIIRS_PIDS" ]; then
        echo "  → Force stopping VIIRS adapter..."
        kill -9 $VIIRS_PIDS 2>/dev/null || true
    fi
    echo "  ✓ VIIRS adapter stopped"
else
    echo "  ℹ VIIRS adapter not running"
fi

# Find and kill Aqueduct adapter
AQUEDUCT_PIDS=$(pgrep -f "aqueduct_http_adapter_v2.py" || true)
if [ -n "$AQUEDUCT_PIDS" ]; then
    echo "Stopping Aqueduct adapter (PIDs: $AQUEDUCT_PIDS)..."
    kill $AQUEDUCT_PIDS 2>/dev/null || true
    sleep 1

    # Force kill if still running
    AQUEDUCT_PIDS=$(pgrep -f "aqueduct_http_adapter_v2.py" || true)
    if [ -n "$AQUEDUCT_PIDS" ]; then
        echo "  → Force stopping Aqueduct adapter..."
        kill -9 $AQUEDUCT_PIDS 2>/dev/null || true
    fi
    echo "  ✓ Aqueduct adapter stopped"
else
    echo "  ℹ Aqueduct adapter not running"
fi

# Check ports are free
echo ""
echo "Checking ports..."
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  ⚠ Port 8000 still in use"
    lsof -Pi :8000 -sTCP:LISTEN
else
    echo "  ✓ Port 8000 free"
fi

if lsof -Pi :8001 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  ⚠ Port 8001 still in use"
    lsof -Pi :8001 -sTCP:LISTEN
else
    echo "  ✓ Port 8001 free"
fi

echo ""
echo "=========================================="
echo "HTTP Adapters Stopped"
echo "=========================================="



