# Restart Services After SQLAlchemy Fix

## What Was Fixed

Fixed SQLAlchemy relationship error in `DeviceSettings` model:
- Changed `relationship("Device")` to `relationship("DeviceModel")`
- Commit: `0f8849d`

## Steps to Restart Services

### On Remote Server (root@faisal-home)

1. **Pull Latest Code**
   ```bash
   cd /opt/solarhub/app/solar-hub
   git pull origin main
   ```

2. **Restart System A (Main API)**

   Find and kill the process:
   ```bash
   # Find the process
   ps aux | grep uvicorn | grep system_a

   # Kill it (replace PID with actual process ID)
   kill -9 <PID>

   # OR use pkill
   pkill -f "uvicorn.*system_a"
   ```

   Start System A:
   ```bash
   cd /opt/solarhub/app/solar-hub/system_a
   source /opt/solarhub/venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload >> /opt/solarhub/logs/system_a.log 2>&1 &
   ```

3. **Restart System B (Device Communication)**

   Find and kill:
   ```bash
   pkill -f "uvicorn.*system_b"
   ```

   Start System B:
   ```bash
   cd /opt/solarhub/app/solar-hub/system_b
   source /opt/solarhub/venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload >> /opt/solarhub/logs/system_b.log 2>&1 &
   ```

4. **Verify Services**
   ```bash
   # Check System A
   curl http://localhost:8000/health

   # Check System B
   curl http://localhost:8001/health

   # Test login
   curl -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"e2e.test@testing.com","password":"Test@123456"}'
   ```

### On Local Windows Machine

If running locally:

1. **Stop Services**
   - Press Ctrl+C in each terminal running the services
   - Or use Task Manager to kill Python processes

2. **Pull Latest Code**
   ```bash
   cd C:\Users\kunwa\PycharmProjects\solar-hub
   git pull origin main
   ```

3. **Start System A**
   ```bash
   cd system_a
   ..\venv\Scripts\activate  # or source venv activation
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Start System B** (in new terminal)
   ```bash
   cd system_b
   ..\venv\Scripts\activate
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```

5. **Start Frontend** (in new terminal)
   ```bash
   cd frontend
   npm run dev
   ```

6. **Verify**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8001/health
   curl http://localhost:8081
   ```

---

## After Restart - Run E2E Tests

Once all services are restarted:

```bash
cd tests/e2e-ts

# Clean old auth state
rm -rf test-results/.auth

# Run smoke tests
npm run regression:local:smoke

# Or run full regression
npm run regression:local

# View results
npm run regression:report
```

---

## Quick Restart Script (Linux/Remote Server)

Save this as `/opt/solarhub/restart-services.sh`:

```bash
#!/bin/bash
set -e

echo "🔄 Restarting Solar Hub Services..."

# Pull latest code
cd /opt/solarhub/app/solar-hub
git pull origin main

# Kill existing processes
echo "Stopping services..."
pkill -f "uvicorn.*system_a" || true
pkill -f "uvicorn.*system_b" || true
sleep 2

# Start System A
echo "Starting System A..."
cd /opt/solarhub/app/solar-hub/system_a
source /opt/solarhub/venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 >> /opt/solarhub/logs/system_a.log 2>&1 &
sleep 3

# Start System B
echo "Starting System B..."
cd /opt/solarhub/app/solar-hub/system_b
nohup uvicorn app.main:app --host 0.0.0.0 --port 8001 >> /opt/solarhub/logs/system_b.log 2>&1 &
sleep 3

# Verify
echo "Verifying services..."
curl -s http://localhost:8000/health && echo "✅ System A is healthy"
curl -s http://localhost:8001/health && echo "✅ System B is healthy" || echo "⚠️  System B not responding"

echo "✅ Services restarted successfully!"
```

Make it executable:
```bash
chmod +x /opt/solarhub/restart-services.sh
```

Run it:
```bash
/opt/solarhub/restart-services.sh
```
