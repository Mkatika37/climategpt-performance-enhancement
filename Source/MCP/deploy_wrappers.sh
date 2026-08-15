#!/bin/bash
# Deploy MCP wrapper scripts to OpenStack server
# Run this from your local Windows machine using Git Bash or WSL

SERVER="YOUR_USERNAME@YOUR_SERVER_IP"
REMOTE_DIR="./Source/MCP"

echo "=========================================="
echo "Deploying MCP Wrapper Scripts"
echo "=========================================="
echo ""

# Check if SSH connection works
echo "Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 "$SERVER" "echo 'SSH connection successful'"; then
    echo "ERROR: Cannot connect to $SERVER"
    echo "Please check:"
    echo "  1. Server is reachable"
    echo "  2. SSH keys are configured"
    echo "  3. Username/hostname is correct"
    exit 1
fi
echo ""

# Upload wrapper scripts
echo "Uploading wrapper scripts..."
scp viirs_mcp_wrapper.sh "$SERVER:$REMOTE_DIR/" || {
    echo "ERROR: Failed to upload viirs_mcp_wrapper.sh"
    exit 1
}
echo "  ✓ viirs_mcp_wrapper.sh uploaded"

scp aqueduct_mcp_wrapper.sh "$SERVER:$REMOTE_DIR/" || {
    echo "ERROR: Failed to upload aqueduct_mcp_wrapper.sh"
    exit 1
}
echo "  ✓ aqueduct_mcp_wrapper.sh uploaded"
echo ""

# Set executable permissions
echo "Setting executable permissions..."
ssh "$SERVER" "chmod +x $REMOTE_DIR/viirs_mcp_wrapper.sh $REMOTE_DIR/aqueduct_mcp_wrapper.sh" || {
    echo "ERROR: Failed to set permissions"
    exit 1
}
echo "  ✓ Permissions set"
echo ""

# Test wrapper scripts
echo "Testing VIIRS wrapper script..."
ssh "$SERVER" "$REMOTE_DIR/viirs_mcp_wrapper.sh &" > /dev/null 2>&1 &
VIIRS_PID=$!
sleep 2
if kill -0 $VIIRS_PID 2>/dev/null; then
    echo "  ✓ VIIRS wrapper started successfully"
    kill $VIIRS_PID 2>/dev/null
else
    echo "  ⚠ VIIRS wrapper may have issues (check manually)"
fi

echo ""
echo "Testing Aqueduct wrapper script..."
ssh "$SERVER" "$REMOTE_DIR/aqueduct_mcp_wrapper.sh &" > /dev/null 2>&1 &
AQUEDUCT_PID=$!
sleep 2
if kill -0 $AQUEDUCT_PID 2>/dev/null; then
    echo "  ✓ Aqueduct wrapper started successfully"
    kill $AQUEDUCT_PID 2>/dev/null
else
    echo "  ⚠ Aqueduct wrapper may have issues (check manually)"
fi

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Update your Claude Desktop config with:"
echo "     $PWD/claude_mcp_config.json"
echo ""
echo "  2. Restart Claude Desktop"
echo ""
echo "  3. Check the connection in Claude"
echo ""
echo "For troubleshooting, see:"
echo "  $PWD/SSH_MCP_TROUBLESHOOTING.md"
echo ""



