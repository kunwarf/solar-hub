#!/bin/bash
#===============================================================================
# Server Diagnostic Script
# Check if services are running and accessible
#===============================================================================

echo "========================================="
echo " Solar Hub Server Diagnostics"
echo "========================================="
echo ""

# 1. Check service status
echo "[1] Service Status:"
echo "-------------------"
sudo systemctl status solarhub-platform --no-pager | head -5
sudo systemctl status solarhub-telemetry --no-pager | head -5
echo ""

# 2. Check if services are listening
echo "[2] Services Listening on Ports:"
echo "--------------------------------"
sudo netstat -tulpn | grep -E ':8000|:8001|:8050|:3000|:80|:443'
echo ""

# 3. Check frontend build
echo "[3] Frontend Build Status:"
echo "--------------------------"
if [ -d "/opt/solarhub/app/frontend/dist" ]; then
    echo "✅ Frontend dist folder exists"
    ls -lh /opt/solarhub/app/frontend/dist/ | head -10
else
    echo "❌ Frontend dist folder NOT found"
fi
echo ""

# 4. Check nginx status (if installed)
echo "[4] Nginx Status:"
echo "-----------------"
if command -v nginx &> /dev/null; then
    sudo systemctl status nginx --no-pager | head -5
    echo ""
    echo "Nginx configuration:"
    sudo nginx -t 2>&1 | head -5
else
    echo "Nginx not installed"
fi
echo ""

# 5. Check firewall
echo "[5] Firewall Status (UFW):"
echo "--------------------------"
if command -v ufw &> /dev/null; then
    sudo ufw status | head -20
else
    echo "UFW not installed"
fi
echo ""

# 6. Check recent logs
echo "[6] Recent Platform Logs (last 10 lines):"
echo "------------------------------------------"
if [ -f "/opt/solarhub/logs/platform.log" ]; then
    tail -10 /opt/solarhub/logs/platform.log
else
    sudo journalctl -u solarhub-platform -n 10 --no-pager
fi
echo ""

# 7. Check if frontend is served
echo "[7] Frontend Server Status:"
echo "---------------------------"
if pgrep -f "npm.*dev" > /dev/null; then
    echo "✅ Frontend dev server is running"
    ps aux | grep "npm.*dev" | grep -v grep
elif [ -f "/opt/solarhub/app/frontend/dist/index.html" ]; then
    echo "✅ Frontend build exists (production mode)"
else
    echo "❌ No frontend server or build found"
fi
echo ""

# 8. Test local connectivity
echo "[8] Local Connectivity Test:"
echo "----------------------------"
echo "Platform API (8000):"
curl -s -o /dev/null -w "  HTTP Status: %{http_code}\n" http://127.0.0.1:8000/health 2>/dev/null || echo "  ❌ Cannot connect"

echo "Telemetry API (8001):"
curl -s -o /dev/null -w "  HTTP Status: %{http_code}\n" http://127.0.0.1:8001/health 2>/dev/null || echo "  ❌ Cannot connect"

echo "Frontend (8050):"
curl -s -o /dev/null -w "  HTTP Status: %{http_code}\n" http://127.0.0.1:8050/ 2>/dev/null || echo "  ❌ Cannot connect"

echo "Frontend (3000 - dev server):"
curl -s -o /dev/null -w "  HTTP Status: %{http_code}\n" http://127.0.0.1:3000/ 2>/dev/null || echo "  ❌ Cannot connect"
echo ""

# 9. Check external IP
echo "[9] Server External IP:"
echo "-----------------------"
curl -s ifconfig.me
echo ""
echo ""

echo "========================================="
echo " Diagnostic Complete"
echo "========================================="
echo ""
echo "Common Issues:"
echo "1. Frontend not running → cd /opt/solarhub/app/frontend && npm run dev"
echo "2. Firewall blocking port → sudo ufw allow 8050/tcp"
echo "3. Services not started → sudo systemctl start solarhub-platform solarhub-telemetry"
echo "4. Nginx not configured → Check /etc/nginx/sites-available/solarhub"
echo ""
