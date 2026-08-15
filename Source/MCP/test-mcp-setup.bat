@echo off
REM Test script to validate MCP HTTP setup

echo ========================================
echo Testing MCP HTTP Setup
echo ========================================
echo.

echo [1/4] Testing SSH tunnel...
curl -s http://localhost:8000/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   ✓ VIIRS HTTP adapter reachable on localhost:8000
) else (
    echo   ✗ FAILED: Cannot reach localhost:8000
    echo   → Run start-ssh-tunnel.bat first!
    goto :end
)

curl -s http://localhost:8001/health >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   ✓ Aqueduct HTTP adapter reachable on localhost:8001
) else (
    echo   ✗ FAILED: Cannot reach localhost:8001
    echo   → Run start-ssh-tunnel.bat first!
    goto :end
)
echo.

echo [2/4] Testing Node.js...
node --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
    echo   ✓ Node.js installed: %NODE_VERSION%
) else (
    echo   ✗ FAILED: Node.js not found
    echo   → Install Node.js from https://nodejs.org/
    goto :end
)
echo.

echo [3/4] Testing mcp-http-client.js...
if exist "C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP\mcp-http-client.js" (
    echo   ✓ mcp-http-client.js found
) else (
    echo   ✗ FAILED: mcp-http-client.js not found
    goto :end
)
echo.

echo [4/4] Testing MCP communication...
echo {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}} | node "C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP\mcp-http-client.js" http://localhost:8000 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   ✓ MCP HTTP client working
) else (
    echo   ✗ FAILED: MCP HTTP client test failed
    goto :end
)
echo.

echo ========================================
echo ✓ All tests passed!
echo ========================================
echo.
echo Next steps:
echo   1. Restart Claude Desktop (Quit completely and reopen)
echo   2. Look for 🔧 viirs_http and 🔧 aqueduct_http in Claude Desktop
echo   3. Try asking: "How many fires around Los Angeles?"
echo.

goto :eof

:end
echo.
echo ========================================
echo ✗ Setup incomplete - see errors above
echo ========================================
echo.
pause



