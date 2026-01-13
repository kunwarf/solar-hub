#!/bin/bash
#===============================================================================
# Solar Hub - Database Restore Script
# Usage: ./restore.sh [postgres|timescale|redis|all] [backup_file]
#===============================================================================

set -e

# Configuration
BACKUP_DIR="/opt/solarhub/backups"
LOG_FILE="/opt/solarhub/logs/restore.log"

# Database credentials
source /opt/solarhub/app/.env 2>/dev/null || true

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}$(date '+%Y-%m-%d %H:%M:%S') - ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}$(date '+%Y-%m-%d %H:%M:%S') - SUCCESS: $1${NC}" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}$(date '+%Y-%m-%d %H:%M:%S') - WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

#===============================================================================
# List Available Backups
#===============================================================================
list_backups() {
    echo ""
    echo "Available PostgreSQL Backups:"
    echo "----------------------------------------"
    ls -lh "$BACKUP_DIR/postgres/"*.sql.gz 2>/dev/null | awk '{print NR": "$9" ("$5")"}'

    echo ""
    echo "Available TimescaleDB Backups:"
    echo "----------------------------------------"
    ls -lh "$BACKUP_DIR/timescale/"*.sql.gz 2>/dev/null | awk '{print NR": "$9" ("$5")"}'

    echo ""
    echo "Available Redis Backups:"
    echo "----------------------------------------"
    ls -lh "$BACKUP_DIR/redis/"*.rdb.gz 2>/dev/null | awk '{print NR": "$9" ("$5")"}'
    echo ""
}

#===============================================================================
# Restore PostgreSQL
#===============================================================================
restore_postgres() {
    local BACKUP_FILE="$1"

    if [ -z "$BACKUP_FILE" ]; then
        # Use latest backup
        BACKUP_FILE=$(ls -t "$BACKUP_DIR/postgres/"*.sql.gz 2>/dev/null | head -1)
    fi

    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "Backup file not found: $BACKUP_FILE"
        return 1
    fi

    log_warn "This will REPLACE all data in the solar_hub database!"
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        log "Restore cancelled"
        return 0
    fi

    log "Stopping services..."
    systemctl stop solarhub-platform 2>/dev/null || true

    log "Restoring PostgreSQL from: $BACKUP_FILE"

    # Drop and recreate database
    PGPASSWORD="${DB_PASSWORD}" psql \
        -h "${DB_HOST:-127.0.0.1}" \
        -p "${DB_PORT:-5432}" \
        -U "${DB_USER:-solarhub_app}" \
        -d postgres \
        -c "DROP DATABASE IF EXISTS ${DB_NAME:-solar_hub};" \
        -c "CREATE DATABASE ${DB_NAME:-solar_hub} OWNER ${DB_USER:-solarhub_app};"

    # Restore backup
    PGPASSWORD="${DB_PASSWORD}" pg_restore \
        -h "${DB_HOST:-127.0.0.1}" \
        -p "${DB_PORT:-5432}" \
        -U "${DB_USER:-solarhub_app}" \
        -d "${DB_NAME:-solar_hub}" \
        --verbose \
        "$BACKUP_FILE" 2>> "$LOG_FILE"

    if [ $? -eq 0 ]; then
        log_success "PostgreSQL restored successfully"
        log "Starting services..."
        systemctl start solarhub-platform 2>/dev/null || true
    else
        log_error "PostgreSQL restore failed"
        return 1
    fi
}

