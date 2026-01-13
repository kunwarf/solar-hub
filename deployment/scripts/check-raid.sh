#!/bin/bash
#===============================================================================
# RAID and Mount Point Checker Script
# Run this script to identify RAID arrays and mount points on your server
#===============================================================================

echo "================================================================="
echo "RAID Arrays Information"
echo "================================================================="
echo ""

# Check for software RAID (mdadm)
if command -v mdadm &> /dev/null; then
    echo "Software RAID (mdadm) Arrays:"
    echo "----------------------------"
    cat /proc/mdstat 2>/dev/null || echo "No mdadm arrays found"
    echo ""
    
    # List detailed RAID info
    if [ -f /proc/mdstat ] && grep -q "md" /proc/mdstat; then
        echo "Detailed RAID Information:"
        mdadm --detail --scan 2>/dev/null || true
        echo ""
        
        # List each RAID device
        for md in /dev/md*; do
            if [ -b "$md" ]; then
                echo "RAID Device: $md"
                mdadm --detail "$md" 2>/dev/null | head -20
                echo ""
            fi
        done
    fi
else
    echo "mdadm not installed - no software RAID detected"
    echo ""
fi

# Check for hardware RAID
echo "Hardware RAID Controllers:"
echo "-------------------------"
lspci | grep -i raid || echo "No hardware RAID controllers found"
echo ""

echo "================================================================="
echo "Mount Points and Filesystems"
echo "================================================================="
echo ""

echo "All Mount Points:"
echo "-----------------"
df -h | grep -E "^/dev|^tmpfs|^/mnt|^/media" || df -h
echo ""

echo "Mount Points in /etc/fstab:"
echo "---------------------------"
grep -v "^#" /etc/fstab | grep -v "^$" | awk '{print $1, $2, $3}' || echo "No entries found"
echo ""

echo "================================================================="
echo "Current Data Directory Locations"
echo "================================================================="
echo ""

# Check PostgreSQL data directory
if [ -d /var/lib/postgresql ]; then
    echo "PostgreSQL Default Location:"
    echo "  /var/lib/postgresql"
    du -sh /var/lib/postgresql/* 2>/dev/null | head -5 || echo "  (empty or no data)"
    echo ""
    
    # Check if PostgreSQL is configured
    if [ -f /etc/postgresql/*/main/postgresql.conf ]; then
        echo "PostgreSQL Configuration:"
        grep "^data_directory" /etc/postgresql/*/main/postgresql.conf 2>/dev/null || echo "  Using default location"
        echo ""
    fi
fi

# Check Redis data directory
if [ -d /var/lib/redis ]; then
    echo "Redis Default Location:"
    echo "  /var/lib/redis"
    du -sh /var/lib/redis 2>/dev/null || echo "  (empty or no data)"
    echo ""
    
    if [ -f /etc/redis/redis.conf ]; then
        echo "Redis Configuration:"
        grep "^dir " /etc/redis/redis.conf 2>/dev/null || echo "  Using default location"
        echo ""
    fi
fi

# Check Mosquitto data directory
if [ -d /var/lib/mosquitto ]; then
    echo "Mosquitto Default Location:"
    echo "  /var/lib/mosquitto"
    du -sh /var/lib/mosquitto 2>/dev/null || echo "  (empty or no data)"
    echo ""
    
    if [ -f /etc/mosquitto/conf.d/*.conf ]; then
        echo "Mosquitto Configuration:"
        grep "persistence_location" /etc/mosquitto/conf.d/*.conf 2>/dev/null || echo "  Using default location"
        echo ""
    fi
fi

echo "================================================================="
echo "Recommended RAID Mount Points for Data"
echo "================================================================="
echo ""
echo "Common RAID mount points to check:"
echo "  /mnt/raid"
echo "  /mnt/storage"
echo "  /mnt/data"
echo "  /media/raid"
echo "  /storage"
echo "  /data"
echo ""
echo "Checking if these exist:"
for dir in /mnt/raid /mnt/storage /mnt/data /media/raid /storage /data; do
    if [ -d "$dir" ] && mountpoint -q "$dir" 2>/dev/null; then
        echo "  ✓ $dir (mounted)"
        df -h "$dir" | tail -1
    elif [ -d "$dir" ]; then
        echo "  - $dir (exists but not mounted)"
    fi
done
echo ""

echo "================================================================="
echo "Disk Usage Summary"
echo "================================================================="
echo ""
df -h | grep -E "^/dev|^tmpfs" | awk '{printf "%-20s %10s %10s %10s %6s %s\n", $1, $2, $3, $4, $5, $6}'
echo ""

echo "================================================================="
echo "Next Steps"
echo "================================================================="
echo ""
echo "1. Identify your RAID mount point from the list above"
echo "2. Note the current data directory locations"
echo "3. Provide the RAID mount point to configure the setup script"
echo "4. Example: If RAID is mounted at /mnt/raid, use:"
echo "   POSTGRES_DATA_DIR=\"/mnt/raid/postgresql\""
echo "   REDIS_DATA_DIR=\"/mnt/raid/redis\""
echo "   MOSQUITTO_DATA_DIR=\"/mnt/raid/mosquitto\""
echo ""
