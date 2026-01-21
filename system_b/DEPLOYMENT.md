sudo nano /etc/systemd/system/solarhub-platform.service
# Change WorkingDirectory from:
#   WorkingDirectory=/opt/solarhub/app/system_a
# To:
#   WorkingDirectory=/opt/solarhub/app/solar-hub/system_a

# Update the telemetry service
sudo nano /etc/systemd/system/solarhub-telemetry.service
# Change WorkingDirectory from:
#   WorkingDirectory=/opt/solarhub/app/system_b
# To:
#   WorkingDirectory=/opt/solarhub/app/solar-hub/system_b

# Then reload systemd and restart services
sudo systemctl daemon-reload
sudo systemctl start solarhub-platform
sudo systemctl start solarhub-telemetry

# System B - Deployment Guide

System B is the Communication & Telemetry component of Solar Hub. This guide covers deployment on a server with Redis, PostgreSQL (with TimescaleDB), MQTT, and Docker already installed.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Database Setup](#database-setup)
3. [Environment Configuration](#environment-configuration)
4. [Application Installation](#application-installation)
5. [Running the Application](#running-the-application)
6. [Running Tests](#running-tests)
7. [Systemd Service Setup](#systemd-service-setup)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Ensure the following are installed and running on your server:

- **Python 3.11+**
- **PostgreSQL 14+** with **TimescaleDB extension**
- **Redis 7+**
- **MQTT Broker** (Mosquitto or similar)

Verify services are running:

```bash
# Check PostgreSQL
sudo systemctl status postgresql

# Check Redis
sudo systemctl status redis

# Check MQTT (if using Mosquitto)
sudo systemctl status mosquitto
```

---

## Database Setup

### 1. Install TimescaleDB Extension

If TimescaleDB is not already installed:

```bash
# Ubuntu/Debian
sudo apt install timescaledb-2-postgresql-14

# Enable the extension in PostgreSQL
sudo timescaledb-tune --quiet --yes

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### 2. Create the Database

Connect to PostgreSQL and create the database:

```bash
# Connect as postgres user
sudo -u postgres psql
```

postgres=#  ALTER USER solarhub_telemetry WITH PASSWORD 'system_b_telemetery';
ALTER ROLE
postgres=# ALTER USER solarhub_app WITH PASSWORD 'system_a_app';


Run the following SQL commands:

```sql
-- Create the database
CREATE DATABASE solar_hub_telemetry;

-- Connect to the new database
\c solar_hub_telemetry

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Verify TimescaleDB is enabled
SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';

-- Exit psql
\q
```

### 3. Create Database User (Optional but Recommended)

```sql
-- Create a dedicated user
CREATE USER solar_hub_user WITH PASSWORD 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE solar_hub_telemetry TO solar_hub_user;

-- Connect to the database and grant schema privileges
\c solar_hub_telemetry
GRANT ALL ON SCHEMA public TO solar_hub_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO solar_hub_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO solar_hub_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO solar_hub_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO solar_hub_user;
```

### 4. Run Database Migrations

Navigate to the system_b directory and run Alembic migrations:

```bash
cd /path/to/solar-hub/system_b

# Set the database URL environment variable
export SYSTEM_B_DATABASE_URL="postgresql+asyncpg://solar_hub_user:your_secure_password@localhost:5432/solar_hub_telemetry"

# Run migrations
alembic upgrade head
```

This will create all required tables:
- `device_registry` - Device management
- `telemetry_raw` - Raw telemetry hypertable
- `device_events` - Device events hypertable
- `device_commands` - Command queue
- `metric_definitions` - Standard metrics (pre-populated)
- `ingestion_batches` - Batch tracking

### 5. Verify Database Setup

```bash
sudo -u postgres psql -d solar_hub_telemetry -c "\dt"
```

Expected output:
```
              List of relations
 Schema |        Name         | Type  |  Owner
--------+---------------------+-------+----------
 public | alembic_version     | table | postgres
 public | device_commands     | table | postgres
 public | device_events       | table | postgres
 public | device_registry     | table | postgres
 public | ingestion_batches   | table | postgres
 public | metric_definitions  | table | postgres
 public | telemetry_raw       | table | postgres
```

Verify hypertables:
```bash
sudo -u postgres psql -d solar_hub_telemetry -c "SELECT hypertable_name FROM timescaledb_information.hypertables;"
```

---

## Environment Configuration

### 1. Create Environment File

Create a `.env` file in the `system_b` directory:

```bash
cd /path/to/solar-hub/system_b
nano .env
```

Add the following configuration (adjust values for your environment):

```bash
# =============================================================================
# System B Environment Configuration
# =============================================================================

# Application Settings
APP_NAME="Solar Hub Telemetry"
APP_VERSION="1.0.0"
DEBUG=false
ENVIRONMENT=production

# Server Settings
HOST=0.0.0.0
PORT=8001
WORKERS=4
RELOAD=false

# API Settings
API_PREFIX=/api
API_VERSION=v1

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# =============================================================================
# TimescaleDB Configuration
# =============================================================================
TIMESCALE_HOST=localhost
TIMESCALE_PORT=5432
TIMESCALE_NAME=solar_hub_telemetry
TIMESCALE_USER=solar_hub_user
TIMESCALE_PASSWORD=your_secure_password
TIMESCALE_POOL_SIZE=10
TIMESCALE_MAX_OVERFLOW=20
TIMESCALE_ECHO_SQL=false

# TimescaleDB-specific settings
TIMESCALE_CHUNK_TIME_INTERVAL="1 day"
TIMESCALE_RETENTION_DAYS=90
TIMESCALE_COMPRESSION_AFTER_DAYS=7

# =============================================================================
# Redis Configuration
# =============================================================================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1
REDIS_PASSWORD=
REDIS_SSL=false
REDIS_STREAM_MAX_LEN=100000
REDIS_CONSUMER_GROUP=telemetry_processors

# =============================================================================
# Protocol Settings (MQTT, Modbus, HTTP)
# =============================================================================
PROTOCOL_MQTT_ENABLED=true
PROTOCOL_MQTT_BROKER_HOST=localhost
PROTOCOL_MQTT_BROKER_PORT=1883
PROTOCOL_MQTT_USERNAME=
PROTOCOL_MQTT_PASSWORD=
PROTOCOL_MQTT_CLIENT_ID=solar_hub_system_b
PROTOCOL_MQTT_TOPIC_PREFIX=solarhub/

PROTOCOL_MODBUS_ENABLED=true
PROTOCOL_MODBUS_TCP_PORT=502
PROTOCOL_MODBUS_TIMEOUT=5.0

PROTOCOL_HTTP_ENABLED=true
PROTOCOL_HTTP_TIMEOUT=30.0

# =============================================================================
# Device Authentication
# =============================================================================
DEVICE_AUTH_TOKEN_VALIDITY_MINUTES=5
DEVICE_AUTH_SECRET_KEY=your-super-secret-key-change-in-production
DEVICE_AUTH_ALGORITHM=HS256

# =============================================================================
# Telemetry Processing
# =============================================================================
TELEMETRY_BATCH_SIZE=100
TELEMETRY_FLUSH_INTERVAL_SECONDS=1.0
TELEMETRY_MAX_METRIC_VALUE=1000000
TELEMETRY_MIN_METRIC_VALUE=-1000000
TELEMETRY_MAX_MESSAGES_PER_MINUTE=120

# =============================================================================
# Background Workers
# =============================================================================
WORKER_TELEMETRY_PROCESSOR_WORKERS=4
WORKER_AGGREGATION_WORKER_INTERVAL=60
WORKER_ALERT_CHECKER_INTERVAL=10

# =============================================================================
# System A Integration
# =============================================================================
SYSTEM_A_URL=http://localhost:8000
SYSTEM_A_API_KEY=your-system-a-api-key

# =============================================================================
# Device Server Settings
# =============================================================================
DEVICE_SERVER_HOST=0.0.0.0
DEVICE_SERVER_PORT=8502
DEVICE_SERVER_MAX_CONNECTIONS=1000
DEVICE_SERVER_BACKLOG=100

DEVICE_CONNECTION_TIMEOUT=30.0
DEVICE_CONNECTION_KEEPALIVE=60.0
DEVICE_CONNECTION_READ_TIMEOUT=10.0
DEVICE_CONNECTION_WRITE_TIMEOUT=10.0

DEVICE_POLLING_DEFAULT_INTERVAL=10
DEVICE_POLLING_MIN_INTERVAL=5
DEVICE_POLLING_MAX_INTERVAL=300

# Timezone
DEFAULT_TIMEZONE=Asia/Karachi
```

### 2. Secure the Environment File

```bash
chmod 600 .env
```

---

## Application Installation

### 1. Clone Repository (if not already done)

```bash
git clone <repository-url> /opt/solar-hub
cd /opt/solar-hub/system_b
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install main dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install test dependencies (for running tests)
pip install -r requirements-test.txt
```

### 4. Verify Installation

```bash
# Check that imports work
python -c "from app.main import app; print('Import successful')"
```

---

## Running the Application

### Option 1: Direct Run (Development/Testing)

```bash
cd /path/to/solar-hub/system_b
source venv/bin/activate

# Run the API server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

### Option 2: Using the Main Module

```bash
cd /path/to/solar-hub/system_b
source venv/bin/activate

# Run using Python module
python -m app.main
```

### Option 3: Run with Gunicorn (Production)

```bash
pip install gunicorn

gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8001 \
    --access-logfile - \
    --error-logfile -
```

### Verify Application is Running

```bash
# Health check
curl http://localhost:8001/health

# Expected response:
# {"status":"healthy","services":{"timescaledb":"up","redis":"up"},"version":"1.0.0","environment":"production"}
```

---

## Running Tests

### 1. Set Up Test Environment

```bash
cd /path/to/solar-hub/system_b
source venv/bin/activate

# Install test dependencies if not already installed
pip install -r requirements-test.txt
```

### 2. Run All Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=html
```

### 3. Run Specific Test Categories

```bash
# Run only E2E tests
pytest tests/e2e/ -v

# Run only unit tests
pytest tests/ -v -m unit

# Run only integration tests
pytest tests/ -v -m integration

# Run only E2E tests
pytest tests/ -v -m e2e
```

### 4. Run Specific Test Files

```bash
# Run command flow tests
pytest tests/e2e/test_command_flow.py -v

# Run telemetry flow tests
pytest tests/e2e/test_telemetry_flow.py -v

# Run device discovery tests
pytest tests/e2e/test_device_discovery_flow.py -v

# Run event flow tests
pytest tests/e2e/test_event_flow.py -v
```

### 5. Run Tests with Verbose Output

```bash
# Very verbose output with full tracebacks
pytest tests/ -vv --tb=long

# Show print statements
pytest tests/ -v -s
```

### 6. Generate Test Reports

```bash
# HTML coverage report
pytest tests/ --cov=app --cov-report=html
# Report will be in htmlcov/index.html

# JUnit XML report (for CI/CD)
pytest tests/ --junitxml=test-results.xml
```

---

## Systemd Service Setup

### 1. Create Systemd Service File

```bash
sudo nano /etc/systemd/system/solar-hub-system-b.service
```

Add the following content:

```ini
[Unit]
Description=Solar Hub System B - Telemetry Service
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=exec
User=solar-hub
Group=solar-hub
WorkingDirectory=/opt/solar-hub/system_b
Environment="PATH=/opt/solar-hub/system_b/venv/bin"
EnvironmentFile=/opt/solar-hub/system_b/.env
ExecStart=/opt/solar-hub/system_b/venv/bin/gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8001 \
    --access-logfile /var/log/solar-hub/system-b-access.log \
    --error-logfile /var/log/solar-hub/system-b-error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 2. Create Log Directory and User

```bash
# Create dedicated user (optional)
sudo useradd -r -s /bin/false solar-hub

# Create log directory
sudo mkdir -p /var/log/solar-hub
sudo chown solar-hub:solar-hub /var/log/solar-hub

# Set ownership of application directory
sudo chown -R solar-hub:solar-hub /opt/solar-hub
```

### 3. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable solar-hub-system-b

# Start the service
sudo systemctl start solar-hub-system-b

# Check status
sudo systemctl status solar-hub-system-b
```

### 4. View Logs

```bash
# View service logs
sudo journalctl -u solar-hub-system-b -f

# View application logs
tail -f /var/log/solar-hub/system-b-error.log
```

---

## Quick Reference Commands

### Database Commands

```bash
# Connect to database
sudo -u postgres psql -d solar_hub_telemetry

# Run migrations
cd /opt/solar-hub/system_b && source venv/bin/activate
alembic upgrade head

# Check migration status
alembic current

# Rollback last migration
alembic downgrade -1
```

### Application Commands

```bash
# Start application
sudo systemctl start solar-hub-system-b

# Stop application
sudo systemctl stop solar-hub-system-b

# Restart application
sudo systemctl restart solar-hub-system-b

# Check health
curl http://localhost:8001/health
```

### Test Commands

```bash
# Run all tests
cd /opt/solar-hub/system_b && source venv/bin/activate
pytest tests/ -v

# Run E2E tests only
pytest tests/e2e/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html
```

---

## Troubleshooting

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -h localhost -U solar_hub_user -d solar_hub_telemetry -c "SELECT 1;"

# Check PostgreSQL is listening
sudo netstat -tlnp | grep 5432

# Check TimescaleDB extension
psql -d solar_hub_telemetry -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis is listening
sudo netstat -tlnp | grep 6379
```

### Application Issues

```bash
# Check application logs
sudo journalctl -u solar-hub-system-b -n 100

# Test API health
curl -v http://localhost:8001/health

# Check if port is in use
sudo lsof -i :8001
```

### Permission Issues

```bash
# Fix ownership
sudo chown -R solar-hub:solar-hub /opt/solar-hub

# Fix .env permissions
chmod 600 /opt/solar-hub/system_b/.env
```

---

## Port Summary

| Service | Default Port | Description |
|---------|-------------|-------------|
| System B API | 8001 | FastAPI telemetry API |
| Device Server | 8502 | TCP server for data loggers |
| PostgreSQL | 5432 | TimescaleDB |
| Redis | 6379 | Streams & caching |
| MQTT | 1883 | MQTT broker |

---

## Environment Variables Quick Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `TIMESCALE_HOST` | localhost | Database host |
| `TIMESCALE_PORT` | 5432 | Database port |
| `TIMESCALE_NAME` | solar_hub_telemetry | Database name |
| `TIMESCALE_USER` | postgres | Database user |
| `TIMESCALE_PASSWORD` | postgres | Database password |
| `REDIS_HOST` | localhost | Redis host |
| `REDIS_PORT` | 6379 | Redis port |
| `REDIS_DB` | 1 | Redis database number |
| `PORT` | 8001 | API server port |
| `WORKERS` | 2 | Number of worker processes |
| `DEBUG` | false | Enable debug mode |
