#!/bin/bash
#===============================================================================
# Solar Hub - Production Server Setup Script
# For Debian 11/12 with 64GB RAM, 24+ CPU cores
#
# RAID Configuration:
# To use RAID arrays for data storage, set the following variables before running:
#   POSTGRES_DATA_DIR="/mnt/raid/postgresql"   # PostgreSQL data directory
#   REDIS_DATA_DIR="/mnt/raid/redis"           # Redis data directory  
#   MOSQUITTO_DATA_DIR="/mnt/raid/mosquitto"   # Mosquitto data directory
# 
# Example: export POSTGRES_DATA_DIR="/mnt/raid/postgresql" && ./setup-server.sh
# Or edit the variables in the Configuration section below.
#===============================================================================
if ! grep -qi debian /etc/os-release; then
  echo "[ERROR] This installer supports Debian only"
  exit 1
fi

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SOLARHUB_USER="solarhub"
SOLARHUB_HOME="/opt/solarhub"
SOLARHUB_REPO="https://github.com/YOUR_USERNAME/solar-hub.git"  # Update this
POSTGRES_VERSION="16"
REDIS_VERSION="7"

# Data Directory Configuration (for RAID arrays)
# Set these to point to your RAID mount points, or leave empty to use defaults
# Example: POSTGRES_DATA_DIR="/mnt/raid/postgresql"
# Example: REDIS_DATA_DIR="/mnt/raid/redis"
# Example: MOSQUITTO_DATA_DIR="/mnt/raid/mosquitto"
# Default: Auto-detect RAID mount points (md1, md0, or common mount locations)
# Note: This auto-detection happens at script start, you can override by setting variables before running

RAID_MOUNT=""

# Function to detect RAID mount point
detect_raid_mount() {
    # Check for md1 (RAID1) - typically the faster/faster array
    if [ -b /dev/md1 ]; then
        # Find where md1 is mounted
        MD1_MOUNT=$(mount | grep "/dev/md1" | awk '{print $3}' | head -1)
        if [ -n "$MD1_MOUNT" ] && [ -d "$MD1_MOUNT" ] && mountpoint -q "$MD1_MOUNT" 2>/dev/null; then
            RAID_MOUNT="$MD1_MOUNT"
            return 0
        fi
    fi
    
    # Check for md0 (RAID1) as fallback
    if [ -b /dev/md0 ]; then
        MD0_MOUNT=$(mount | grep "/dev/md0" | awk '{print $3}' | head -1)
        if [ -n "$MD0_MOUNT" ] && [ -d "$MD0_MOUNT" ] && mountpoint -q "$MD0_MOUNT" 2>/dev/null; then
            RAID_MOUNT="$MD0_MOUNT"
            return 0
        fi
    fi
    
    # Check common mount points
    for mount_point in /mnt/md1 /mnt/raid /mnt/storage /mnt/data; do
        if [ -d "$mount_point" ] && mountpoint -q "$mount_point" 2>/dev/null; then
            # Verify it's actually a RAID device
            if mount | grep -q "$mount_point.*md[0-9]"; then
                RAID_MOUNT="$mount_point"
                return 0
            fi
        fi
    done
    
    return 1
}

# Detect RAID mount point
if detect_raid_mount; then
    POSTGRES_DATA_DIR="$RAID_MOUNT/postgresql"   # RAID array location
    REDIS_DATA_DIR="$RAID_MOUNT/redis"           # RAID array location
    MOSQUITTO_DATA_DIR="$RAID_MOUNT/mosquitto"   # RAID array location
else
    POSTGRES_DATA_DIR=""  # Leave empty for default: /var/lib/postgresql
    REDIS_DATA_DIR=""     # Leave empty for default: /var/lib/redis
    MOSQUITTO_DATA_DIR="" # Leave empty for default: /var/lib/mosquitto
fi

# Logging
LOG_FILE="/var/log/solarhub-setup.log"
exec 1> >(tee -a "$LOG_FILE") 2>&1

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}================================================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}================================================================${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root"
        exit 1
    fi
}

# Get server IP
get_server_ip() {
    SERVER_IP=$(hostname -I | awk '{print $1}')
    log_info "Server IP: $SERVER_IP"
}

