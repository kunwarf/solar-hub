#!/bin/bash
# Get detailed error information from System B logs

echo "=== Checking Error Log File ==="
if [ -f /opt/solarhub/logs/telemetry-error.log ]; then
    echo "Last 100 lines of error log:"
    sudo tail -100 /opt/solarhub/logs/telemetry-error.log
else
    echo "Error log file not found"
fi

echo ""
echo "=== Checking Standard Log for Errors ==="
sudo tail -200 /opt/solarhub/logs/telemetry.log | grep -A 30 -i "error\|exception\|traceback\|failed"

echo ""
echo "=== Full Journal Logs (Last 200 lines) ==="
sudo journalctl -u solarhub-telemetry -n 200 --no-pager

echo ""
echo "=== Testing Device Registration Manually ==="
echo "You can test the endpoint directly:"
echo "curl -X POST http://127.0.0.1:8001/api/v1/devices/register \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"site_id\":\"89e93c4c-a466-459d-9453-8f32a73a401f\",\"device_type\":\"inverter\",\"serial_number\":\"PD12K00001\",\"protocol_id\":\"powdrive\"}'"
