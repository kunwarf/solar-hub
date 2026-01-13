#!/bin/bash
#===============================================================================
# Solar Hub - Deployment Script
# Pull latest code and redeploy
#===============================================================================

set -e

# Configuration
SOLARHUB_HOME="/opt/solarhub"
APP_DIR="$SOLARHUB_HOME/app"
VENV_DIR="$SOLARHUB_HOME/venv"
LOG_FILE="$SOLARHUB_HOME/logs/deploy.log"
BACKUP_BEFORE_DEPLOY=true

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

log_success() {
    echo -e "${GREEN}$1${NC}" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

#===============================================================================
# Pre-deployment Checks
#===============================================================================
pre_deploy_checks() {
    log_section "Pre-deployment Checks"

    # Check if running as solarhub user or root
    if [[ "$EUID" -ne 0 ]] && [[ "$(whoami)" != "solarhub" ]]; then
        log_error "Please run as root or solarhub user"
        exit 1
    fi

    # Check if app directory exists
    if [ ! -d "$APP_DIR" ]; then
        log_error "App directory not found: $APP_DIR"
        exit 1
    fi

    # Check if it's a git repository
    if [ ! -d "$APP_DIR/.git" ]; then
        log_error "Not a git repository: $APP_DIR"
        exit 1
    fi

    log "Pre-deployment checks passed"
}

#===============================================================================
# Backup Before Deploy
#===============================================================================
backup_before_deploy() {
    if [ "$BACKUP_BEFORE_DEPLOY" = true ]; then
        log_section "Creating Pre-deployment Backup"

        if [ -x "$SOLARHUB_HOME/scripts/backup.sh" ]; then
            "$SOLARHUB_HOME/scripts/backup.sh"
        else
            log_warn "Backup script not found, skipping backup"
        fi
    fi
}

#===============================================================================
# Pull Latest Code
#===============================================================================
pull_code() {
    log_section "Pulling Latest Code"

    cd "$APP_DIR"

    # Stash any local changes
    git stash --include-untracked 2>/dev/null || true

    # Fetch and pull
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    log "Current branch: $BRANCH"

    git fetch origin
    git pull origin "$BRANCH"

    # Show what changed
    log "Latest commit:"
    git log -1 --oneline

    log "Code updated successfully"
}

#===============================================================================
# Install Dependencies
#===============================================================================
install_dependencies() {
    log_section "Installing Dependencies"

    source "$VENV_DIR/bin/activate"

    # Upgrade pip
    pip install --upgrade pip wheel setuptools

    # Install dependencies
    if [ -f "$APP_DIR/system_a/requirements.txt" ]; then
        log "Installing System A dependencies..."
        pip install -r "$APP_DIR/system_a/requirements.txt"
    fi

    if [ -f "$APP_DIR/system_b/requirements.txt" ]; then
        log "Installing System B dependencies..."
        pip install -r "$APP_DIR/system_b/requirements.txt"
    fi

    log "Dependencies installed"
}

#===============================================================================
# Run Migrations
#===============================================================================
run_migrations() {
    log_section "Running Database Migrations"

    source "$VENV_DIR/bin/activate"
    source "$APP_DIR/.env" 2>/dev/null || true

    # System A migrations
    if [ -d "$APP_DIR/system_a/alembic" ]; then
        log "Running System A migrations..."
        cd "$APP_DIR/system_a"
        alembic upgrade head
    fi

    # System B migrations
    if [ -d "$APP_DIR/system_b/alembic" ]; then
        log "Running System B migrations..."
        cd "$APP_DIR/system_b"
        alembic upgrade head
    fi

    log "Migrations completed"
}

#===============================================================================
# Build Frontend
#===============================================================================
build_frontend() {
    log_section "Building Frontend"

    if [ -d "$APP_DIR/frontend" ] && [ -f "$APP_DIR/frontend/package.json" ]; then
        cd "$APP_DIR/frontend"

        if command -v npm &> /dev/null; then
            npm ci --production=false
            npm run build

            log "Frontend built successfully"
        else
            log_warn "npm not found, skipping frontend build"
        fi
    else
        log "No frontend directory found, skipping"
    fi
}

#===============================================================================
# Restart Services
#===============================================================================
restart_services() {
    log_section "Restarting Services"

    if [[ "$EUID" -eq 0 ]]; then
        systemctl restart solarhub-platform
        systemctl restart solarhub-telemetry
        systemctl restart solarhub-worker 2>/dev/null || true
    else
        log_warn "Not running as root, please restart services manually:"
        echo "  sudo systemctl restart solarhub-platform"
        echo "  sudo systemctl restart solarhub-telemetry"
        return
    fi

    # Wait for services to start
    sleep 5

    log "Services restarted"
}

#===============================================================================
# Health Check
#===============================================================================
post_deploy_health_check() {
    log_section "Post-deployment Health Check"

    local MAX_RETRIES=5
    local RETRY_DELAY=5

    for i in $(seq 1 $MAX_RETRIES); do
        log "Health check attempt $i/$MAX_RETRIES..."

        PLATFORM_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo "000")
        TELEMETRY_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/health 2>/dev/null || echo "000")

        if [ "$PLATFORM_HEALTH" == "200" ] && [ "$TELEMETRY_HEALTH" == "200" ]; then
            log_success "All services healthy!"
            return 0
        fi

        if [ $i -lt $MAX_RETRIES ]; then
            log "Services not ready, waiting ${RETRY_DELAY}s..."
            sleep $RETRY_DELAY
        fi
    done

    log_error "Health check failed after $MAX_RETRIES attempts"
    log "Platform API: HTTP $PLATFORM_HEALTH"
    log "Telemetry API: HTTP $TELEMETRY_HEALTH"
    return 1
}

