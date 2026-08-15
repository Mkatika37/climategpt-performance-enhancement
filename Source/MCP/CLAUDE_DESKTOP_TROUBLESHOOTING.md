## Claude Desktop MCP HTTP Troubleshooting Guide

### Current Error: Invalid Union / Zod Validation Errors

**Error Pattern:**
```
invalid_union
Unrecognized key(s) in object: 'error'
```

This error means Claude Desktop is receiving malformed JSON-RPC responses from the MCP HTTP client.

---

## Quick Diagnosis

### Step 1: Is the SSH Tunnel Running?

**Test:**
```bash
curl http://localhost:8000/health
```

**Expected:**
```json
{"status":"healthy","service":"viirs-http-adapter",...}
```

**If it fails:**
```bash
# Start the SSH tunnel
cd C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP
start-ssh-tunnel.bat
```

### Step 2: Test the MCP HTTP Client

**Run the test script:**
```bash
cd C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP
test-mcp-http-client.bat
```

**Expected output:** Valid JSON-RPC responses

**Check the debug log:**
```
%TEMP%\mcp-http-client-8000.log
%TEMP%\mcp-http-client-8001.log
```

Example path: `C:\Users\iruka\AppData\Local\Temp\mcp-http-client-8000.log`

### Step 3: Check Claude Desktop Logs

**Location:**
```
%APPDATA%\Claude\logs\
```

**Key files:**
- `mcp-server-viirs_http.log`
- `mcp-server-aqueduct_http.log`

---

## Common Issues & Solutions

### Issue 1: "Invalid Union" Errors

**Cause:** SSH tunnel not running, so HTTP requests fail

**Solution:**
1. Start SSH tunnel: `start-ssh-tunnel.bat`
2. Restart Claude Desktop completely (Quit → Reopen)
3. Check logs in `%TEMP%\mcp-http-client-8000.log`

### Issue 2: Connection Refused

**Symptoms in log:**
```
tools/list error: connect ECONNREFUSED
```

**Solution:**
```bash
# Check if tunnel is running
netstat -an | findstr "8000"
netstat -an | findstr "8001"

# If not, start it
start-ssh-tunnel.bat
```

### Issue 3: HTTP Adapters Not Running

**Symptoms:** SSH tunnel works but HTTP requests fail

**Solution:**
```bash
# SSH to server and check adapters
ssh YOUR_USERNAME@YOUR_SERVER_IP "./Source/Webapp/start_http_adapters.sh"
```

### Issue 4: MCP Servers Don't Appear in Claude Desktop

**Check:**
1. Claude Desktop configuration is correct
2. Node.js is in PATH: `node --version`
3. mcp-http-client.js exists at the configured path
4. Restart Claude Desktop **completely** (not just close window)

---

## Debugging Workflow

### 1. Test Local Connectivity

```bash
# Test VIIRS
curl http://localhost:8000/health

# Test Aqueduct
curl http://localhost:8001/health
```

### 2. Test MCP Client Manually

```bash
# Initialize
echo {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}} | node mcp-http-client.js http://localhost:8000

# List tools
echo {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}} | node mcp-http-client.js http://localhost:8000
```

### 3. Check Debug Logs

**MCP HTTP Client logs:**
```
type %TEMP%\mcp-http-client-8000.log
type %TEMP%\mcp-http-client-8001.log
```

**Claude Desktop logs:**
```
cd %APPDATA%\Claude\logs
dir /o-d
type mcp-server-viirs_http.log
```

### 4. Test Tool Call

```bash
curl http://localhost:8000/mcp/call_tool -H "Content-Type: application/json" -d "{\"tool\": \"describe_viirs_dataset\", \"arguments\": {}}"
```

---

## Verification Checklist

Before using Claude Desktop, verify:

