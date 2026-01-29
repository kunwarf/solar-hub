# Database Credentials

**Created:** 2026-01-29

---

## PostgreSQL Database (solar_hub)

### Connection Details
```
Host:     localhost
Port:     5433
Database: solar_hub
Username: postgres
Password: faisal
```

### Connection String
```
postgresql://postgres:faisal@localhost:5433/solar_hub
```

### psql Command
```bash
PGPASSWORD=faisal psql -h localhost -p 5433 -U postgres -d solar_hub
```

### Python Connection (SQLAlchemy)
```python
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://postgres:faisal@localhost:5433/solar_hub"
engine = create_engine(DATABASE_URL)
```

### Python Connection (asyncpg)
```python
import asyncpg

conn = await asyncpg.connect(
    host='localhost',
    port=5433,
    user='postgres',
    password='faisal',
    database='solar_hub'
)
```

---

## TimescaleDB Extension

The database has TimescaleDB extension enabled for time-series data:

```sql
-- Check if TimescaleDB is installed
SELECT * FROM pg_extension WHERE extname = 'timescaledb';

-- List hypertables
SELECT * FROM timescaledb_information.hypertables;
```

---

## Database Schema

### Main Tables

#### Users & Organizations
- `users` - User accounts
- `organizations` - Organization records
- `sites` - Installation sites
- `devices` - Solar devices

#### Dashboard (Phase 2)
- `user_dashboard_preferences` - User dashboard settings
- `user_custom_presets` - Custom dashboard layouts

#### Telemetry (TimescaleDB)
- `telemetry_data` - Time-series device data (hypertable)
- `telemetry_data_1m` - 1-minute aggregates (continuous aggregate)
- `telemetry_data_5m` - 5-minute aggregates (continuous aggregate)
- `telemetry_data_1h` - 1-hour aggregates (continuous aggregate)
- `telemetry_data_1d` - 1-day aggregates (continuous aggregate)

#### Alerts
- `alerts` - Alert records
- `alert_rules` - Alert rule definitions

---

## Useful Queries

### Check Database Size
```sql
SELECT
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'solar_hub';
```

### List All Tables
```sql
SELECT schemaname, tablename, tableowner
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

### Check Table Row Counts
```sql
SELECT
    schemaname,
    tablename,
    n_live_tup AS row_count
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;
```

### View Dashboard Preferences
```sql
SELECT
    u.email,
    dp.layout_preset,
    dp.grid_layout,
    dp.created_at,
    dp.updated_at
FROM user_dashboard_preferences dp
JOIN users u ON u.id = dp.user_id
ORDER BY dp.updated_at DESC;
```

### View Custom Presets
```sql
SELECT
    u.email,
    cp.name,
    cp.description,
    cp.created_at
FROM user_custom_presets cp
JOIN users u ON u.id = cp.user_id
ORDER BY cp.created_at DESC;
```

### Check Active Users
```sql
SELECT
    email,
    first_name,
    last_name,
    role,
    status,
    created_at
FROM users
WHERE status = 'active'
ORDER BY created_at DESC;
```

---

## Backup & Restore

### Backup Database
```bash
PGPASSWORD=faisal pg_dump -h localhost -p 5433 -U postgres solar_hub > solar_hub_backup.sql
```

### Restore Database
```bash
PGPASSWORD=faisal psql -h localhost -p 5433 -U postgres solar_hub < solar_hub_backup.sql
```

### Backup Specific Table
```bash
PGPASSWORD=faisal pg_dump -h localhost -p 5433 -U postgres -t user_dashboard_preferences solar_hub > preferences_backup.sql
```

---

## Redis Credentials

### Connection Details
```
Host:     localhost
Port:     6379
Password: (none - no auth)
```

### redis-cli Command
```bash
redis-cli -h localhost -p 6379
```

### Python Connection (redis-py)
```python
import redis

r = redis.Redis(
    host='localhost',
    port=6379,
    decode_responses=True
)
```

---

## Environment Variables

For application configuration, set these environment variables:

```bash
# Database
DATABASE_URL=postgresql://postgres:faisal@localhost:5433/solar_hub

# Redis
REDIS_URL=redis://localhost:6379

# TimescaleDB (System B)
TIMESCALE_URL=postgresql://postgres:faisal@localhost:5433/solar_hub
```

---

## Security Notes

⚠️ **IMPORTANT:** These credentials are for local development only.

**For production:**
- Use strong, randomly generated passwords
- Store credentials in environment variables or secrets manager
- Never commit credentials to version control
- Use SSL/TLS for database connections
- Implement connection pooling
- Set up proper firewall rules
- Enable audit logging
- Regular security updates

---

## Maintenance Tasks

### Vacuum Database
```sql
VACUUM ANALYZE;
```

### Reindex Tables
```sql
REINDEX DATABASE solar_hub;
```

### Check Connection Count
```sql
SELECT count(*) as connections
FROM pg_stat_activity
WHERE datname = 'solar_hub';
```

### Kill Long-Running Queries
```sql
SELECT
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query
FROM pg_stat_activity
WHERE state != 'idle'
AND now() - pg_stat_activity.query_start > interval '5 minutes'
ORDER BY duration DESC;

-- Kill specific query
SELECT pg_terminate_backend(pid);
```

---

## Migration Management

### Check Migration Status (Alembic)
```bash
cd system_a
python -m alembic current
python -m alembic history
```

### Run Pending Migrations
```bash
cd system_a
python -m alembic upgrade head
```

### Rollback Migration
```bash
cd system_a
python -m alembic downgrade -1
```

---

**Generated:** 2026-01-29
**For:** Local Development Environment
**Security:** Development credentials only - DO NOT use in production
