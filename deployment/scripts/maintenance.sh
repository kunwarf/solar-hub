#!/bin/bash
#===============================================================================
# Solar Hub - Maintenance Script
# Common maintenance tasks for the Solar Hub platform
#===============================================================================

set -e

# Configuration
SOLARHUB_HOME="/opt/solarhub"
LOG_FILE="$SOLARHUB_HOME/logs/maintenance.log"

# Load environment
source "$SOLARHUB_HOME/app/.env" 2>/dev/null || true

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

#===============================================================================
# Service Management
#===============================================================================
service_status() {
    log_section "Service Status"

    echo ""
    echo "Core Services:"
    echo "----------------------------------------"
    for service in postgresql redis-server mosquitto nginx; do
        STATUS=$(systemctl is-active $service 2>/dev/null || echo "not found")
        if [ "$STATUS" == "active" ]; then
            echo -e "$service: ${GREEN}$STATUS${NC}"
        else
            echo -e "$service: ${RED}$STATUS${NC}"
        fi
    done

    echo ""
    echo "Application Services:"
    echo "----------------------------------------"
    for service in solarhub-platform solarhub-telemetry solarhub-worker; do
        STATUS=$(systemctl is-active $service 2>/dev/null || echo "not found")
        if [ "$STATUS" == "active" ]; then
            echo -e "$service: ${GREEN}$STATUS${NC}"
        else
            echo -e "$service: ${RED}$STATUS${NC}"
        fi
    done
}

restart_services() {
    log_section "Restarting Services"

    log "Restarting application services..."
    systemctl restart solarhub-platform
    systemctl restart solarhub-telemetry
    systemctl restart solarhub-worker 2>/dev/null || true

    log "Services restarted"
}

#===============================================================================
# Database Maintenance
#===============================================================================
vacuum_databases() {
    log_section "Vacuuming Databases"

    log "Vacuuming PostgreSQL..."
    PGPASSWORD="${DB_PASSWORD}" psql \
        -h "${DB_HOST:-127.0.0.1}" \
        -p "${DB_PORT:-5432}" \
        -U "${DB_USER:-solarhub_app}" \
        -d "${DB_NAME:-solar_hub}" \
        -c "VACUUM ANALYZE;"

    log "Vacuuming TimescaleDB..."
    PGPASSWORD="${TIMESCALE_PASSWORD}" psql \
        -h "${TIMESCALE_HOST:-127.0.0.1}" \
        -p "${TIMESCALE_PORT:-5432}" \
        -U "${TIMESCALE_USER:-solarhub_telemetry}" \
        -d "${TIMESCALE_NAME:-solar_hub_telemetry}" \
        -c "VACUUM ANALYZE;"

    log "Database maintenance completed"
}

db_stats() {
    log_section "Database Statistics"

    echo ""
    echo "PostgreSQL (System A):"
    echo "----------------------------------------"
    PGPASSWORD="${DB_PASSWORD}" psql \
        -h "${DB_HOST:-127.0.0.1}" \
        -p "${DB_PORT:-5432}" \
        -U "${DB_USER:-solarhub_app}" \
        -d "${DB_NAME:-solar_hub}" \
        -c "SELECT
            pg_size_pretty(pg_database_size('${DB_NAME:-solar_hub}')) as db_size,
            (SELECT count(*) FROM pg_stat_activity WHERE datname='${DB_NAME:-solar_hub}') as connections;"

    echo ""
    echo "TimescaleDB (System B):"
    echo "----------------------------------------"
    PGPASSWORD="${TIMESCALE_PASSWORD}" psql \
        -h "${TIMESCALE_HOST:-127.0.0.1}" \
        -p "${TIMESCALE_PORT:-5432}" \
        -U "${TIMESCALE_USER:-solarhub_telemetry}" \
        -d "${TIMESCALE_NAME:-solar_hub_telemetry}" \
        -c "SELECT
            pg_size_pretty(pg_database_size('${TIMESCALE_NAME:-solar_hub_telemetry}')) as db_size,
            (SELECT count(*) FROM pg_stat_activity WHERE datname='${TIMESCALE_NAME:-solar_hub_telemetry}') as connections;"

    echo ""
    echo "TimescaleDB Hypertable Info:"
    echo "----------------------------------------"
    PGPASSWORD="${TIMESCALE_PASSWORD}" psql \
        -h "${TIMESCALE_HOST:-127.0.0.1}" \
        -p "${TIMESCALE_PORT:-5432}" \
        -U "${TIMESCALE_USER:-solarhub_telemetry}" \
        -d "${TIMESCALE_NAME:-solar_hub_telemetry}" \
        -c "SELECT hypertable_name,
            pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) as size,
            num_chunks
            FROM timescaledb_information.hypertables;" 2>/dev/null || echo "No hypertables found"
}

#===============================================================================
# Log Management
#===============================================================================
rotate_logs() {
    log_section "Rotating Logs"

    logrotate -f /etc/logrotate.d/solarhub

    log "Logs rotated"
}

view_logs() {
    local SERVICE="$1"
    local LINES="${2:-100}"

    case "$SERVICE" in
        platform)
            tail -n "$LINES" "$SOLARHUB_HOME/logs/platform.log"
            ;;
        telemetry)
            tail -n "$LINES" "$SOLARHUB_HOME/logs/telemetry.log"
            ;;
        worker)
            tail -n "$LINES" "$SOLARHUB_HOME/logs/worker.log"
            ;;
        all)
            echo "=== Platform Logs ===" && tail -n 50 "$SOLARHUB_HOME/logs/platform.log"
            echo "=== Telemetry Logs ===" && tail -n 50 "$SOLARHUB_HOME/logs/telemetry.log"
            ;;
        *)
            echo "Usage: $0 logs [platform|telemetry|worker|all] [lines]"
            ;;
    esac
}