- [ ] SSH tunnel is running (`netstat -an | findstr "8000"`)
- [ ] HTTP adapters are running on server
- [ ] VIIRS health check works: `curl http://localhost:8000/health`
- [ ] Aqueduct health check works: `curl http://localhost:8001/health`
- [ ] Node.js is accessible: `node --version`
- [ ] mcp-http-client.js exists at configured path
- [ ] Claude Desktop config JSON is valid
- [ ] Claude Desktop was restarted after config changes

---

## Log File Locations

| Component | Log Location |
|-----------|--------------|
| MCP HTTP Client (VIIRS) | `%TEMP%\mcp-http-client-8000.log` |
| MCP HTTP Client (Aqueduct) | `%TEMP%\mcp-http-client-8001.log` |
| Claude Desktop (VIIRS) | `%APPDATA%\Claude\logs\mcp-server-viirs_http.log` |
| Claude Desktop (Aqueduct) | `%APPDATA%\Claude\logs\mcp-server-aqueduct_http.log` |
| HTTP Adapter (server-side) | Check SSH session output |

---

## Expected Log Output

### Successful Connection

**mcp-http-client-8000.log:**
```
2025-11-08T17:00:00.000Z MCP HTTP Client starting for http://localhost:8000
2025-11-08T17:00:01.000Z Received: initialize (id: 1)
2025-11-08T17:00:02.000Z Received: tools/list (id: 2)
2025-11-08T17:00:02.100Z Fetching tools list from HTTP server
2025-11-08T17:00:02.200Z Received 19 tools
```

### Failed Connection (SSH Tunnel Not Running)

**mcp-http-client-8000.log:**
```
2025-11-08T17:00:00.000Z MCP HTTP Client starting for http://localhost:8000
2025-11-08T17:00:01.000Z Received: initialize (id: 1)
2025-11-08T17:00:02.000Z Received: tools/list (id: 2)
2025-11-08T17:00:02.100Z Fetching tools list from HTTP server
2025-11-08T17:00:02.200Z tools/list error: connect ECONNREFUSED 127.0.0.1:8000
```

**Action:** Start SSH tunnel!

---

## Quick Fix Workflow

If Claude Desktop shows MCP errors:

```bash
# 1. Stop Claude Desktop completely
taskkill /IM "Claude.exe" /F

# 2. Start SSH tunnel
start-ssh-tunnel.bat

# 3. Verify connectivity
curl http://localhost:8000/health
curl http://localhost:8001/health

# 4. Clear logs (optional)
del %TEMP%\mcp-http-client-*.log

# 5. Start Claude Desktop
# (Launch from Start Menu)

# 6. Check logs
type %TEMP%\mcp-http-client-8000.log
```

---

## Still Having Issues?

### Collect Diagnostic Info

Run these commands and save output:

```bash
# Check Node.js
node --version

# Check SSH tunnel
netstat -an | findstr "8000"
netstat -an | findstr "8001"

# Test HTTP adapters
curl http://localhost:8000/health
curl http://localhost:8001/health

# Test MCP client
test-mcp-http-client.bat

# Show Claude config
type "%APPDATA%\Claude\claude_desktop_config.json"

# Show recent logs
type %TEMP%\mcp-http-client-8000.log
```

### Common Root Causes

1. **SSH tunnel died** - Restart it with `start-ssh-tunnel.bat`
2. **HTTP adapters stopped** - SSH to server and run `start_http_adapters.sh`
3. **Node.js not in PATH** - Reinstall Node.js or add to PATH
4. **Config file has syntax error** - Validate JSON at jsonlint.com
5. **Windows firewall blocking localhost** - Allow Node.js through firewall

---

## Testing Without Claude Desktop

You can test the entire stack without Claude Desktop:

```bash
# 1. Start SSH tunnel
start-ssh-tunnel.bat

# 2. Test MCP client
test-mcp-http-client.bat

# 3. Manual tool call test
echo {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"describe_viirs_dataset","arguments":{}}} | node mcp-http-client.js http://localhost:8000
```

This isolates whether the problem is with the MCP client or Claude Desktop integration.



