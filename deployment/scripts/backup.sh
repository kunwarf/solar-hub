#!/bin/bash
#===============================================================================
# Solar Hub - Database Backup Script
# Run daily via cron: 0 2 * * * /opt/solarhub/scripts/backup.sh
#===============================================================================

set -e

# Configuration
BACKUP_DIR="/opt/solarhub/backups"
RETENTION_DAYS=30
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/opt/solarhub/logs/backup.log"

# Database credentials (loaded from environment or .env file)
source /opt/solarhub/app/.env 2>/dev/null || true

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
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

# Create backup directories
mkdir -p "$BACKUP_DIR"/{postgres,timescale,redis,daily,weekly,monthly}

#===============================================================================
# PostgreSQL Backup (System A)
#===============================================================================
backup_postgres() {
    log "Starting PostgreSQL backup..."

    POSTGRES_BACKUP="$BACKUP_DIR/postgres/solar_hub_${DATE}.sql.gz"

    PGPASSWORD="${DB_PASSWORD}" pg_dump \
        -h "${DB_HOST:-127.0.0.1}" \
        -p "${DB_PORT:-5432}" \
        -U "${DB_USER:-solarhub_app}" \
        -d "${DB_NAME:-solar_hub}" \
        --format=custom \
        --compress=9 \
        --verbose \
        -f "$POSTGRES_BACKUP" 2>> "$LOG_FILE"

    if [ $? -eq 0 ]; then
        SIZE=$(du -h "$POSTGRES_BACKUP" | cut -f1)
        log_success "PostgreSQL backup completed: $POSTGRES_BACKUP ($SIZE)"
    else
        log_error "PostgreSQL backup failed"
        return 1
    fi
}

#===============================================================================
# TimescaleDB Backup (System B - Telemetry)
#===============================================================================
backup_timescale() {
    log "Starting TimescaleDB backup..."

    TIMESCALE_BACKUP="$BACKUP_DIR/timescale/solar_hub_telemetry_${DATE}.sql.gz"

    PGPASSWORD="${TIMESCALE_PASSWORD}" pg_dump \
        -h "${TIMESCALE_HOST:-127.0.0.1}" \
        -p "${TIMESCALE_PORT:-5432}" \
        -U "${TIMESCALE_USER:-solarhub_telemetry}" \
        -d "${TIMESCALE_NAME:-solar_hub_telemetry}" \
        --format=custom \
        --compress=9 \
        --verbose \
        -f "$TIMESCALE_BACKUP" 2>> "$LOG_FILE"

    if [ $? -eq 0 ]; then
        SIZE=$(du -h "$TIMESCALE_BACKUP" | cut -f1)
        log_success "TimescaleDB backup completed: $TIMESCALE_BACKUP ($SIZE)"
    else
        log_error "TimescaleDB backup failed"
        return 1
    fi
}

#===============================================================================
# Redis Backup
#===============================================================================
backup_redis() {
    log "Starting Redis backup..."

    REDIS_BACKUP="$BACKUP_DIR/redis/dump_${DATE}.rdb"

    # Trigger BGSAVE
    redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning BGSAVE 2>> "$LOG_FILE"

    # Wait for background save to complete
    while [ "$(redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning LASTSAVE)" == "$(redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning LASTSAVE)" ]; do
        sleep 1
    done

    # Copy the dump file
    cp /var/lib/redis/dump.rdb "$REDIS_BACKUP"
    gzip "$REDIS_BACKUP"

    if [ $? -eq 0 ]; then
        SIZE=$(du -h "${REDIS_BACKUP}.gz" | cut -f1)
        log_success "Redis backup completed: ${REDIS_BACKUP}.gz ($SIZE)"
    else
        log_error "Redis backup failed"
        return 1
    fi
}

#===============================================================================
# Backup Rotation
#===============================================================================
rotate_backups() {
    log "Rotating old backups..."

    # Remove backups older than retention period
    find "$BACKUP_DIR/postgres" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR/timescale" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR/redis" -name "*.rdb.gz" -mtime +$RETENTION_DAYS -delete

    # Create weekly backup (on Sundays)
    if [ "$(date +%u)" -eq 7 ]; then
        log "Creating weekly backup archive..."
        WEEKLY_ARCHIVE="$BACKUP_DIR/weekly/solarhub_weekly_${DATE}.tar.gz"
        tar -czf "$WEEKLY_ARCHIVE" \
            "$BACKUP_DIR/postgres/solar_hub_${DATE}.sql.gz" \
            "$BACKUP_DIR/timescale/solar_hub_telemetry_${DATE}.sql.gz" \
            "$BACKUP_DIR/redis/dump_${DATE}.rdb.gz" 2>/dev/null || true

        # Keep only last 4 weekly backups
        find "$BACKUP_DIR/weekly" -name "*.tar.gz" -mtime +28 -delete
    fi

    # Create monthly backup (on 1st of month)
    if [ "$(date +%d)" -eq 01 ]; then
        log "Creating monthly backup archive..."
        MONTHLY_ARCHIVE="$BACKUP_DIR/monthly/solarhub_monthly_${DATE}.tar.gz"
        tar -czf "$MONTHLY_ARCHIVE" \
            "$BACKUP_DIR/postgres/solar_hub_${DATE}.sql.gz" \
            "$BACKUP_DIR/timescale/solar_hub_telemetry_${DATE}.sql.gz" \
            "$BACKUP_DIR/redis/dump_${DATE}.rdb.gz" 2>/dev/null || true

        # Keep only last 12 monthly backups
        find "$BACKUP_DIR/monthly" -name "*.tar.gz" -mtime +365 -delete
    fi

    log_success "Backup rotation completed"
}

#===============================================================================
# Calculate Backup Statistics
#===============================================================================
show_stats() {
    log "Backup Statistics:"
    echo "----------------------------------------"
    echo "PostgreSQL backups: $(ls -1 $BACKUP_DIR/postgres/*.sql.gz 2>/dev/null | wc -l)"
    echo "TimescaleDB backups: $(ls -1 $BACKUP_DIR/timescale/*.sql.gz 2>/dev/null | wc -l)"
    echo "Redis backups: $(ls -1 $BACKUP_DIR/redis/*.rdb.gz 2>/dev/null | wc -l)"
    echo "Weekly archives: $(ls -1 $BACKUP_DIR/weekly/*.tar.gz 2>/dev/null | wc -l)"
    echo "Monthly archives: $(ls -1 $BACKUP_DIR/monthly/*.tar.gz 2>/dev/null | wc -l)"
    echo "Total backup size: $(du -sh $BACKUP_DIR | cut -f1)"
    echo "----------------------------------------"
}

#===============================================================================
# Main
#===============================================================================
main() {
    log "=========================================="
    log "Starting Solar Hub Backup"
    log "=========================================="

    backup_postgres
    backup_timescale
    backup_redis
    rotate_backups
    show_stats

    log "=========================================="
    log "Backup completed successfully"
    log "=========================================="
}

main "$@"
