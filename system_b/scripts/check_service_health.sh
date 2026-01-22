#!/bin/bash
# Comprehensive service health check

echo "=== Service Status ==="
sudo systemctl status solarhub-telemetry --no-pager -l | head -20

echo ""
echo "=== Recent Error Logs (last 30 lines) ==="
sudo tail -30 /opt/solarhub/logs/telemetry-error.log

echo ""
echo "=== Recent Standard Logs (last 30 lines) ==="
sudo tail -30 /opt/solarhub/logs/telemetry.log

echo ""
echo "=== Journal Logs (last 30 lines) ==="
sudo journalctl -u solarhub-telemetry -n 30 --no-pager

echo ""
echo "=== Process Check ==="
ps aux | grep uvicorn | grep -v grep

echo ""
echo "=== Port Check ==="
sudo ss -tlnp | grep 8001 || echo "Port 8001 is NOT listening"

echo ""
echo "=== Test Connection ==="
curl -v http://127.0.0.1:8001/health 2>&1 | head -10
