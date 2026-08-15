# HTTP Adapter Setup for MCP Servers

This guide will help you set up HTTP adapters for the VIIRS and Aqueduct MCP servers, enabling reliable communication with Claude Desktop.

## Why HTTP Adapters?

- ✅ **More reliable** than stdio over SSH
- ✅ **Easy to debug** with curl and browser
- ✅ **Better error messages** via HTTP status codes
- ✅ **Claude Desktop supports it** via HTTP/SSE transport
- ✅ **Can test independently** before integrating with Claude

## Architecture

```
Claude Desktop (Windows)
    ↓ HTTP over SSH tunnel
    ↓
SSH Tunnel (localhost:8000, localhost:8001)
    ↓
OpenStack Server (YOUR_SERVER_IP)
    ├─→ VIIRS HTTP Adapter :8000
    │       ↓
    │   viirs_mcp_server.py
    │       ↓
    │   VIIRS DuckDB Database
    │
    └─→ Aqueduct HTTP Adapter :8001
            ↓
        Aqueduct_Server.py
            ↓
        Aqueduct DuckDB Database
```

## Step 1: Deploy HTTP Adapters to OpenStack

### Upload the new adapters:

```bash
scp Source/Webapp/viirs_http_adapter_v2.py YOUR_USERNAME@YOUR_SERVER_IP:./Source/Webapp/
scp Source/Webapp/aqueduct_http_adapter_v2.py YOUR_USERNAME@YOUR_SERVER_IP:./Source/Webapp/
scp Source/Webapp/start_http_adapters.sh YOUR_USERNAME@YOUR_SERVER_IP:./Source/Webapp/
```

### Make the start script executable:

```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP "chmod +x ./Source/Webapp/start_http_adapters.sh"
```

## Step 2: Start HTTP Adapters on OpenStack

### Option A: Using the start script (Recommended)

```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP "./Source/Webapp/start_http_adapters.sh"
```

This starts both adapters in one command!

### Option B: Manual start (for testing/debugging)

```bash
# Terminal 1 - VIIRS
ssh YOUR_USERNAME@YOUR_SERVER_IP
cd .
source .venv/bin/activate
export VIIRS_DUCKDB_PATH=/srv/viirs_database/VIIRS_Thermal_Database.duckdb
cd Source/Webapp
python viirs_http_adapter_v2.py --host 0.0.0.0 --port 8000

# Terminal 2 - Aqueduct
ssh YOUR_USERNAME@YOUR_SERVER_IP
cd .
source .venv/bin/activate
cd Source/Webapp
python aqueduct_http_adapter_v2.py --host 0.0.0.0 --port 8001
```

## Step 3: Install flask-cors on Server

The adapters need `flask-cors` for CORS support:

```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP "cd . && source .venv/bin/activate && pip install flask-cors"
```

## Step 4: Test HTTP Adapters

### From your Windows machine:

```bash
# Test VIIRS health
ssh YOUR_USERNAME@YOUR_SERVER_IP "curl http://localhost:8000/health"

# Test Aqueduct health
ssh YOUR_USERNAME@YOUR_SERVER_IP "curl http://localhost:8001/health"

# Test VIIRS tool call
ssh YOUR_USERNAME@YOUR_SERVER_IP 'curl -X POST http://localhost:8000/mcp/call_tool -H "Content-Type: application/json" -d "{\"tool\": \"describe_viirs_dataset\", \"arguments\": {}}"'

# Test Aqueduct tool call
ssh YOUR_USERNAME@YOUR_SERVER_IP 'curl -X POST http://localhost:8001/mcp/call_tool -H "Content-Type: application/json" -d "{\"tool\": \"list_datasets\", \"arguments\": {}}"'
```

Expected responses:
- Health checks should return `{"status": "healthy", ...}`
- Tool calls should return `{"tool": "...", "result": ...}`

## Step 5: Create SSH Tunnels

In a **separate terminal** on your Windows machine, create SSH tunnels:

```bash
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_USERNAME@YOUR_SERVER_IP -N
```

**Important:** Leave this terminal running! The `-N` flag means "don't execute a command, just tunnel".

## Step 6: Test Tunnels Locally

From your Windows machine (new terminal):

