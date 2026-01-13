# Solar Hub - Production Deployment Guide

This guide covers deploying Solar Hub on a Debian server with native services (recommended for production).

## Server Requirements

- **OS**: Debian 11 or 12
- **RAM**: 64GB (minimum 16GB for smaller deployments)
- **CPU**: 24+ cores recommended
- **Storage**: SSD with 500GB+ (for telemetry data)
- **Network**: Static IP address

## Quick Start

### 1. Initial Server Setup

SSH into your server and run the setup script:

```bash
# Download the setup script
wget https://raw.githubusercontent.com/YOUR_REPO/solar-hub/main/deployment/scripts/setup-server.sh

# Make it executable
chmod +x setup-server.sh

# Run as root
sudo ./setup-server.sh
```

The script will install and configure:
- Docker (for optional containerized deployment)
- PostgreSQL 16 with optimized settings
- TimescaleDB extension for telemetry
- Redis 7 for caching and pub/sub
- Mosquitto MQTT broker
- Nginx reverse proxy with SSL
- UFW firewall
- Fail2Ban for security
- Python virtual environment
- Systemd services

### 2. Update Passwords

**CRITICAL**: Update all default passwords before going live.

Edit the environment file:
```bash
sudo nano /opt/solarhub/app/.env
```

Update these passwords:
- `DB_PASSWORD` - PostgreSQL password
- `TIMESCALE_PASSWORD` - TimescaleDB password
- `REDIS_PASSWORD` - Redis password
- `PROTOCOL_MQTT_PASSWORD` - MQTT broker password

Then update the database passwords:
```bash
# PostgreSQL
sudo -u postgres psql -c "ALTER USER solarhub_app PASSWORD 'YOUR_NEW_PASSWORD';"
sudo -u postgres psql -c "ALTER USER solarhub_telemetry PASSWORD 'YOUR_NEW_PASSWORD';"

# Redis
sudo sed -i 's/CHANGE_THIS_REDIS_PASSWORD/YOUR_NEW_PASSWORD/' /etc/redis/redis.conf
sudo systemctl restart redis-server

# MQTT
sudo mosquitto_passwd -b /etc/mosquitto/passwd solarhub YOUR_NEW_PASSWORD
sudo systemctl restart mosquitto
```

### 3. Deploy Application Code

```bash
# Switch to solarhub user
sudo su - solarhub

# Clone your repository
cd /opt/solarhub/app
git clone https://github.com/YOUR_REPO/solar-hub.git .

# Activate virtual environment
source /opt/solarhub/venv/bin/activate

# Install dependencies
pip install -r system_a/requirements.txt
pip install -r system_b/requirements.txt
```

### 4. Run Database Migrations

```bash
cd /opt/solarhub/app/system_a
alembic upgrade head

cd /opt/solarhub/app/system_b
alembic upgrade head
```

### 5. Start Services

```bash
# Start application services
sudo systemctl start solarhub-platform
sudo systemctl start solarhub-telemetry

# Enable on boot
sudo systemctl enable solarhub-platform
sudo systemctl enable solarhub-telemetry
```

### 6. Verify Installation

```bash
# Check service status
sudo systemctl status solarhub-platform
sudo systemctl status solarhub-telemetry

# Check API health
curl http://localhost:8000/health
curl http://localhost:8001/health

# Check via Nginx
curl -k https://YOUR_SERVER_IP/health
```

## Directory Structure

```
/opt/solarhub/
├── app/                    # Application code
│   ├── system_a/          # Platform API
│   ├── system_b/          # Telemetry API
│   ├── frontend/          # React frontend (build)
│   └── .env               # Environment configuration
├── venv/                  # Python virtual environment
├── logs/                  # Application logs
├── data/                  # Persistent data
├── backups/               # Database backups
└── ssl/                   # SSL certificates
```

## Service Management

### Starting/Stopping Services

```bash
# Platform API
sudo systemctl start solarhub-platform
sudo systemctl stop solarhub-platform
sudo systemctl restart solarhub-platform

# Telemetry API
sudo systemctl start solarhub-telemetry
sudo systemctl stop solarhub-telemetry
sudo systemctl restart solarhub-telemetry

# All services
sudo systemctl restart solarhub-platform solarhub-telemetry
```

### Viewing Logs

```bash
# Application logs
tail -f /opt/solarhub/logs/platform.log
tail -f /opt/solarhub/logs/telemetry.log

# Systemd logs
journalctl -u solarhub-platform -f
journalctl -u solarhub-telemetry -f
```

