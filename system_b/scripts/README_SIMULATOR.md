# Inverter Simulator for System B

This script runs a Powdrive inverter simulator that connects to System B and:
- Registers as a device with System B
- Sends telemetry data at regular intervals
- Accepts and responds to commands from System B

## Prerequisites

- System B API running (default: http://127.0.0.1:8001)
- Python 3.8+ with required dependencies
- A valid Site ID in System B

## Usage

### Basic Usage

```bash
cd /opt/solarhub/app/solar-hub/system_b
python scripts/run_inverter_simulator.py \
    --serial PD12K00001 \
    --site-id <your-site-uuid> \
    --system-b-url http://127.0.0.1:8001 \
    --modbus-port 8502 \
    --telemetry-interval 60
```

### Arguments

- `--serial`: Device serial number (required)
- `--site-id`: Site UUID in System B (required)
- `--system-b-url`: System B API base URL (default: http://127.0.0.1:8001)
- `--modbus-port`: Port for Modbus TCP server (default: 8502)
- `--telemetry-interval`: Seconds between telemetry sends (default: 60)

### Running as a Service

Create a systemd service file `/etc/systemd/system/solarhub-simulator.service`:

```ini
[Unit]
Description=Solar Hub Inverter Simulator
After=network.target

[Service]
Type=simple
User=solarhub
Group=solarhub
WorkingDirectory=/opt/solarhub/app/solar-hub/system_b
Environment="PATH=/opt/solarhub/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/opt/solarhub/app/.env
ExecStart=/opt/solarhub/venv/bin/python scripts/run_inverter_simulator.py \
    --serial PD12K00001 \
    --site-id <your-site-uuid> \
    --system-b-url http://127.0.0.1:8001 \
    --modbus-port 8502 \
    --telemetry-interval 60
Restart=always
RestartSec=5
StandardOutput=append:/opt/solarhub/logs/simulator.log
StandardError=append:/opt/solarhub/logs/simulator-error.log

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable solarhub-simulator
sudo systemctl start solarhub-simulator
```

## How It Works

1. **Modbus TCP Server**: The simulator runs a Modbus TCP server that System B's device_server can connect to and poll for data.

2. **Device Registration**: On startup, the simulator registers itself with System B via the `/api/v1/devices/register` endpoint.

3. **Telemetry Transmission**: Every `telemetry_interval` seconds, the simulator:
   - Reads current state from the simulated inverter
   - Sends telemetry data to System B via `/api/v1/telemetry/batch`

4. **Command Handling**: Every 5 seconds, the simulator:
   - Polls System B for pending commands via `/api/v1/commands/pending/{device_id}`
   - Executes received commands
   - Reports results back via `/api/v1/commands/{command_id}/result`

## Simulated Data

The simulator provides realistic inverter data:
- Battery SOC (State of Charge)
- PV power (follows sun curve)
- Grid power (import/export)
- Load power (varies throughout day)
- Battery power (charge/discharge)
- Grid voltage and frequency
- Inverter temperature
- Energy counters

## Troubleshooting

- **Connection refused**: Ensure System B API is running and accessible
- **Registration fails**: Verify the site ID exists in System B
- **No telemetry**: Check System B API logs and verify device was registered
- **Commands not received**: Ensure device_server is configured to connect to the simulator's Modbus port
