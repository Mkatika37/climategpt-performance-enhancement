# start_http_adapters.sh Improvements

## What Changed

The `start_http_adapters.sh` script now **automatically cleans up old processes** before starting new HTTP adapters.

## Problem Solved

**Before:**
```
$ ./start_http_adapters.sh
Address already in use
Port 8000 is in use by another program...
```

You had to manually find and kill the old processes:
```bash
pkill -f viirs_http_adapter
pkill -f aqueduct_http_adapter
```

**After:**
The script now handles cleanup automatically! Just run:
```bash
./start_http_adapters.sh
```

## How It Works

The updated script performs **3 steps**:

### Step 1: Cleanup Existing Processes
```bash
[1/3] Checking for existing adapter processes...
  → Stopping existing VIIRS adapter (PIDs: 224153)
  → Stopping existing Aqueduct adapter (PIDs: 224312)
  ✓ Ports 8000 and 8001 are now available
```

The script:
1. Finds any running `viirs_http_adapter_v2.py` processes
2. Finds any running `aqueduct_http_adapter_v2.py` processes
3. Gracefully kills them with `kill` (SIGTERM)
4. If ports are still in use, force kills with `kill -9`
5. Waits to ensure ports are released

### Step 2: Setup Environment
```bash
[2/3] Setting up environment...
  ✓ Environment ready
```

- Activates Python virtual environment
- Sets `VIIRS_DUCKDB_PATH` environment variable
- Installs dependencies (flask-cors)

### Step 3: Start Adapters
```bash
[3/3] Starting HTTP adapters...
  ✓ VIIRS HTTP adapter started (PID: 226873)
  ✓ Aqueduct HTTP adapter started (PID: 226874)
```

Both adapters start fresh with new PIDs.

## Output

The script provides clear status output:

```
==========================================
HTTP Adapters Running
==========================================
  VIIRS:    http://YOUR_SERVER_IP:8000
  Aqueduct: http://YOUR_SERVER_IP:8001

  SSH Tunnel Command (run on local machine):
  ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_USERNAME@YOUR_SERVER_IP -N

Press Ctrl+C to stop both servers
==========================================
```

## Usage

**On OpenStack Server:**
```bash
cd ./Source/Webapp
./start_http_adapters.sh
```

**Or via SSH from local machine:**
```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP "./Source/Webapp/start_http_adapters.sh"
```

## Technical Details

### Process Detection
Uses `pgrep -f` to find processes by full command line:
```bash
VIIRS_PIDS=$(pgrep -f "viirs_http_adapter_v2.py" || true)
```

### Port Checking
Uses `lsof` to detect processes using ports 8000/8001:
```bash
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    kill -9 $(lsof -ti:8000)
fi
```

### Graceful Shutdown
First attempts graceful shutdown (SIGTERM), then force kill (SIGKILL) if needed.

## Benefits

✅ **No more "port in use" errors**
✅ **One-command restart** - just run the script
✅ **Idempotent** - safe to run multiple times
✅ **Clear status output** - see what's happening at each step
✅ **Automatic cleanup** - no orphaned processes

## Related Files

- `start_http_adapters.sh` - The startup script (updated)
- `viirs_http_adapter_v2.py` - VIIRS HTTP adapter
- `aqueduct_http_adapter_v2.py` - Aqueduct HTTP adapter
- `deploy_http_adapters.bat` - Windows deployment script

## See Also

- [HTTP_ADAPTER_SETUP.md](HTTP_ADAPTER_SETUP.md) - Complete HTTP adapter setup guide
- [QUICK_START_HTTP.md](QUICK_START_HTTP.md) - Quick start guide



