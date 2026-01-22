#!/bin/bash
# Script to check and manage uvicorn processes

echo "=== Checking for uvicorn processes ==="
ps aux | grep -E "uvicorn|app.main:app" | grep -v grep

echo ""
echo "=== Checking systemd service status ==="
systemctl status solarhub-telemetry --no-pager -l

echo ""
echo "=== Checking if port 8001 is in use ==="
netstat -tlnp | grep 8001 || ss -tlnp | grep 8001