#===============================================================================
# System Update and Basic Packages
#===============================================================================
setup_system() {
    log_section "Updating System and Installing Base Packages"

    # Clean up any conflicting Docker repository configurations before updating package lists
    log_info "Cleaning up any conflicting repository configurations..."
    
    # Remove all Docker-related repository files (both .list and .sources formats)
    rm -f /etc/apt/sources.list.d/docker*.list
    rm -f /etc/apt/sources.list.d/docker*.list.save
    rm -f /etc/apt/sources.list.d/docker*.list.dpkg-old
    rm -f /etc/apt/sources.list.d/docker*.list.dpkg-dist
    rm -f /etc/apt/sources.list.d/docker*.sources
    rm -f /etc/apt/sources.list.d/omvdocker.sources  # OpenMediaVault Docker sources
    
    # Remove all Docker GPG keys from various locations
    rm -f /etc/apt/keyrings/docker.asc
    rm -f /etc/apt/keyrings/docker.gpg
    rm -f /usr/share/keyrings/docker*.asc
    rm -f /usr/share/keyrings/docker*.gpg
    rm -f /etc/apt/trusted.gpg.d/docker*.gpg
    rm -f /etc/apt/trusted.gpg.d/docker*.asc
    
    # Remove Docker entries from main sources.list
    if [ -f /etc/apt/sources.list ]; then
        sed -i '/download\.docker\.com/d' /etc/apt/sources.list 2>/dev/null || true
        sed -i '/docker\.com/d' /etc/apt/sources.list 2>/dev/null || true
    fi
    
    # Remove Docker entries from any other sources files (.list format)
    find /etc/apt/sources.list.d/ -type f -name "*.list" -exec sed -i '/download\.docker\.com/d' {} \; 2>/dev/null || true
    find /etc/apt/sources.list.d/ -type f -name "*.list" -exec sed -i '/docker\.com/d' {} \; 2>/dev/null || true
    
    # Remove any .sources files that contain Docker references
    for sources_file in /etc/apt/sources.list.d/*.sources; do
        [ ! -e "$sources_file" ] && continue
        if grep -qi "docker\|download.docker.com" "$sources_file" 2>/dev/null; then
            log_warn "Removing Docker .sources file: $sources_file"
            rm -f "$sources_file"
        fi
    done
    
    log_info "Repository cleanup completed"

    # Update package lists with retry logic
    log_info "Updating package lists..."
    if ! apt-get update 2>&1 | tee /tmp/apt-update-error.log; then
        log_error "Failed to update package lists. Trying again..."
        sleep 2
        if ! apt-get update 2>&1 | tee -a /tmp/apt-update-error.log; then
            log_error "Package list update failed after cleanup attempts."
            log_error "Please manually fix Docker repository conflicts:"
            log_error "  rm -f /etc/apt/sources.list.d/docker*.list*"
            log_error "  rm -f /etc/apt/keyrings/docker* /usr/share/keyrings/docker*"
            log_error "  sed -i '/docker\.com/d' /etc/apt/sources.list"
            log_error "  apt-get update"
            log_error "Error details saved to /tmp/apt-update-error.log"
            exit 1
        fi
    fi
    rm -f /tmp/apt-update-error.log

    # Upgrade system packages (non-interactive)
    log_info "Upgrading system packages..."
    DEBIAN_FRONTEND=noninteractive apt-get upgrade -y || log_warn "Some packages could not be upgraded"

    # Install essential packages first (required for repository operations)
    log_info "Installing essential packages..."
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        gnupg \
        lsb-release \
        ca-certificates \
        apt-transport-https \
        git

    # Note: software-properties-common is not required and may not be available in all Debian versions
    # It's only needed for adding PPAs, which we don't use in this script

    # Install remaining packages
    log_info "Installing remaining system packages..."
    apt-get install -y \
        htop \
        iotop \
        net-tools \
        vim \
        nano \
        unzip \
        jq \
        fail2ban \
        ufw \
        logrotate \
        cron \
        acl \
        python3 \
        python3-pip \
        python3-venv \
        build-essential \
        libpq-dev \
        libffi-dev \
        libssl-dev || {
        log_error "Failed to install some packages"
        exit 1
    }

    log_info "System packages installed successfully"
}

#===============================================================================
# Create Application User
#===============================================================================
create_user() {
    log_section "Creating Application User"

    if id "$SOLARHUB_USER" &>/dev/null; then
        log_warn "User $SOLARHUB_USER already exists"
    else
        useradd -r -m -d "$SOLARHUB_HOME" -s /bin/bash "$SOLARHUB_USER"
        log_info "User $SOLARHUB_USER created"
    fi

    # Create directory structure
    mkdir -p "$SOLARHUB_HOME"/{app,data,logs,backups,ssl}
    mkdir -p "$SOLARHUB_HOME"/data/{postgres,timescale,redis,mosquitto}

    chown -R "$SOLARHUB_USER":"$SOLARHUB_USER" "$SOLARHUB_HOME"

    log_info "Directory structure created at $SOLARHUB_HOME"
}

#===============================================================================
# Install Docker
#===============================================================================
install_docker() {
    log_section "Installing Docker"

    if command -v docker &> /dev/null; then
        log_warn "Docker already installed"
        docker --version
    else
        # Clean up any existing Docker repository configurations to avoid conflicts
        log_info "Cleaning up any existing Docker repository configurations..."
        
        # Remove all Docker-related repository files (both .list and .sources formats)
        rm -f /etc/apt/sources.list.d/docker*.list
        rm -f /etc/apt/sources.list.d/docker*.list.save
        rm -f /etc/apt/sources.list.d/docker*.list.dpkg-old
        rm -f /etc/apt/sources.list.d/docker*.list.dpkg-dist
        rm -f /etc/apt/sources.list.d/docker*.sources
        rm -f /etc/apt/sources.list.d/omvdocker.sources  # OpenMediaVault Docker sources
        
        # Remove all Docker GPG keys from various locations
        rm -f /etc/apt/keyrings/docker.asc
        rm -f /etc/apt/keyrings/docker.gpg
        rm -f /usr/share/keyrings/docker*.asc
        rm -f /usr/share/keyrings/docker*.gpg
        rm -f /etc/apt/trusted.gpg.d/docker*.gpg
        rm -f /etc/apt/trusted.gpg.d/docker*.asc
        
        # Remove Docker entries from main sources.list
        if [ -f /etc/apt/sources.list ]; then
            sed -i '/download\.docker\.com/d' /etc/apt/sources.list 2>/dev/null || true
            sed -i '/docker\.com/d' /etc/apt/sources.list 2>/dev/null || true
        fi
        
        # Remove Docker entries from any other sources files (.list format)
        find /etc/apt/sources.list.d/ -type f -name "*.list" -exec sed -i '/download\.docker\.com/d' {} \; 2>/dev/null || true
        find /etc/apt/sources.list.d/ -type f -name "*.list" -exec sed -i '/docker\.com/d' {} \; 2>/dev/null || true
        
        # Remove any .sources files that contain Docker references
        for sources_file in /etc/apt/sources.list.d/*.sources; do
            [ ! -e "$sources_file" ] && continue
            if grep -qi "docker\|download.docker.com" "$sources_file" 2>/dev/null; then
                log_warn "Removing Docker .sources file: $sources_file"
                rm -f "$sources_file"
            fi
        done
        
        # Remove any entries that reference the old keyring location
        find /etc/apt/sources.list.d/ -type f -name "*.list" -exec sed -i '/usr\/share\/keyrings\/docker/d' {} \; 2>/dev/null || true
        find /etc/apt/sources.list.d/ -type f -name "*.list" -exec sed -i '/signed-by.*docker/d' {} \; 2>/dev/null || true
        
        # Verify no Docker entries remain
        if grep -r "docker.com" /etc/apt/sources.list.d/ 2>/dev/null || grep "docker.com" /etc/apt/sources.list 2>/dev/null; then
            log_warn "Some Docker repository entries may still exist, attempting additional cleanup..."
            find /etc/apt/sources.list.d/ -type f -exec sed -i '/docker/d' {} \; 2>/dev/null || true
        fi
        
        # Final verification - check for any signed-by references to old keyring
        if grep -r "signed-by.*docker\|usr/share/keyrings/docker" /etc/apt/sources.list.d/ 2>/dev/null; then
            log_warn "Found Docker keyring references, removing affected files..."
            grep -rl "signed-by.*docker\|usr/share/keyrings/docker" /etc/apt/sources.list.d/ 2>/dev/null | xargs rm -f 2>/dev/null || true
        fi
        
        # Aggressive cleanup: Remove ANY file that contains docker.com or docker references
        log_info "Performing aggressive cleanup of Docker references..."
        for file in /etc/apt/sources.list.d/*.list* /etc/apt/sources.list.d/*.save /etc/apt/sources.list.d/*.sources; do
            [ ! -e "$file" ] && continue  # Skip if file doesn't exist
            if [ -f "$file" ] && grep -qi "docker\|download.docker.com" "$file" 2>/dev/null; then
                log_warn "Removing file with Docker references: $file"
                rm -f "$file"
            fi
        done
        
        # Also check for any files with the old keyring path
        for file in /etc/apt/sources.list.d/*; do
            [ ! -e "$file" ] && continue  # Skip if file doesn't exist
            if [ -f "$file" ] && grep -q "usr/share/keyrings/docker" "$file" 2>/dev/null; then
                log_warn "Removing file with old Docker keyring reference: $file"
                rm -f "$file"
            fi
        done
        
        # Clear apt cache to ensure no stale repository info
        rm -rf /var/lib/apt/lists/partial/* 2>/dev/null || true

        # Add Docker's official GPG key
        log_info "Adding Docker's official GPG key..."
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
        chmod a+r /etc/apt/keyrings/docker.asc

        # Remove our docker.list if it exists (we'll recreate it cleanly)
        rm -f /etc/apt/sources.list.d/docker.list
        
        # Add repository
        log_info "Adding Docker repository..."
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
          $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
          tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Ensure the file has correct permissions
        chmod 644 /etc/apt/sources.list.d/docker.list

        # Verify no conflicting Docker entries exist
        log_info "Verifying no conflicting Docker entries..."
        if grep -r "download.docker.com" /etc/apt/sources.list.d/ 2>/dev/null | grep -v "docker.list" | grep -v "signed-by=/etc/apt/keyrings/docker.asc"; then
            log_warn "Found conflicting Docker repository entries:"
            grep -r "download.docker.com" /etc/apt/sources.list.d/ 2>/dev/null | grep -v "docker.list" || true
            log_warn "Removing conflicting entries..."
            grep -rl "download.docker.com" /etc/apt/sources.list.d/ 2>/dev/null | grep -v "docker.list" | xargs rm -f 2>/dev/null || true
        fi
        
        # Check for any references to old keyring location
        if grep -r "usr/share/keyrings/docker" /etc/apt/sources.list.d/ 2>/dev/null; then
            log_error "Found references to old Docker keyring location:"
            grep -r "usr/share/keyrings/docker" /etc/apt/sources.list.d/ 2>/dev/null || true
            log_error "Removing files with old keyring references..."
            grep -rl "usr/share/keyrings/docker" /etc/apt/sources.list.d/ 2>/dev/null | xargs rm -f 2>/dev/null || true
        fi
        
        # Comprehensive check: List all repository files and their Docker-related content
        log_info "Checking all repository files for Docker references..."
        for file in /etc/apt/sources.list.d/*.list* /etc/apt/sources.list.d/*.sources /etc/apt/sources.list; do
            [ ! -e "$file" ] && continue  # Skip if file doesn't exist
            if [ -f "$file" ]; then
                if grep -qi "docker\|download.docker.com" "$file" 2>/dev/null; then
                    log_warn "Found Docker reference in $file:"
                    grep -i "docker\|download.docker.com" "$file" 2>/dev/null || true
                    # If it's not our new docker.list file, remove it
                    if [ "$file" != "/etc/apt/sources.list.d/docker.list" ] && [ "$file" != "/etc/apt/sources.list.d/docker.list.save" ]; then
                        log_warn "Removing conflicting file: $file"
                        rm -f "$file"
                    fi
                fi
            fi
        done
        
        # Final check: Remove ANY file that has signed-by pointing to old keyring
        log_info "Final check for old keyring references..."
        for file in /etc/apt/sources.list.d/*; do
            [ ! -e "$file" ] && continue  # Skip if file doesn't exist
            if [ -f "$file" ] && grep -q "signed-by.*usr/share/keyrings/docker" "$file" 2>/dev/null; then
                log_error "Found file with old keyring signed-by: $file"
                cat "$file" || true
                rm -f "$file"
            fi
        done
        
        # Use apt-config to check what apt sees (if available)
        if command -v apt-config &>/dev/null; then
            log_info "Checking apt configuration for Docker repositories..."
            apt-config dump | grep -i docker || log_info "No Docker entries in apt-config"
        fi
        
        # List all .list files to verify
        log_info "Repository files after cleanup:"
        ls -la /etc/apt/sources.list.d/*.list 2>/dev/null || true

        # Update package lists
        log_info "Updating package lists..."
        if ! apt-get update 2>&1 | tee /tmp/docker-apt-update.log; then
            log_error "Failed to update package lists after Docker repository setup."
            log_error "Checking for remaining conflicts..."
            echo "=== All files in sources.list.d ==="
            ls -la /etc/apt/sources.list.d/ 2>/dev/null || true
            echo "=== Docker references in all files ==="
            grep -r "docker" /etc/apt/sources.list.d/ 2>/dev/null || true
            grep "docker" /etc/apt/sources.list 2>/dev/null || true
            echo "=== Contents of docker.list ==="
            cat /etc/apt/sources.list.d/docker.list 2>/dev/null || true
            echo "=== Full error log ==="
            cat /tmp/docker-apt-update.log 2>/dev/null || true
            log_error "Please manually remove all Docker repository files and try again"
            exit 1
        fi
        rm -f /tmp/docker-apt-update.log

        # Install Docker
        log_info "Installing Docker..."
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

        # Add user to docker group
        usermod -aG docker "$SOLARHUB_USER"

        log_info "Docker installed successfully"
    fi

    # Start and enable Docker
    systemctl start docker
    systemctl enable docker

    # Configure Docker daemon for production
    cat > /etc/docker/daemon.json <<EOF
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "100m",
        "max-file": "5"
    },
    "storage-driver": "overlay2",
    "live-restore": true,
    "default-ulimits": {
        "nofile": {
            "Name": "nofile",
            "Hard": 65536,
            "Soft": 65536
        }
    }
}
EOF

    systemctl restart docker
    log_info "Docker configured for production"
}

#===============================================================================
# Install PostgreSQL with TimescaleDB
#===============================================================================
install_postgresql() {
    log_section "Installing PostgreSQL $POSTGRES_VERSION with TimescaleDB"

    # Add PostgreSQL repository (using modern method without apt-key)
    log_info "Adding PostgreSQL repository..."
    install -m 0755 -d /etc/apt/keyrings
    wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg
    chmod a+r /etc/apt/keyrings/postgresql.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list

    # Add TimescaleDB repository (using modern method without apt-key)
    log_info "Adding TimescaleDB repository..."
    wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | gpg --dearmor -o /etc/apt/keyrings/timescaledb.gpg
    chmod a+r /etc/apt/keyrings/timescaledb.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/timescaledb.gpg] https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/timescaledb.list

    apt-get update
    apt-get install -y postgresql-$POSTGRES_VERSION timescaledb-2-postgresql-$POSTGRES_VERSION timescaledb-tools
    
    # Configure custom data directory for PostgreSQL if specified
    if [ -n "$POSTGRES_DATA_DIR" ]; then
        # Check if parent directory (mount point) exists
        PARENT_DIR=$(dirname "$POSTGRES_DATA_DIR")
        if [ ! -d "$PARENT_DIR" ]; then
            log_warn "Parent directory $PARENT_DIR does not exist, skipping custom PostgreSQL data directory"
        else
        log_info "Configuring PostgreSQL to use custom data directory: $POSTGRES_DATA_DIR"
        systemctl stop postgresql
        
        # Create data directory structure
        mkdir -p "$POSTGRES_DATA_DIR/$POSTGRES_VERSION/main"
        chown -R postgres:postgres "$POSTGRES_DATA_DIR"
        chmod 700 "$POSTGRES_DATA_DIR/$POSTGRES_VERSION/main"
        
        # Check current data directory location
        CURRENT_DATA_DIR=$(grep "^data_directory" /etc/postgresql/$POSTGRES_VERSION/main/postgresql.conf 2>/dev/null | cut -d"'" -f2)
        DEFAULT_DATA_DIR="/var/lib/postgresql/$POSTGRES_VERSION/main"
        
        # Use current location if configured, otherwise use default
        SOURCE_DIR="${CURRENT_DATA_DIR:-$DEFAULT_DATA_DIR}"
        
        # Move existing data if source location has data
        if [ -d "$SOURCE_DIR" ] && [ -f "$SOURCE_DIR/PG_VERSION" ]; then
            log_info "Migrating existing PostgreSQL data from $SOURCE_DIR to RAID..."
            log_info "This may take a while depending on database size..."
            
            # Copy data with proper permissions
            sudo -u postgres rsync -av "$SOURCE_DIR/" "$POSTGRES_DATA_DIR/$POSTGRES_VERSION/main/" 2>/dev/null || \
            sudo -u postgres cp -a "$SOURCE_DIR"/* "$POSTGRES_DATA_DIR/$POSTGRES_VERSION/main/" 2>/dev/null || {
                log_warn "Data copy had issues, but continuing..."
            }
            
            log_info "PostgreSQL data migration completed"
        elif [ ! -f "$POSTGRES_DATA_DIR/$POSTGRES_VERSION/main/PG_VERSION" ]; then
            log_info "Initializing new PostgreSQL data directory on RAID..."
            sudo -u postgres /usr/lib/postgresql/$POSTGRES_VERSION/bin/initdb -D "$POSTGRES_DATA_DIR/$POSTGRES_VERSION/main"
        else
            log_info "PostgreSQL data directory already exists on RAID"
        fi
        
        # Update postgresql.conf to use custom data directory
        if ! grep -q "^data_directory" /etc/postgresql/$POSTGRES_VERSION/main/postgresql.conf; then
            echo "data_directory = '$POSTGRES_DATA_DIR/$POSTGRES_VERSION/main'" >> /etc/postgresql/$POSTGRES_VERSION/main/postgresql.conf
        else
            sed -i "s|^data_directory =.*|data_directory = '$POSTGRES_DATA_DIR/$POSTGRES_VERSION/main'|" /etc/postgresql/$POSTGRES_VERSION/main/postgresql.conf
        fi
        
        log_info "PostgreSQL data directory configured to use: $POSTGRES_DATA_DIR/$POSTGRES_VERSION/main"
        fi
    fi

    # Run TimescaleDB tuning
    log_info "Running TimescaleDB tuning..."
    timescaledb-tune --quiet --yes --pg-config=/usr/lib/postgresql/$POSTGRES_VERSION/bin/pg_config || log_warn "timescaledb-tune failed, continuing with manual configuration"

    # Configure PostgreSQL for production (64GB RAM, 24 cores)
    cat > /etc/postgresql/$POSTGRES_VERSION/main/conf.d/solarhub.conf <<EOF
# Solar Hub PostgreSQL Configuration
# Optimized for 64GB RAM, 24 cores

# Memory Settings
shared_buffers = 16GB
effective_cache_size = 48GB
maintenance_work_mem = 2GB
work_mem = 256MB
wal_buffers = 64MB

# Checkpoint Settings
checkpoint_completion_target = 0.9
max_wal_size = 4GB
min_wal_size = 1GB

# Connection Settings
max_connections = 200
superuser_reserved_connections = 3

# Query Planner
random_page_cost = 1.1
effective_io_concurrency = 200
default_statistics_target = 100

# Parallelism
max_worker_processes = 24
max_parallel_workers_per_gather = 4
max_parallel_workers = 12
max_parallel_maintenance_workers = 4

# Write Ahead Log
wal_level = replica
archive_mode = off

# Logging
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d_%H%M%S.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
log_temp_files = 0

# TimescaleDB
shared_preload_libraries = 'timescaledb'
timescaledb.max_background_workers = 8
EOF

    # Restart PostgreSQL
    systemctl restart postgresql
    systemctl enable postgresql

    # Create databases and users
    sudo -u postgres psql <<EOF
-- Create users
CREATE USER solarhub_app WITH PASSWORD 'CHANGE_THIS_PASSWORD_APP';
CREATE USER solarhub_telemetry WITH PASSWORD 'CHANGE_THIS_PASSWORD_TELEMETRY';

-- Create databases
CREATE DATABASE solar_hub OWNER solarhub_app;
CREATE DATABASE solar_hub_telemetry OWNER solarhub_telemetry;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE solar_hub TO solarhub_app;
GRANT ALL PRIVILEGES ON DATABASE solar_hub_telemetry TO solarhub_telemetry;

-- Enable TimescaleDB extension on telemetry database
\c solar_hub_telemetry
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable UUID extension on both databases
\c solar_hub
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
\c solar_hub_telemetry
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
EOF

    # Configure pg_hba.conf for local connections
    cat >> /etc/postgresql/$POSTGRES_VERSION/main/pg_hba.conf <<EOF

# Solar Hub connections
host    solar_hub           solarhub_app        127.0.0.1/32            scram-sha-256
host    solar_hub_telemetry solarhub_telemetry  127.0.0.1/32            scram-sha-256
host    solar_hub           solarhub_app        ::1/128                 scram-sha-256
host    solar_hub_telemetry solarhub_telemetry  ::1/128                 scram-sha-256
EOF

    systemctl reload postgresql

    log_info "PostgreSQL with TimescaleDB installed and configured"
}

#===============================================================================
# Install Redis
#===============================================================================
install_redis() {
    log_section "Installing Redis"

    apt-get install -y redis-server
    
    # Configure custom data directory for Redis if specified
    REDIS_DIR="/var/lib/redis"
    if [ -n "$REDIS_DATA_DIR" ]; then
        PARENT_DIR=$(dirname "$REDIS_DATA_DIR")
        if [ ! -d "$PARENT_DIR" ]; then
            log_warn "Parent directory $PARENT_DIR does not exist, using default Redis data directory"
        else
        log_info "Configuring Redis to use custom data directory: $REDIS_DATA_DIR"
        REDIS_DIR="$REDIS_DATA_DIR"
        mkdir -p "$REDIS_DIR"
        chown redis:redis "$REDIS_DIR"
        chmod 755 "$REDIS_DIR"
        fi
    fi

    # Configure Redis for production
    cat > /etc/redis/redis.conf <<EOF
# Solar Hub Redis Configuration
# Optimized for production

# Network
bind 127.0.0.1 ::1
port 6379
protected-mode yes
tcp-backlog 511
timeout 0
tcp-keepalive 300

# General
daemonize yes
supervised systemd
pidfile /run/redis/redis-server.pid
loglevel notice
logfile /var/log/redis/redis-server.log
databases 16

# Snapshotting
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir $REDIS_DIR

# Security
requirepass CHANGE_THIS_REDIS_PASSWORD

# Memory Management (allocate 4GB for Redis)
maxmemory 4gb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Append Only Mode
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Slow Log
slowlog-log-slower-than 10000
slowlog-max-len 128

# Client Output Buffer
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit replica 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60
EOF

    systemctl restart redis-server
    systemctl enable redis-server

    log_info "Redis installed and configured"
}

#===============================================================================
# Install Mosquitto MQTT Broker
#===============================================================================
install_mosquitto() {
    log_section "Installing Mosquitto MQTT Broker"

    apt-get install -y mosquitto mosquitto-clients
    
    # Configure custom data directory for Mosquitto if specified
    MOSQUITTO_DIR="/var/lib/mosquitto"
    if [ -n "$MOSQUITTO_DATA_DIR" ]; then
        PARENT_DIR=$(dirname "$MOSQUITTO_DATA_DIR")
        if [ ! -d "$PARENT_DIR" ]; then
            log_warn "Parent directory $PARENT_DIR does not exist, using default Mosquitto data directory"
        else
        log_info "Configuring Mosquitto to use custom data directory: $MOSQUITTO_DATA_DIR"
        MOSQUITTO_DIR="$MOSQUITTO_DATA_DIR"
        mkdir -p "$MOSQUITTO_DIR"
        chown mosquitto:mosquitto "$MOSQUITTO_DIR"
        chmod 755 "$MOSQUITTO_DIR"
        
        # Migrate existing Mosquitto data if it exists
        DEFAULT_MOSQUITTO_DIR="/var/lib/mosquitto"
        if [ -d "$DEFAULT_MOSQUITTO_DIR" ] && [ "$(ls -A $DEFAULT_MOSQUITTO_DIR 2>/dev/null)" ]; then
            log_info "Migrating existing Mosquitto data to RAID..."
            cp -a "$DEFAULT_MOSQUITTO_DIR"/* "$MOSQUITTO_DIR/" 2>/dev/null || true
            chown -R mosquitto:mosquitto "$MOSQUITTO_DIR"
            log_info "Mosquitto data migration completed"
        fi
        fi
    fi

    # Create password file
    touch /etc/mosquitto/passwd
    mosquitto_passwd -b /etc/mosquitto/passwd solarhub CHANGE_THIS_MQTT_PASSWORD

    # Configure Mosquitto
    cat > /etc/mosquitto/conf.d/solarhub.conf <<EOF
# Solar Hub MQTT Configuration

# Default listener for local connections
listener 1883 127.0.0.1
protocol mqtt

# Listener for device connections (external)
listener 8883
protocol mqtt
cafile /opt/solarhub/ssl/ca.crt
certfile /opt/solarhub/ssl/server.crt
keyfile /opt/solarhub/ssl/server.key
require_certificate false

# WebSocket listener (for web dashboard)
listener 9001
protocol websockets

# Authentication
allow_anonymous false
password_file /etc/mosquitto/passwd

# Access Control
acl_file /etc/mosquitto/acl

# Persistence
persistence true
persistence_location $MOSQUITTO_DIR/

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type error
log_type warning
log_type notice
log_type information
log_timestamp true
log_timestamp_format %Y-%m-%dT%H:%M:%S

# Performance
max_connections 10000
max_queued_messages 1000
message_size_limit 1048576
EOF

    # Create ACL file
    cat > /etc/mosquitto/acl <<EOF
# Solar Hub MQTT ACL

# Admin user has full access
user solarhub
topic readwrite #

# Devices can publish to their topics and subscribe to commands
pattern readwrite solarhub/devices/%c/#
pattern read solarhub/commands/%c/#

# System topics are read-only for devices
pattern read \$SYS/#
EOF

    systemctl restart mosquitto
    systemctl enable mosquitto

    log_info "Mosquitto MQTT Broker installed and configured"
}

#===============================================================================
# Install and Configure Nginx
#===============================================================================
install_nginx() {
    log_section "Installing Nginx"

    apt-get install -y nginx

    # Remove default config
    rm -f /etc/nginx/sites-enabled/default

    # Create Solar Hub nginx config
    cat > /etc/nginx/sites-available/solarhub <<EOF
# Solar Hub Nginx Configuration

# Rate limiting zones
limit_req_zone \$binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone \$binary_remote_addr zone=telemetry_limit:10m rate=100r/s;
limit_conn_zone \$binary_remote_addr zone=conn_limit:10m;

# Upstream for System A (Platform API)
upstream system_a {
    server 127.0.0.1:8000;
    keepalive 32;
}

# Upstream for System B (Telemetry API)
upstream system_b {
    server 127.0.0.1:8001;
    keepalive 64;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name _;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

# Main HTTPS server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name _;

    # SSL Configuration (self-signed for now)
    ssl_certificate /opt/solarhub/ssl/server.crt;
    ssl_certificate_key /opt/solarhub/ssl/server.key;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml application/json application/javascript application/rss+xml application/atom+xml image/svg+xml;

    # Connection limits
    limit_conn conn_limit 20;

    # Root for static files (React frontend)
    root /opt/solarhub/app/frontend/build;
    index index.html;

    # Frontend routes
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # System A API (Platform)
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://system_a;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection "";

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # System A WebSocket (Real-time updates)
    location /ws/ {
        proxy_pass http://system_a;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
    }

    # System B API (Telemetry) - Higher rate limits for device data
    location /telemetry/ {
        limit_req zone=telemetry_limit burst=200 nodelay;

        proxy_pass http://system_b/api/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection "";

        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;

        # Larger buffer for telemetry batches
        proxy_buffering on;
        proxy_buffer_size 8k;
        proxy_buffers 16 8k;
        client_max_body_size 10m;
    }

    # Health check endpoints (no rate limiting)
    location /health {
        proxy_pass http://system_a/health;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    location /telemetry/health {
        proxy_pass http://system_b/health;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    # Deny access to sensitive files
    location ~ /\. {
        deny all;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/solarhub /etc/nginx/sites-enabled/

    # Test and reload
    nginx -t
    systemctl restart nginx
    systemctl enable nginx

    log_info "Nginx installed and configured"
}

#===============================================================================
# Generate Self-Signed SSL Certificates
#===============================================================================
generate_ssl_certs() {
    log_section "Generating SSL Certificates"

    SSL_DIR="$SOLARHUB_HOME/ssl"

    # Generate CA key and certificate
    openssl genrsa -out "$SSL_DIR/ca.key" 4096
    openssl req -new -x509 -days 3650 -key "$SSL_DIR/ca.key" -out "$SSL_DIR/ca.crt" \
        -subj "/C=PK/ST=Punjab/L=Lahore/O=Solar Hub/OU=IT/CN=Solar Hub CA"

    # Generate server key and CSR
    openssl genrsa -out "$SSL_DIR/server.key" 2048
    openssl req -new -key "$SSL_DIR/server.key" -out "$SSL_DIR/server.csr" \
        -subj "/C=PK/ST=Punjab/L=Lahore/O=Solar Hub/OU=IT/CN=$SERVER_IP"

    # Create extension file for SAN
    cat > "$SSL_DIR/server.ext" <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
IP.1 = $SERVER_IP
IP.2 = 127.0.0.1
DNS.1 = localhost
EOF

    # Sign server certificate with CA
    openssl x509 -req -in "$SSL_DIR/server.csr" -CA "$SSL_DIR/ca.crt" -CAkey "$SSL_DIR/ca.key" \
        -CAcreateserial -out "$SSL_DIR/server.crt" -days 365 -sha256 -extfile "$SSL_DIR/server.ext"

    # Set permissions
    chmod 600 "$SSL_DIR"/*.key
    chmod 644 "$SSL_DIR"/*.crt
    chown -R "$SOLARHUB_USER":"$SOLARHUB_USER" "$SSL_DIR"

    log_info "SSL certificates generated at $SSL_DIR"
    log_warn "These are self-signed certificates. For production with a domain, use Let's Encrypt"
}

#===============================================================================
# Configure Firewall
#===============================================================================
configure_firewall() {
    log_section "Configuring Firewall"

    # Reset UFW
    ufw --force reset

    # Default policies
    ufw default deny incoming
    ufw default allow outgoing

    # Allow SSH (change port if using non-standard)
    ufw allow 22/tcp comment 'SSH'

    # Allow HTTP and HTTPS
    ufw allow 80/tcp comment 'HTTP'
    ufw allow 443/tcp comment 'HTTPS'

    # Allow MQTT with TLS (for devices)
    ufw allow 8883/tcp comment 'MQTT TLS'

    # Allow MQTT WebSocket (for web dashboard)
    ufw allow 9001/tcp comment 'MQTT WebSocket'

    # Enable UFW
    ufw --force enable

    log_info "Firewall configured"
    ufw status verbose
}

#===============================================================================
# Configure Fail2Ban
#===============================================================================
configure_fail2ban() {
    log_section "Configuring Fail2Ban"

    cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
banaction = ufw

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 24h

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
findtime = 1m
bantime = 1h
EOF

    systemctl restart fail2ban
    systemctl enable fail2ban

    log_info "Fail2Ban configured"
}

#===============================================================================
# Setup Log Rotation
#===============================================================================
setup_logrotate() {
    log_section "Configuring Log Rotation"

    cat > /etc/logrotate.d/solarhub <<EOF
/opt/solarhub/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 solarhub solarhub
    sharedscripts
    postrotate
        systemctl reload solarhub-platform >/dev/null 2>&1 || true
        systemctl reload solarhub-telemetry >/dev/null 2>&1 || true
    endscript
}
EOF

    log_info "Log rotation configured"
}

#===============================================================================
# Create Environment File
#===============================================================================
create_env_file() {
    log_section "Creating Environment File"

    # Generate random passwords
    JWT_SECRET=$(openssl rand -hex 32)
    DEVICE_SECRET=$(openssl rand -hex 32)

    cat > "$SOLARHUB_HOME/app/.env" <<EOF
# Solar Hub Production Environment Configuration
# Generated on $(date)

# =============================================================================
# Application Settings
# =============================================================================
ENVIRONMENT=production
DEBUG=false

# =============================================================================
# System A - Platform & Monitoring
# =============================================================================
APP_NAME="Solar Hub Platform"
APP_VERSION=1.0.0
HOST=127.0.0.1
PORT=8000
WORKERS=8

# Database (PostgreSQL)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=solar_hub
DB_USER=solarhub_app
DB_PASSWORD=CHANGE_THIS_PASSWORD_APP
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_ECHO_SQL=false

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=CHANGE_THIS_REDIS_PASSWORD

# JWT Authentication
JWT_SECRET_KEY=$JWT_SECRET
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ALLOWED_ORIGINS=["https://$SERVER_IP"]

# Notifications
NOTIFICATION_SMS_ENABLED=false
NOTIFICATION_EMAIL_ENABLED=false

# AI Features
AI_ENABLED=false

# =============================================================================
# System B - Communication & Telemetry
# =============================================================================
# TimescaleDB
TIMESCALE_HOST=127.0.0.1
TIMESCALE_PORT=5432
TIMESCALE_NAME=solar_hub_telemetry
TIMESCALE_USER=solarhub_telemetry
TIMESCALE_PASSWORD=CHANGE_THIS_PASSWORD_TELEMETRY
TIMESCALE_POOL_SIZE=30
TIMESCALE_MAX_OVERFLOW=60
TIMESCALE_RETENTION_DAYS=90
TIMESCALE_COMPRESSION_AFTER_DAYS=7

# Redis (separate DB for System B)
# Uses same Redis instance but different DB number

# MQTT Protocol
PROTOCOL_MQTT_ENABLED=true
PROTOCOL_MQTT_BROKER_HOST=127.0.0.1
PROTOCOL_MQTT_BROKER_PORT=1883
PROTOCOL_MQTT_USERNAME=solarhub
PROTOCOL_MQTT_PASSWORD=CHANGE_THIS_MQTT_PASSWORD
PROTOCOL_MQTT_TOPIC_PREFIX=solarhub/

# Device Authentication
DEVICE_AUTH_TOKEN_VALIDITY_MINUTES=5
DEVICE_AUTH_SECRET_KEY=$DEVICE_SECRET

# Telemetry Processing
TELEMETRY_BATCH_SIZE=500
TELEMETRY_FLUSH_INTERVAL_SECONDS=1.0
TELEMETRY_MAX_MESSAGES_PER_MINUTE=200

# Workers
WORKER_TELEMETRY_PROCESSOR_WORKERS=8
WORKER_AGGREGATION_WORKER_INTERVAL=60
WORKER_ALERT_CHECKER_INTERVAL=10

# System A Integration
SYSTEM_A_URL=http://127.0.0.1:8000
EOF

    chmod 600 "$SOLARHUB_HOME/app/.env"
    chown "$SOLARHUB_USER":"$SOLARHUB_USER" "$SOLARHUB_HOME/app/.env"

    log_info "Environment file created at $SOLARHUB_HOME/app/.env"
    log_warn "IMPORTANT: Update the passwords in the .env file before starting the application!"
}

#===============================================================================
# Create Systemd Services
#===============================================================================
create_systemd_services() {
    log_section "Creating Systemd Services"

    # System A Service
    cat > /etc/systemd/system/solarhub-platform.service <<EOF
[Unit]
Description=Solar Hub Platform API (System A)
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=exec
User=$SOLARHUB_USER
Group=$SOLARHUB_USER
WorkingDirectory=$SOLARHUB_HOME/app/system_a
Environment="PATH=$SOLARHUB_HOME/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$SOLARHUB_HOME/app/.env
ExecStart=$SOLARHUB_HOME/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 8 --loop uvloop --http httptools
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=append:$SOLARHUB_HOME/logs/platform.log
StandardError=append:$SOLARHUB_HOME/logs/platform-error.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$SOLARHUB_HOME/logs $SOLARHUB_HOME/data

# Resource Limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

    # System B Service
    cat > /etc/systemd/system/solarhub-telemetry.service <<EOF
[Unit]
Description=Solar Hub Telemetry API (System B)
After=network.target postgresql.service redis-server.service mosquitto.service
Wants=postgresql.service redis-server.service mosquitto.service

[Service]
Type=exec
User=$SOLARHUB_USER
Group=$SOLARHUB_USER
WorkingDirectory=$SOLARHUB_HOME/app/system_b
Environment="PATH=$SOLARHUB_HOME/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=$SOLARHUB_HOME/app/.env
ExecStart=$SOLARHUB_HOME/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 4 --loop uvloop --http httptools
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=append:$SOLARHUB_HOME/logs/telemetry.log
StandardError=append:$SOLARHUB_HOME/logs/telemetry-error.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$SOLARHUB_HOME/logs $SOLARHUB_HOME/data

# Resource Limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload

    log_info "Systemd services created"
}

#===============================================================================
# Setup Python Virtual Environment
#===============================================================================
setup_python_env() {
    log_section "Setting Up Python Virtual Environment"

    # Create virtual environment
    python3 -m venv "$SOLARHUB_HOME/venv"

    # Upgrade pip
    "$SOLARHUB_HOME/venv/bin/pip" install --upgrade pip wheel setuptools

    # Install uvloop and httptools for performance
    "$SOLARHUB_HOME/venv/bin/pip" install uvloop httptools

    chown -R "$SOLARHUB_USER":"$SOLARHUB_USER" "$SOLARHUB_HOME/venv"

    log_info "Python virtual environment created"
}

#===============================================================================
# Print Summary
#===============================================================================
print_summary() {
    log_section "Setup Complete!"

    echo ""
    echo -e "${GREEN}Solar Hub server setup is complete!${NC}"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "                         IMPORTANT NEXT STEPS"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    echo "1. UPDATE PASSWORDS in the following files:"
    echo "   - $SOLARHUB_HOME/app/.env"
    echo "   - PostgreSQL users (run: sudo -u postgres psql)"
    echo "   - Redis password in /etc/redis/redis.conf"
    echo "   - MQTT password (run: mosquitto_passwd -b /etc/mosquitto/passwd solarhub NEW_PASSWORD)"
    echo ""
    echo "2. CLONE YOUR REPOSITORY:"
    echo "   cd $SOLARHUB_HOME/app"
    echo "   git clone YOUR_REPO_URL ."
    echo ""
    echo "3. INSTALL PYTHON DEPENDENCIES:"
    echo "   source $SOLARHUB_HOME/venv/bin/activate"
    echo "   pip install -r system_a/requirements.txt"
    echo "   pip install -r system_b/requirements.txt"
    echo ""
    echo "4. RUN DATABASE MIGRATIONS:"
    echo "   cd system_a && alembic upgrade head"
    echo ""
    echo "5. START THE SERVICES:"
    echo "   systemctl start solarhub-platform"
    echo "   systemctl start solarhub-telemetry"
    echo "   systemctl enable solarhub-platform"
    echo "   systemctl enable solarhub-telemetry"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "                         ACCESS INFORMATION"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    echo "Server IP: $SERVER_IP"
    echo ""
    echo "URLs (after starting services):"
    echo "  - Platform API:  https://$SERVER_IP/api/v1/"
    echo "  - Telemetry API: https://$SERVER_IP/telemetry/v1/"
    echo "  - Health Check:  https://$SERVER_IP/health"
    echo ""
    echo "Ports:"
    echo "  - HTTPS:      443"
    echo "  - MQTT TLS:   8883"
    echo "  - MQTT WS:    9001"
    echo ""
    echo "Log files: $SOLARHUB_HOME/logs/"
    echo "Data dir:  $SOLARHUB_HOME/data/"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    echo "Setup log saved to: $LOG_FILE"
    echo ""
}

#===============================================================================
# Main
#===============================================================================
main() {
    log_section "Solar Hub Production Server Setup"
    log_info "Starting setup process..."

    check_root
    get_server_ip
    
    # Log RAID configuration if detected
    if [ -n "$RAID_MOUNT" ]; then
        # Get the device name for the mount point
        RAID_DEVICE=$(mount | grep "$RAID_MOUNT" | awk '{print $1}' | head -1)
        log_info "RAID array detected: $RAID_DEVICE mounted at $RAID_MOUNT"
        log_info "Data directories will be configured on RAID:"
        log_info "  PostgreSQL: $POSTGRES_DATA_DIR"
        log_info "  Redis: $REDIS_DATA_DIR"
        log_info "  Mosquitto: $MOSQUITTO_DATA_DIR"
    else
        log_info "No RAID array detected - using default data directories"
    fi

    setup_system
    create_user
    install_docker
    install_postgresql
    install_redis
    install_mosquitto
    setup_python_env
    generate_ssl_certs
    install_nginx
    configure_firewall
    configure_fail2ban
    setup_logrotate
    create_env_file
    create_systemd_services

    print_summary
}

# Run main function
main "$@"