#===============================================================================
# Restore TimescaleDB
#===============================================================================
restore_timescale() {
    local BACKUP_FILE="$1"

    if [ -z "$BACKUP_FILE" ]; then
        BACKUP_FILE=$(ls -t "$BACKUP_DIR/timescale/"*.sql.gz 2>/dev/null | head -1)
    fi

    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "Backup file not found: $BACKUP_FILE"
        return 1
    fi

    log_warn "This will REPLACE all data in the solar_hub_telemetry database!"
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        log "Restore cancelled"
        return 0
    fi

    log "Stopping services..."
    systemctl stop solarhub-telemetry solarhub-worker 2>/dev/null || true

    log "Restoring TimescaleDB from: $BACKUP_FILE"

    # Drop and recreate database
    PGPASSWORD="${TIMESCALE_PASSWORD}" psql \
        -h "${TIMESCALE_HOST:-127.0.0.1}" \
        -p "${TIMESCALE_PORT:-5432}" \
        -U "${TIMESCALE_USER:-solarhub_telemetry}" \
        -d postgres \
        -c "DROP DATABASE IF EXISTS ${TIMESCALE_NAME:-solar_hub_telemetry};" \
        -c "CREATE DATABASE ${TIMESCALE_NAME:-solar_hub_telemetry} OWNER ${TIMESCALE_USER:-solarhub_telemetry};"

    # Enable TimescaleDB extension
    PGPASSWORD="${TIMESCALE_PASSWORD}" psql \
        -h "${TIMESCALE_HOST:-127.0.0.1}" \
        -p "${TIMESCALE_PORT:-5432}" \
        -U "${TIMESCALE_USER:-solarhub_telemetry}" \
        -d "${TIMESCALE_NAME:-solar_hub_telemetry}" \
        -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

    # Restore backup
    PGPASSWORD="${TIMESCALE_PASSWORD}" pg_restore \
        -h "${TIMESCALE_HOST:-127.0.0.1}" \
        -p "${TIMESCALE_PORT:-5432}" \
        -U "${TIMESCALE_USER:-solarhub_telemetry}" \
        -d "${TIMESCALE_NAME:-solar_hub_telemetry}" \
        --verbose \
        "$BACKUP_FILE" 2>> "$LOG_FILE"

    if [ $? -eq 0 ]; then
        log_success "TimescaleDB restored successfully"
        log "Starting services..."
        systemctl start solarhub-telemetry solarhub-worker 2>/dev/null || true
    else
        log_error "TimescaleDB restore failed"
        return 1
    fi
}

#===============================================================================
# Restore Redis
#===============================================================================
restore_redis() {
    local BACKUP_FILE="$1"

    if [ -z "$BACKUP_FILE" ]; then
        BACKUP_FILE=$(ls -t "$BACKUP_DIR/redis/"*.rdb.gz 2>/dev/null | head -1)
    fi

    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "Backup file not found: $BACKUP_FILE"
        return 1
    fi

    log_warn "This will REPLACE all Redis data!"
    read -p "Are you sure you want to continue? (yes/no): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        log "Restore cancelled"
        return 0
    fi

    log "Stopping Redis..."
    systemctl stop redis-server

    log "Restoring Redis from: $BACKUP_FILE"

    # Decompress and copy
    gunzip -c "$BACKUP_FILE" > /var/lib/redis/dump.rdb
    chown redis:redis /var/lib/redis/dump.rdb

    log "Starting Redis..."
    systemctl start redis-server

    log_success "Redis restored successfully"
}

#===============================================================================
# Usage
#===============================================================================
usage() {
    echo "Usage: $0 [command] [backup_file]"
    echo ""
    echo "Commands:"
    echo "  list              List available backups"
    echo "  postgres [file]   Restore PostgreSQL database"
    echo "  timescale [file]  Restore TimescaleDB database"
    echo "  redis [file]      Restore Redis data"
    echo "  all               Restore all databases (latest backups)"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 postgres /opt/solarhub/backups/postgres/solar_hub_20240115.sql.gz"
    echo "  $0 all"
}

#===============================================================================
# Main
#===============================================================================
main() {
    case "$1" in
        list)
            list_backups
            ;;
        postgres)
            restore_postgres "$2"
            ;;
        timescale)
            restore_timescale "$2"
            ;;
        redis)
            restore_redis "$2"
            ;;
        all)
            restore_postgres
            restore_timescale
            restore_redis
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