#===============================================================================
# Rollback
#===============================================================================
rollback() {
    log_section "Rolling Back"

    cd "$APP_DIR"

    # Get previous commit
    PREV_COMMIT=$(git rev-parse HEAD~1)
    log "Rolling back to: $PREV_COMMIT"

    git checkout "$PREV_COMMIT"

    install_dependencies
    restart_services

    log "Rollback completed"
}

#===============================================================================
# Usage
#===============================================================================
usage() {
    echo "Solar Hub Deployment Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  deploy          Full deployment (pull, install, migrate, restart)"
    echo "  pull            Pull latest code only"
    echo "  install-deps    Install Python dependencies"
    echo "  migrate         Run database migrations"
    echo "  build-frontend  Build React frontend"
    echo "  restart         Restart services"
    echo "  health          Run health check"
    echo "  rollback        Rollback to previous commit"
    echo "  help            Show this help message"
    echo ""
    echo "Options:"
    echo "  --no-backup     Skip pre-deployment backup"
    echo ""
    echo "Examples:"
    echo "  $0 deploy"
    echo "  $0 deploy --no-backup"
    echo "  $0 rollback"
}

#===============================================================================
# Main
#===============================================================================
main() {
    # Parse options
    for arg in "$@"; do
        case $arg in
            --no-backup)
                BACKUP_BEFORE_DEPLOY=false
                shift
                ;;
        esac
    done

    case "$1" in
        deploy)
            log_section "Starting Full Deployment"
            log "Deployment started at $(date)"

            pre_deploy_checks
            backup_before_deploy
            pull_code
            install_dependencies
            run_migrations
            build_frontend
            restart_services
            post_deploy_health_check

            log_section "Deployment Complete"
            log_success "Deployment finished successfully at $(date)"
            ;;
        pull)
            pre_deploy_checks
            pull_code
            ;;
        install-deps)
            install_dependencies
            ;;
        migrate)
            run_migrations
            ;;
        build-frontend)
            build_frontend
            ;;
        restart)
            restart_services
            ;;
        health)
            post_deploy_health_check
            ;;
        rollback)
            pre_deploy_checks
            rollback
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
