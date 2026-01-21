# Systemd Service Logging Configuration

## Log File Paths

The systemd service file already includes logging configuration:

```ini
StandardOutput=append:/opt/solarhub/logs/telemetry.log
StandardError=append:/opt/solarhub/logs/telemetry-error.log
```

## Improvements Made

### 1. Ensure Log Directory Exists

Added `ExecStartPre` directives to create and set permissions on the log directory:

```ini
ExecStartPre=/bin/mkdir -p /opt/solarhub/logs
ExecStartPre=/bin/chown solarhub:solarhub /opt/solarhub/logs
```

This ensures the directory exists before the service starts.

### 2. Log Rotation

Created a logrotate configuration file at:
`deployment/logrotate/solarhub-telemetry`

This will:
- Rotate logs daily
- Keep 30 days of logs
- Compress old logs
- Maintain proper permissions

To install logrotate configuration:

```bash
sudo cp deployment/logrotate/solarhub-telemetry /etc/logrotate.d/
sudo chmod 644 /etc/logrotate.d/solarhub-telemetry
```

### 3. Viewing Logs

View logs in real-time:
```bash
# Standard output
sudo tail -f /opt/solarhub/logs/telemetry.log

# Errors
sudo tail -f /opt/solarhub/logs/telemetry-error.log

# Both
sudo tail -f /opt/solarhub/logs/telemetry*.log
```

View last N lines:
```bash
sudo tail -n 100 /opt/solarhub/logs/telemetry.log
```

Search logs:
```bash
sudo grep "ERROR" /opt/solarhub/logs/telemetry-error.log
```

## Complete Service File

The improved service file is located at:
`deployment/systemd/solarhub-telemetry.service`

To install:

```bash
sudo cp deployment/systemd/solarhub-telemetry.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart solarhub-telemetry
```

## Log File Permissions

The log files will be owned by `solarhub:solarhub` with permissions `0644`.

To manually set permissions:
```bash
sudo chown -R solarhub:solarhub /opt/solarhub/logs
sudo chmod 755 /opt/solarhub/logs
sudo chmod 644 /opt/solarhub/logs/*.log
```

## Additional Logging Options

If you want to use journald instead of files, you can remove the `StandardOutput` and `StandardError` lines and use:

```bash
# View logs via journald
sudo journalctl -u solarhub-telemetry -f
```

However, file-based logging is recommended for production as it:
- Provides persistent logs across reboots
- Allows easy log rotation
- Enables external log aggregation tools
