#!/bin/bash
# Script to kill uvicorn processes

echo "=== Finding uvicorn processes ==="
UVICORN_PIDS=$(ps aux | grep -E "uvicorn|app.main:app" | grep -v grep | awk '{print $2}')

if [ -z "$UVICORN_PIDS" ]; then
    echo "No uvicorn processes found"
    exit 0
fi

echo "Found uvicorn processes: $UVICORN_PIDS"

# Check if running as systemd service
if systemctl is-active --quiet solarhub-telemetry; then
    echo ""
    echo "Uvicorn is running as systemd service. Use systemctl to stop it:"
    echo "  sudo systemctl stop solarhub-telemetry"
    echo ""
    read -p "Stop systemd service? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo systemctl stop solarhub-telemetry
        echo "Service stopped"
    fi
else
    echo ""
    echo "Killing uvicorn processes..."
    for pid in $UVICORN_PIDS; do
        echo "Killing process $pid"
        kill $pid
    done
    
    # Wait a bit and force kill if still running
    sleep 2
    for pid in $UVICORN_PIDS; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "Force killing process $pid"
            kill -9 $pid
        fi
    done
    
    echo "Done"
fi