### Maintenance Commands

```bash
# Use the maintenance script
/opt/solarhub/scripts/maintenance.sh status    # Service status
/opt/solarhub/scripts/maintenance.sh health    # Health checks
/opt/solarhub/scripts/maintenance.sh stats     # System resources
/opt/solarhub/scripts/maintenance.sh db-stats  # Database stats
/opt/solarhub/scripts/maintenance.sh vacuum    # Database vacuum
/opt/solarhub/scripts/maintenance.sh logs platform 100  # View logs
```

## Backup & Restore

### Automatic Backups

Set up daily backups via cron:

```bash
# Edit crontab
sudo crontab -e

# Add this line (runs at 2 AM daily)
0 2 * * * /opt/solarhub/scripts/backup.sh
```

### Manual Backup

```bash
/opt/solarhub/scripts/backup.sh
```

### Restore from Backup

```bash
# List available backups
/opt/solarhub/scripts/restore.sh list

# Restore specific database
/opt/solarhub/scripts/restore.sh postgres /path/to/backup.sql.gz
/opt/solarhub/scripts/restore.sh timescale /path/to/backup.sql.gz

# Restore all (latest backups)
/opt/solarhub/scripts/restore.sh all
```

## SSL Certificates

### Using Self-Signed Certificates (Default)

Self-signed certificates are generated during setup. For internal/testing use only.

### Using Let's Encrypt (Production)

When you have a domain name:

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Update Nginx config
sudo nano /etc/nginx/sites-available/solarhub
# Uncomment the Let's Encrypt lines and comment out self-signed

# Test and reload
sudo nginx -t
sudo systemctl reload nginx
```

## Firewall Configuration

The setup script configures UFW with these rules:

| Port | Protocol | Description |
|------|----------|-------------|
| 22   | TCP      | SSH         |
| 80   | TCP      | HTTP (redirects to HTTPS) |
| 443  | TCP      | HTTPS       |
| 8883 | TCP      | MQTT with TLS |
| 9001 | TCP      | MQTT WebSocket |

To add additional rules:

```bash
sudo ufw allow 8080/tcp comment 'Custom port'
sudo ufw status
```

## Scaling Considerations

### Horizontal Scaling

For high-traffic deployments:

1. **Load Balancer**: Place Nginx or HAProxy in front of multiple app instances
2. **Database Replication**: Set up PostgreSQL streaming replication
3. **Redis Cluster**: Use Redis Cluster for distributed caching
4. **Separate Workers**: Run background workers on dedicated nodes

### Vertical Scaling

Adjust worker counts based on CPU cores:

```bash
# In systemd service files
# Platform API: 2 workers per core (up to 16)
# Telemetry API: 1 worker per 4 cores (handles high throughput)

# Edit: /etc/systemd/system/solarhub-platform.service
ExecStart=... --workers 16 ...

sudo systemctl daemon-reload
sudo systemctl restart solarhub-platform
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
journalctl -u solarhub-platform -n 100

# Check for port conflicts
sudo netstat -tulpn | grep 8000

# Verify dependencies
sudo systemctl status postgresql redis-server
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
PGPASSWORD=your_password psql -h 127.0.0.1 -U solarhub_app -d solar_hub -c "SELECT 1"

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-16-main.log
```

### MQTT Connection Issues

```bash
# Test MQTT connection
mosquitto_pub -h 127.0.0.1 -u solarhub -P your_password -t test -m "hello"

# Check Mosquitto logs
sudo tail -f /var/log/mosquitto/mosquitto.log
```

### High Memory Usage

```bash
# Check memory usage by service
ps aux --sort=-%mem | head -20

# Restart services to free memory
sudo systemctl restart solarhub-platform solarhub-telemetry
```

## Security Checklist

- [ ] Changed all default passwords
- [ ] Updated SSH to use key-based authentication
- [ ] Disabled root SSH login
- [ ] Configured UFW firewall
- [ ] Enabled Fail2Ban
- [ ] Set up SSL certificates (Let's Encrypt for production)
- [ ] Enabled automatic security updates
- [ ] Configured backup encryption for off-site storage
- [ ] Set up monitoring and alerting

## Support

For issues and questions:
- Create an issue on GitHub
- Check the logs in `/opt/solarhub/logs/`
- Run health checks: `/opt/solarhub/scripts/maintenance.sh health`
