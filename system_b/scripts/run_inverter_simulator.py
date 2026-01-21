#!/usr/bin/env python3
"""
Standalone inverter simulator that connects to System B.

This script runs a Powdrive inverter simulator and optionally:
- Registers with System B API
- Sends telemetry data at regular intervals
- Accepts and responds to commands
"""
import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import httpx
from pathlib import Path

# Add system_b directory to path
system_b_dir = Path(__file__).parent.parent
sys.path.insert(0, str(system_b_dir))

from tests.simulators.inverter_simulator import PowdriveSimulator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemBConnectedSimulator:
    """
    Inverter simulator that connects to System B API.
    
    Features:
    - Runs Modbus TCP server for device_server to connect
    - Registers device with System B
    - Sends telemetry data periodically
    - Polls for commands and responds
    """
    
    def __init__(
        self,
        serial_number: str,
        site_id: UUID,
        system_b_url: str = "http://127.0.0.1:8001",
        modbus_port: int = 8502,
        telemetry_interval: int = 60,
    ):
        """
        Initialize connected simulator.
        
        Args:
            serial_number: Device serial number
            site_id: Site ID in System B
            system_b_url: System B API base URL
            modbus_port: Port for Modbus TCP server
            telemetry_interval: Seconds between telemetry sends
        """
        self.serial_number = serial_number
        self.site_id = site_id
        self.system_b_url = system_b_url.rstrip('/')
        self.modbus_port = modbus_port
        self.telemetry_interval = telemetry_interval
        
        # Create simulator
        self.simulator = PowdriveSimulator(
            serial_number=serial_number,
            rated_power_w=12000,
            battery_capacity_pct=75.0,
        )
        
        # HTTP client for System B API
        self.http_client: Optional[httpx.AsyncClient] = None
        self.device_id: Optional[UUID] = None
        
        # Background tasks
        self._running = False
        self._telemetry_task: Optional[asyncio.Task] = None
        self._command_poll_task: Optional[asyncio.Task] = None
        
    async def start(self) -> None:
        """Start the simulator and connect to System B."""
        logger.info(f"Starting simulator for {self.serial_number}")
        
        # Start Modbus TCP server
        actual_port = await self.simulator.start(host="0.0.0.0", port=self.modbus_port)
        logger.info(f"Modbus TCP server listening on port {actual_port}")
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            base_url=self.system_b_url,
            timeout=30.0,
        )
        
        # Register with System B
        await self._register_device()
        
        # Start background tasks
        self._running = True
        self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        self._command_poll_task = asyncio.create_task(self._command_poll_loop())
        
        logger.info("Simulator started and connected to System B")
        
    async def stop(self) -> None:
        """Stop the simulator."""
        logger.info("Stopping simulator...")
        self._running = False
        
        # Cancel background tasks
        if self._telemetry_task:
            self._telemetry_task.cancel()
        if self._command_poll_task:
            self._command_poll_task.cancel()
            
        # Stop simulator
        await self.simulator.stop()
        
        # Close HTTP client
        if self.http_client:
            await self.http_client.aclose()
            
        logger.info("Simulator stopped")
        
    async def _register_device(self) -> None:
        """Register device with System B."""
        try:
            response = await self.http_client.post(
                "/api/v1/devices/register",
                json={
                    "site_id": str(self.site_id),
                    "device_type": "inverter",
                    "serial_number": self.serial_number,
                    "protocol_id": "powdrive",
                    "firmware_version": "1.0.0",
                    "hardware_version": "1.0",
                }
            )
            
            if response.status_code == 201:
                data = response.json()
                self.device_id = UUID(data["id"])
                logger.info(f"Registered device: {self.device_id}")
            else:
                logger.error(f"Failed to register device: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error registering device: {e}")
            
    async def _telemetry_loop(self) -> None:
        """Send telemetry data periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.telemetry_interval)
                
                if not self.device_id:
                    continue
                    
                # Get current state from simulator
                state = self.simulator.get_state()
                
                # Prepare telemetry data
                telemetry = {
                    "battery_soc_pct": state["battery_soc"],
                    "battery_power_w": state["battery_power_w"],
                    "pv_power_w": state["pv_power_w"],
                    "grid_power_w": state["grid_power_w"],
                    "load_power_w": state["load_power_w"],
                    "grid_voltage_v": state["grid_voltage_v"],
                    "inverter_temp_c": state["inverter_temp_c"],
                    "energy_pv_today_kwh": state["energy_pv_today_kwh"],
                }
                
                # Send to System B
                await self._send_telemetry(telemetry)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in telemetry loop: {e}")
                
    async def _send_telemetry(self, telemetry: dict) -> None:
        """Send telemetry data to System B."""
        if not self.device_id or not self.http_client:
            return
            
        try:
            # Convert to telemetry points format
            timestamp = datetime.now(timezone.utc).isoformat()
            points = []
            
            for metric_name, value in telemetry.items():
                points.append({
                    "time": timestamp,
                    "device_id": str(self.device_id),
                    "site_id": str(self.site_id),
                    "metric_name": metric_name,
                    "metric_value": float(value) if isinstance(value, (int, float)) else None,
                    "quality": "good",
                })
            
            response = await self.http_client.post(
                "/api/v1/telemetry/batch",
                json={
                    "source_type": "simulator",
                    "source_identifier": self.serial_number,
                    "points": points,
                }
            )
            
            if response.status_code in (200, 201):
                logger.debug(f"Sent telemetry: {len(points)} points")
            else:
                logger.warning(f"Failed to send telemetry: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending telemetry: {e}")
            
    async def _command_poll_loop(self) -> None:
        """Poll for pending commands and execute them."""
        while self._running:
            try:
                await asyncio.sleep(5)  # Poll every 5 seconds
                
                if not self.device_id:
                    continue
                    
                # Get pending commands
                await self._check_commands()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in command poll loop: {e}")
                
    async def _check_commands(self) -> None:
        """Check for pending commands and execute them."""
        if not self.device_id or not self.http_client:
            return
            
        try:
            # Get pending command
            response = await self.http_client.get(
                f"/api/v1/commands/pending/{self.device_id}"
            )
            
            if response.status_code == 200:
                command = response.json()
                if command:
                    await self._execute_command(command)
                    
        except Exception as e:
            logger.error(f"Error checking commands: {e}")
            
    async def _execute_command(self, command: dict) -> None:
        """Execute a command and report result."""
        command_id = UUID(command["id"])
        command_type = command["command_type"]
        command_params = command.get("command_params", {})
        
        logger.info(f"Executing command: {command_type} with params: {command_params}")
        
        # Simulate command execution
        success = True
        result_data = {}
        
        # Handle different command types
        if command_type == "set_battery_mode":
            mode = command_params.get("mode", "auto")
            logger.info(f"Setting battery mode to: {mode}")
            result_data = {"mode": mode, "status": "applied"}
            
        elif command_type == "set_charge_current":
            current = command_params.get("current_a", 0)
            logger.info(f"Setting charge current to: {current}A")
            result_data = {"current_a": current, "status": "applied"}
            
        # Report result
        try:
            response = await self.http_client.post(
                f"/api/v1/commands/{command_id}/result",
                json={
                    "success": success,
                    "data": result_data,
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Command {command_id} completed successfully")
            else:
                logger.warning(f"Failed to report command result: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error reporting command result: {e}")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run inverter simulator connected to System B")
    parser.add_argument("--serial", required=True, help="Device serial number")
    parser.add_argument("--site-id", required=True, type=UUID, help="Site ID (UUID)")
    parser.add_argument("--system-b-url", default="http://127.0.0.1:8001", help="System B API URL")
    parser.add_argument("--modbus-port", type=int, default=8502, help="Modbus TCP port")
    parser.add_argument("--telemetry-interval", type=int, default=60, help="Telemetry interval (seconds)")
    
    args = parser.parse_args()
    
    simulator = SystemBConnectedSimulator(
        serial_number=args.serial,
        site_id=args.site_id,
        system_b_url=args.system_b_url,
        modbus_port=args.modbus_port,
        telemetry_interval=args.telemetry_interval,
    )
    
    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(simulator.stop())
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await simulator.start()
        
        # Keep running
        while simulator._running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await simulator.stop()


if __name__ == "__main__":
    asyncio.run(main())
