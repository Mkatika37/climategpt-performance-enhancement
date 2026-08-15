# Claude Desktop HTTP MCP Setup Guide

This guide shows you how to connect Claude Desktop to your MCP servers running on OpenStack via HTTP transport.

## Architecture

```
Claude Desktop (Windows)
    ↓ stdio (JSON-RPC)
mcp-http-client.js (Node.js bridge)
    ↓ HTTP
localhost:8000 / localhost:8001 (SSH tunnel)
    ↓ SSH
YOUR_SERVER_IP:8000 / 8001 (HTTP adapters)
    ↓
viirs_mcp_server.py / Aqueduct_Server.py
    ↓
DuckDB databases
```

## Prerequisites

✅ **Node.js installed** (v22.20.0 confirmed)
✅ **SSH access** to YOUR_USERNAME@YOUR_SERVER_IP
✅ **HTTP adapters running** on OpenStack server

## Setup Steps

### 1. Start SSH Tunnel

**Option A: Using the batch script**
```batch
cd C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP
start-ssh-tunnel.bat
```

**Option B: Manual command**
```bash
ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_USERNAME@YOUR_SERVER_IP -N
```

This creates port forwards:
- `localhost:8000` → `YOUR_SERVER_IP:8000` (VIIRS)
- `localhost:8001` → `YOUR_SERVER_IP:8001` (Aqueduct)

**Keep this terminal window open!** The tunnel runs as long as this SSH session is active.

### 2. Verify HTTP Adapters are Running

Open a new terminal and test:

```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy","service":"viirs-http-adapter",...}

curl http://localhost:8001/health
# Should return: {"status":"healthy","service":"aqueduct-http-adapter",...}
```

If these fail, the HTTP adapters aren't running on the OpenStack server. SSH in and start them:

```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP
cd ./Source/Webapp
./start_http_adapters.sh
```

### 3. Test MCP HTTP Client

Test the bridge script manually:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | node C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP\mcp-http-client.js http://localhost:8000
```

You should see a JSON response with the list of VIIRS tools.

### 4. Configure Claude Desktop

The configuration file is already updated at:
```
C:\Users\iruka\AppData\Roaming\Claude\claude_desktop_config.json
```

It now contains:
```json
{
  "mcpServers": {
    "viirs_http": {
      "command": "node",
      "args": [
        "C:\\Users\\iruka\\Documents\\GitHub\\climategpt-performance-enhancement\\Source\\MCP\\mcp-http-client.js",
        "http://localhost:8000"
      ]
    },
    "aqueduct_http": {
      "command": "node",
      "args": [
        "C:\\Users\\iruka\\Documents\\GitHub\\climategpt-performance-enhancement\\Source\\MCP\\mcp-http-client.js",
        "http://localhost:8001"
      ]
    }
  }
}
```

### 5. Restart Claude Desktop

1. **Quit Claude Desktop completely** (right-click system tray icon → Quit)
2. **Start Claude Desktop again**
3. Look for the MCP server icons in the bottom-left corner:
   - 🔧 `viirs_http`
   - 🔧 `aqueduct_http`

### 6. Test in Claude Desktop

Try asking:
- "How many fires have happened around Los Angeles California?"
- "Show me recent wildfires"
- "What water datasets are available?"

Claude should now be able to use the VIIRS and Aqueduct MCP tools!

## Troubleshooting

### SSH Tunnel Disconnects

**Symptom:** Claude Desktop shows MCP connection errors

**Solution:** Restart the SSH tunnel:
```bash
cd C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP
start-ssh-tunnel.bat
```

### HTTP Adapters Not Running

**Symptom:** `curl http://localhost:8000/health` fails

**Solution:** SSH to server and restart adapters:
```bash
ssh YOUR_USERNAME@YOUR_SERVER_IP
cd ./Source/Webapp
pkill -f viirs_http_adapter
pkill -f aqueduct_http_adapter
./start_http_adapters.sh
```

### Claude Desktop Shows "MCP Server Error"

**Check the Claude Desktop logs:**
- Windows: `%APPDATA%\Claude\logs\mcp*.log`

**Common issues:**
1. Node.js not in PATH
2. mcp-http-client.js file path wrong
3. SSH tunnel not running

### Testing Individual Components

**Test SSH tunnel:**
```bash
curl http://localhost:8000/health
```

**Test HTTP adapter directly:**
```bash
curl http://localhost:8000/mcp/tools/list
```

**Test MCP HTTP client:**
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | node mcp-http-client.js http://localhost:8000
```

## Comparison: HTTP vs stdio Transport

### Old Config (stdio over SSH - UNRELIABLE)
```json
{
  "command": "ssh",
  "args": ["YOUR_USERNAME@YOUR_SERVER_IP", "/srv/.../wrapper.sh"],
  "transport": "stdio"
}
```

**Problems:**
- ❌ BrokenPipeError with stderr output
- ❌ Race conditions in stdin/stdout handling
- ❌ Difficult to debug

### New Config (HTTP via tunnel - RELIABLE)
```json
{
  "command": "node",
  "args": ["mcp-http-client.js", "http://localhost:8000"]
}
```

**Benefits:**
- ✅ Proper HTTP request/response cycle
- ✅ No stderr conflicts
- ✅ Easy to test with curl
- ✅ Same setup used by pipeline_app_v2.py

## Daily Workflow

**Morning startup:**
1. Open terminal
2. Run `start-ssh-tunnel.bat`
3. Start Claude Desktop
4. Start coding!

**End of day:**
1. Ctrl+C in tunnel terminal to stop SSH tunnel
2. Quit Claude Desktop

**The HTTP adapters on OpenStack can stay running 24/7** - they're lightweight and stable.

## Files Created

- `mcp-http-client.js` - Node.js bridge between Claude Desktop and HTTP adapters
- `start-ssh-tunnel.bat` - Convenient script to start SSH tunnel
- `claude_desktop_config.json` - Claude Desktop MCP configuration (updated)

## See Also

- [HTTP_ADAPTER_SETUP.md](../../Webapp/HTTP_ADAPTER_SETUP.md) - HTTP adapter details
- [QUICK_START_HTTP.md](../../Webapp/QUICK_START_HTTP.md) - HTTP adapter quick start
- [PROMPT_ENGINEERING_FIX.md](../../Webapp/PROMPT_ENGINEERING_FIX.md) - ClimateGPT integration fixes



