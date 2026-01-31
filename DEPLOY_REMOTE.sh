#!/bin/bash
#===============================================================================
# Quick Deployment Script for Remote Server
# Run this on your remote server after SSHing in
#===============================================================================

set -e

echo "========================================="
echo " Solar Hub - Remote Deployment"
echo "========================================="
echo ""

# 1. Navigate to app directory
echo "[1/7] Navigating to app directory..."
cd /opt/solarhub/app || {
    echo "ERROR: Directory /opt/solarhub/app not found"
    exit 1
}

# 2. Stash any local changes
echo "[2/7] Stashing local changes..."
git stash --include-untracked 2>/dev/null || true

# 3. Pull latest code
echo "[3/7] Pulling latest code from GitHub..."
git pull origin main

# 4. Show latest commit
echo "[4/7] Latest commit pulled:"
git log -1 --pretty=format:"%h - %an, %ar : %s" --color=always
echo ""
echo ""

# 5. Build frontend
echo "[5/7] Building frontend with refactored component..."
cd frontend
npm ci
npm run build
cd ..

# 6. Restart services
echo "[6/7] Restarting backend services..."
sudo systemctl restart solarhub-platform
sudo systemctl restart solarhub-telemetry

# Wait for services to start
echo "Waiting for services to start..."
sleep 5

# 7. Health check
echo "[7/7] Running health checks..."
PLATFORM_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health)
TELEMETRY_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/health)

echo ""
echo "========================================="
echo " Deployment Complete!"
echo "========================================="
echo ""
echo "Health Status:"
echo "  Platform API (System A): HTTP $PLATFORM_HEALTH"
echo "  Telemetry API (System B): HTTP $TELEMETRY_HEALTH"
echo ""

if [ "$PLATFORM_HEALTH" == "200" ] && [ "$TELEMETRY_HEALTH" == "200" ]; then
    echo "✅ All services are healthy!"
    echo ""
    echo "Changes deployed:"
    echo "  ✅ Enhanced logging in System A"
    echo "  ✅ Refactored InverterSettingsPage (82% smaller)"
    echo "  ✅ Fixed repeated API calls"
    echo "  ✅ Better caching and polling"
    echo ""
    echo "Test the changes:"
    echo "  1. Open your browser and navigate to the device settings page"
    echo "  2. Check browser DevTools > Network tab"
    echo "  3. You should see:"
    echo "     - Only 1 query on first load"
    echo "     - No queries when navigating back within 60s"
    echo "     - Auto-refresh every 60 seconds"
    echo ""
    echo "Check the logs:"
    echo "  tail -f /opt/solarhub/logs/platform.log | grep query-settings"
    echo ""
else
    echo "❌ Health check failed!"
    echo ""
    echo "Check logs:"
    echo "  journalctl -u solarhub-platform -n 50"
    echo "  journalctl -u solarhub-telemetry -n 50"
    exit 1
fi
