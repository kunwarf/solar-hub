#!/bin/bash
# Script to check System B logs

echo "=== System B Service Logs ==="
echo ""
echo "1. Recent Error Log (last 50 lines):"
echo "-----------------------------------"
sudo tail -50 /opt/solarhub/logs/telemetry-error.log

echo ""
echo "2. Recent Standard Log (last 50 lines):"
echo "-----------------------------------"
sudo tail -50 /opt/solarhub/logs/telemetry.log

echo ""
echo "3. Systemd Journal Logs (last 50 lines):"
echo "-----------------------------------"
sudo journalctl -u solarhub-telemetry -n 50 --no-pager

echo ""
echo "4. Recent Errors Only:"
echo "-----------------------------------"
sudo journalctl -u solarhub-telemetry --since "10 minutes ago" | grep -i error

echo ""
echo "5. Full Traceback (if any):"
echo "-----------------------------------"
sudo journalctl -u solarhub-telemetry --since "10 minutes ago" | grep -A 20 -i "traceback\|exception\|error"
