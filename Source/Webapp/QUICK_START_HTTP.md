# Quick Start: HTTP Adapters for MCP Servers

Get your MCP servers working with ClimateGPT in 10 minutes!

## Prerequisites

- SSH access to OpenStack server (YOUR_USERNAME@YOUR_SERVER_IP)
- SSH keys configured (passwordless login)
- Python installed on both Windows and OpenStack server
- Git Bash or Windows PowerShell

## Step-by-Step Guide

### Step 1: Deploy (2 minutes)

**On your Windows machine, from the project root:**

```bash
cd Source/Webapp
deploy_http_adapters.bat
```

This will:
- Upload HTTP adapters to OpenStack
- Install dependencies
- Make scripts executable

### Step 2: Start HTTP Adapters (1 minute)

**In a new terminal (Git Bash or PowerShell):**

```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP "./Source/Webapp/start_http_adapters.sh"
```

You should see:
```
VIIRS HTTP adapter started (PID: ...)
Aqueduct HTTP adapter started (PID: ...)
HTTP adapters running:
  VIIRS:    http://YOUR_SERVER_IP:8000
  Aqueduct: http://YOUR_SERVER_IP:8001
```

**Keep this terminal open!**

### Step 3: Create SSH Tunnels (1 minute)

**In ANOTHER new terminal:**

```bash
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_USERNAME@YOUR_SERVER_IP -N
```

**Keep this terminal open too!**

### Step 4: Test Locally (2 minutes)

**In a third terminal:**

```bash
# Test VIIRS
curl http://localhost:8000/health

# Should return: {"status":"healthy","service":"viirs-http-adapter",...}

# Test Aqueduct
curl http://localhost:8001/health

# Should return: {"status":"healthy","service":"aqueduct-http-adapter",...}
```

### Step 5: Start ClimateGPT Interface (1 minute)

**Same terminal as Step 4:**

```bash
cd Source/Webapp
set VIIRS_MCP_URL=http://localhost:8000
set AQUEDUCT_MCP_URL=http://localhost:8001
python pipeline_app_v2.py
```

(Or use `export` instead of `set` if in Git Bash)

### Step 6: Use It! (ongoing)

Open http://127.0.0.1:5000 in your browser

**Try these queries:**

1. **"What are the recent wildfires?"**
   - Should query VIIRS MCP server
   - Return fire detection data

2. **"What water risk datasets are available?"**
   - Should query Aqueduct MCP server
   - Return list of datasets

3. **"Show me fires in California and water stress in Texas"**
   - Should query BOTH MCP servers
   - Combine data in response

## What You'll See

```
┌─────────────────────┐
│  Your Browser       │
│  localhost:5000     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  pipeline_app_v2    │
│  (Flask)            │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐   ┌────────┐
│VIIRS   │   │Aqueduct│
│:8000   │   │:8001   │
└────┬───┘   └───┬────┘
     │           │
  (SSH Tunnel)   │
     │           │
     ▼           ▼
┌─────────────────────┐
│  OpenStack Server   │
│  YOUR_SERVER_IP      │
│                     │
│  ┌──────────────┐   │
│  │VIIRS Adapter │   │
│  │    :8000     │   │
│  └──────┬───────┘   │
│         │           │
│  ┌──────▼───────┐   │
│  │ VIIRS MCP    │   │
│  │   Server     │   │
│  └──────────────┘   │
│                     │
│  ┌──────────────┐   │
│  │Aqueduct      │   │
│  │ Adapter:8001 │   │
│  └──────┬───────┘   │
│         │           │
│  ┌──────▼───────┐   │
│  │ Aqueduct MCP │   │
│  │   Server     │   │
│  └──────────────┘   │
└─────────────────────┘
```

## Troubleshooting

### "Connection refused" when testing localhost:8000

**Problem:** SSH tunnel isn't running or HTTP adapters aren't started

**Fix:**
```bash
# Check if SSH tunnel is running
netstat -an | findstr "8000"

# If not, create it again
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_USERNAME@YOUR_SERVER_IP -N
```

### HTTP adapters show errors

**Problem:** Missing dependencies or database not found

**Fix:**
```bash
# SSH into server
ssh YOUR_USERNAME@YOUR_SERVER_IP

# Check VIIRS database
ls -la /srv/viirs_database/VIIRS_Thermal_Database.duckdb

# Install missing packages
cd .
source .venv/bin/activate
pip install flask flask-cors mcp
```

### ClimateGPT not returning MCP data

**Problem:** Keyword detection not working

**Fix:** Be explicit with keywords:
- Use "fire", "wildfire", "burn" for VIIRS
- Use "water", "flood", "drought" for Aqueduct

### Port already in use

**Problem:** Another process using port 8000 or 8001

**Fix:**
```bash
# On OpenStack server, find and kill the process
ssh YOUR_USERNAME@YOUR_SERVER_IP "netstat -tuln | grep 8000"
ssh YOUR_USERNAME@YOUR_SERVER_IP "pkill -f 'viirs_http_adapter'"

# Or use different ports
python viirs_http_adapter_v2.py --port 8002
```

## Stopping Everything

### Stop HTTP Adapters

In the terminal running start_http_adapters.sh, press `Ctrl+C`

### Stop SSH Tunnel

In the tunnel terminal, press `Ctrl+C`

### Stop pipeline_app_v2

In the Flask terminal, press `Ctrl+C`

## Terminal Summary

You need **3 terminals**:

1. **HTTP Adapters** (on OpenStack)
   ```
   ssh YOUR_USERNAME@YOUR_SERVER_IP ".../start_http_adapters.sh"
   ```

2. **SSH Tunnel** (on Windows)
   ```
   ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_USERNAME@YOUR_SERVER_IP -N
   ```

3. **Pipeline App** (on Windows)
   ```
   cd Source/Webapp
   python pipeline_app_v2.py
   ```

## Files Reference

| File | Purpose |
|------|---------|
| [viirs_http_adapter_v2.py](viirs_http_adapter_v2.py) | VIIRS HTTP adapter |
| [aqueduct_http_adapter_v2.py](aqueduct_http_adapter_v2.py) | Aqueduct HTTP adapter |
| [start_http_adapters.sh](start_http_adapters.sh) | Start both adapters |
| [deploy_http_adapters.bat](deploy_http_adapters.bat) | Deploy from Windows |
| [pipeline_app_v2.py](pipeline_app_v2.py) | ClimateGPT web UI |
| [HTTP_ADAPTER_SETUP.md](HTTP_ADAPTER_SETUP.md) | Detailed setup guide |

## Success Indicators

✅ **Working correctly when:**
- `curl http://localhost:8000/health` returns 200 OK
- `curl http://localhost:8001/health` returns 200 OK
- pipeline_app_v2 shows "ClimateGPT Chat UI with MCP Integration"
- Fire queries return VIIRS data
- Water queries return Aqueduct data

## Next Steps

Once working:
1. Try different queries to test both MCP servers
2. Monitor the HTTP adapter logs for errors
3. Optimize database queries if needed
4. Consider running HTTP adapters as systemd services for production

---

**Estimated Time:** 10 minutes
**Difficulty:** Easy
**Success Rate:** Very high (HTTP is reliable!)



