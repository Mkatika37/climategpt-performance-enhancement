@echo off
REM Test the MCP HTTP client manually

echo Testing MCP HTTP Client
echo ========================
echo.

REM Test initialize message
echo Testing 'initialize' method...
echo {"jsonrpc":"2.0","id":1,"method":"initialize","params":{}} | node "C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP\mcp-http-client.js" http://localhost:8000
echo.

echo Testing 'tools/list' method...
echo {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}} | node "C:\Users\iruka\Documents\GitHub\climategpt-performance-enhancement\Source\MCP\mcp-http-client.js" http://localhost:8000
echo.

echo ========================
echo Check log file at: %TEMP%\mcp-http-client-8000.log
echo.
pause