#===============================================================================
# Health Checks
#===============================================================================
health_check() {
    log_section "Health Check"

    echo ""
    echo "API Health:"
    echo "----------------------------------------"

    # Platform API
    PLATFORM_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo "000")
    if [ "$PLATFORM_HEALTH" == "200" ]; then
        echo -e "Platform API: ${GREEN}Healthy${NC}"
    else
        echo -e "Platform API: ${RED}Unhealthy (HTTP $PLATFORM_HEALTH)${NC}"
    fi

    # Telemetry API
    TELEMETRY_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/health 2>/dev/null || echo "000")
    if [ "$TELEMETRY_HEALTH" == "200" ]; then
        echo -e "Telemetry API: ${GREEN}Healthy${NC}"
    else
        echo -e "Telemetry API: ${RED}Unhealthy (HTTP $TELEMETRY_HEALTH)${NC}"
    fi

    echo ""
    echo "Database Connections:"
    echo "----------------------------------------"

    # PostgreSQL
    if PGPASSWORD="${DB_PASSWORD}" psql -h "${DB_HOST:-127.0.0.1}" -U "${DB_USER:-solarhub_app}" -d "${DB_NAME:-solar_hub}" -c "SELECT 1" &>/dev/null; then
        echo -e "PostgreSQL: ${GREEN}Connected${NC}"
    else
        echo -e "PostgreSQL: ${RED}Connection Failed${NC}"
    fi

    # TimescaleDB
    if PGPASSWORD="${TIMESCALE_PASSWORD}" psql -h "${TIMESCALE_HOST:-127.0.0.1}" -U "${TIMESCALE_USER:-solarhub_telemetry}" -d "${TIMESCALE_NAME:-solar_hub_telemetry}" -c "SELECT 1" &>/dev/null; then
        echo -e "TimescaleDB: ${GREEN}Connected${NC}"
    else
        echo -e "TimescaleDB: ${RED}Connection Failed${NC}"
    fi

    # Redis
    if redis-cli -a "${REDIS_PASSWORD}" --no-auth-warning ping &>/dev/null; then
        echo -e "Redis: ${GREEN}Connected${NC}"
    else
        echo -e "Redis: ${RED}Connection Failed${NC}"
    fi

    # MQTT
    if mosquitto_sub -h 127.0.0.1 -u solarhub -P "${PROTOCOL_MQTT_PASSWORD}" -t '#' -C 1 -W 1 &>/dev/null; then
        echo -e "MQTT: ${GREEN}Connected${NC}"
    else
        echo -e "MQTT: ${YELLOW}No Messages (Broker may be OK)${NC}"
    fi
}

#===============================================================================
# System Resources
#===============================================================================
system_stats() {
    log_section "System Resources"

    echo ""
    echo "Memory Usage:"
    echo "----------------------------------------"
    free -h

    echo ""
    echo "Disk Usage:"
    echo "----------------------------------------"
    df -h /opt/solarhub

    echo ""
    echo "CPU Load:"
    echo "----------------------------------------"
    uptime

    echo ""
    echo "Top Processes:"
    echo "----------------------------------------"
    ps aux --sort=-%mem | head -10
}

#===============================================================================
# SSL Certificate Management
#===============================================================================
check_ssl() {
    log_section "SSL Certificate Status"

    if [ -f "$SOLARHUB_HOME/ssl/server.crt" ]; then
        EXPIRY=$(openssl x509 -enddate -noout -in "$SOLARHUB_HOME/ssl/server.crt" | cut -d= -f2)
        echo "Certificate expires: $EXPIRY"

        # Check if expiring soon (within 30 days)
        EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
        NOW_EPOCH=$(date +%s)
        DAYS_LEFT=$(( ($EXPIRY_EPOCH - $NOW_EPOCH) / 86400 ))

        if [ $DAYS_LEFT -lt 30 ]; then
            echo -e "${YELLOW}WARNING: Certificate expires in $DAYS_LEFT days${NC}"
        else
            echo -e "${GREEN}Certificate valid for $DAYS_LEFT more days${NC}"
        fi
    else
        echo -e "${RED}No SSL certificate found${NC}"
    fi
}

renew_ssl() {
    log_section "Renewing SSL Certificate"

    # For Let's Encrypt
    if command -v certbot &> /dev/null; then
        certbot renew --quiet
        systemctl reload nginx
        log "SSL certificate renewed"
    else
        log_error "Certbot not installed. For Let's Encrypt, install certbot first."
    fi
}

#===============================================================================
# Usage
#===============================================================================
usage() {
    echo "Solar Hub Maintenance Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  status          Show service status"
    echo "  restart         Restart application services"
    echo "  health          Run health checks"
    echo "  stats           Show system statistics"
    echo "  db-stats        Show database statistics"
    echo "  vacuum          Run database vacuum"
    echo "  logs [service]  View logs (platform|telemetry|worker|all)"
    echo "  rotate-logs     Force log rotation"
    echo "  ssl-check       Check SSL certificate status"
    echo "  ssl-renew       Renew SSL certificate (Let's Encrypt)"
    echo "  help            Show this help message"
}

#===============================================================================
# Main
#===============================================================================
main() {
    case "$1" in
        status)
            service_status
            ;;
        restart)
            restart_services
            ;;
        health)
            health_check
            ;;
        stats)
            system_stats
            ;;
        db-stats)
            db_stats
            ;;
        vacuum)
            vacuum_databases
            ;;
        logs)
            view_logs "$2" "$3"
            ;;
        rotate-logs)
            rotate_logs
            ;;
        ssl-check)
            check_ssl
            ;;
        ssl-renew)
            renew_ssl
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

main "$@"
