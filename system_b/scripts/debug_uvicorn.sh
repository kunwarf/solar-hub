#!/bin/bash
# Script to debug uvicorn service issues

echo "=== Service Status ==="
sudo systemctl status solarhub-telemetry --no-pager -l

echo ""
echo "=== Recent Logs (last 50 lines) ==="
sudo journalctl -u solarhub-telemetry -n 50 --no-pager

echo ""
echo "=== Error Logs ==="
sudo journalctl -u solarhub-telemetry --since "5 minutes ago" | grep -i error

echo ""
echo "=== Check if process is actually running ==="
ps aux | grep uvicorn | grep -v grep

echo ""
echo "=== Check port 8001 ==="
sudo ss -tlnp | grep 8001 || echo "Port 8001 is NOT listening"

echo ""
echo "=== Check service logs file ==="
if [ -f /opt/solarhub/logs/telemetry-error.log ]; then
    echo "Last 20 lines of error log:"
    tail -20 /opt/solarhub/logs/telemetry-error.log
else
    echo "Error log file not found at /opt/solarhub/logs/telemetry-error.log"
fi

echo ""
echo "=== Check if log directory exists ==="
ls -la /opt/solarhub/logs/ 2>/dev/null || echo "Log directory does not exist"
