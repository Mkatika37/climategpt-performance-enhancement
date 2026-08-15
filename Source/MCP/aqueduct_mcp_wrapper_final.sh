#!/bin/bash
# Final wrapper for Aqueduct MCP Server over SSH
# Uses proper stdin handling to prevent premature closure

set -e  # Exit on error

# Redirect script errors to stderr
exec 2>&1

# Set unbuffered I/O
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Change to project directory
cd /srv/github/GMU_DAEN_2025_02_D

# Activate venv
source .venv/bin/activate

# Change to MCP directory
cd Source/MCP

# Run MCP server with unbuffered I/O
# The exec ensures the Python process replaces this shell
exec python3 -u Aqueduct_Server.py