```bash
# Test VIIRS via tunnel
curl http://localhost:8000/health

# Test Aqueduct via tunnel
curl http://localhost:8001/health

# Test VIIRS tool
curl -X POST http://localhost:8000/mcp/call_tool ^
  -H "Content-Type: application/json" ^
  -d "{\"tool\": \"describe_viirs_dataset\", \"arguments\": {}}"

# Test Aqueduct tool
curl -X POST http://localhost:8001/mcp/call_tool ^
  -H "Content-Type: application/json" ^
  -d "{\"tool\": \"list_datasets\", \"arguments\": {}}"
```

(Use `^` for line continuation in Windows CMD, or `\` in Git Bash)

## Step 7: Configure Claude Desktop for HTTP

**File:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "viirs": {
      "command": "node",
      "args": ["-e", "require('http').request('http://localhost:8000/mcp').end()"],
      "transport": "sse",
      "url": "http://localhost:8000/mcp"
    },
    "aqueduct": {
      "command": "node",
      "args": ["-e", "require('http').request('http://localhost:8001/mcp').end()"],
      "transport": "sse",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

**Note:** Claude Desktop's HTTP/SSE support is somewhat experimental. If the above doesn't work, we can use the MCP proxy approach (pipeline_app_v2.py) which is proven to work.

## Step 8: Restart Claude Desktop

1. Quit Claude Desktop completely
2. Ensure SSH tunnels are still running
3. Start Claude Desktop
4. Test with: "Use the describe_viirs_dataset tool"

## Alternative: Use pipeline_app_v2.py (Recommended)

If Claude Desktop's HTTP transport has issues, use the Flask proxy:

```bash
# On Windows
cd Source/Webapp
set VIIRS_MCP_URL=http://localhost:8000
set AQUEDUCT_MCP_URL=http://localhost:8001
python pipeline_app_v2.py
```

Visit http://127.0.0.1:5000 and you have a working ClimateGPT interface!

## Troubleshooting

### HTTP adapters won't start

**Check Python environment:**
```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP "cd . && source .venv/bin/activate && python --version && pip list | grep -E '(flask|mcp)'"
```

**Install missing dependencies:**
```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP "cd . && source .venv/bin/activate && pip install flask flask-cors"
```

### Can't connect via tunnel

**Check if adapters are running:**
```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP "netstat -tuln | grep -E '(8000|8001)'"
```

**Check tunnel is active:**
```bash
netstat -an | findstr "8000"
netstat -an | findstr "8001"
```

### VIIRS database not found

**Set the environment variable when starting:**
```bash
export VIIRS_DUCKDB_PATH=/srv/viirs_database/VIIRS_Thermal_Database.duckdb
python viirs_http_adapter_v2.py
```

### Firewall issues

If running on Windows firewall:
```bash
# Allow Python through firewall
netsh advfirewall firewall add rule name="Python Flask" dir=in action=allow program="C:\Path\To\python.exe" enable=yes
```

## Running as a Service (Optional)

To keep HTTP adapters running permanently:

### Using systemd (on OpenStack):

Create `/etc/systemd/system/viirs-http.service`:
```ini
[Unit]
Description=VIIRS MCP HTTP Adapter
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=.
Environment="VIIRS_DUCKDB_PATH=/srv/viirs_database/VIIRS_Thermal_Database.duckdb"
ExecStart=./.venv/bin/python ./Source/Webapp/viirs_http_adapter_v2.py --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable viirs-http
sudo systemctl start viirs-http
```

## Summary

**Pros of HTTP Adapters:**
- ✅ Reliable, no EPIPE errors
- ✅ Easy to debug and test
- ✅ Works with multiple clients
- ✅ Can monitor with HTTP tools

**Quick Start:**
1. Deploy adapters to OpenStack
2. Start them with `start_http_adapters.sh`
3. Create SSH tunnels
4. Use pipeline_app_v2.py or configure Claude Desktop

**Files:**
- [viirs_http_adapter_v2.py](viirs_http_adapter_v2.py) - VIIRS HTTP adapter
- [aqueduct_http_adapter_v2.py](aqueduct_http_adapter_v2.py) - Aqueduct HTTP adapter
- [start_http_adapters.sh](start_http_adapters.sh) - Start both adapters
- [HTTP_ADAPTER_SETUP.md](HTTP_ADAPTER_SETUP.md) - This guide

**Next Steps:**
1. Deploy and test HTTP adapters
2. Create SSH tunnels
3. Test with curl
4. Use pipeline_app_v2.py for ClimateGPT interface



