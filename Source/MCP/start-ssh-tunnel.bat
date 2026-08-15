@echo off
REM Start SSH tunnel for MCP HTTP adapters
REM This forwards localhost:8000 -> YOUR_SERVER_IP:8000 (VIIRS)
REM and localhost:8001 -> YOUR_SERVER_IP:8001 (Aqueduct)

echo ========================================
echo Starting SSH Tunnel for MCP Servers
echo ========================================
echo.
echo Tunneling:
echo   localhost:8000 -^> YOUR_SERVER_IP:8000 (VIIRS)
echo   localhost:8001 -^> YOUR_SERVER_IP:8001 (Aqueduct)
echo.
echo Press Ctrl+C to stop the tunnel
echo ========================================
echo.

ssh -L 8000:localhost:8000 -L 8001:localhost:8001 YOUR_USERNAME@YOUR_SERVER_IP -N

