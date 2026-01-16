from typing import Dict, Any, List, Optional, Union, Literal
from abc import ABC, abstractmethod
import json
import asyncio
import logging
from solarhub.models import Telemetry
from solarhub.config import InverterConfig

log = logging.getLogger(__name__)

class InverterAdapter(ABC):
    def __init__(self, inv: InverterConfig):
        self.inv = inv

    @abstractmethod
    async def connect(self): ...
    @abstractmethod
    async def close(self): ...
    @abstractmethod
    async def poll(self) -> Telemetry: ...
    @abstractmethod
    async def handle_command(self, cmd: Dict[str, Any]): ...
    
    async def read_serial_number(self) -> Optional[str]:
        """
        Read device serial number for identification.
        Must be implemented by adapters that support auto-discovery.
        Returns None if serial number cannot be read.
        """
        return None  # Default implementation returns None (not supported)
    
    async def check_connectivity(self) -> bool:
        """
        Check if the device is connected and responding.
        This method should use a device-specific register read or command
        to verify connectivity. For example:
        - Inverters: Read serial number register
        - Batteries: Send device-specific command (e.g., 'pwr 1' for Pytes)
        
        Returns:
            True if device is connected and responding, False otherwise
        """
        # Default implementation tries to read serial number as connectivity check
        try:
            serial = await self.read_serial_number()
            return serial is not None
        except Exception:
            return False
    
    @staticmethod
    def normalize_battery_power(power: Optional[float], invert: bool = False) -> Optional[float]:
        """
        Normalize battery power to standard convention:
        - Positive power = Charging (power flowing INTO battery)
        - Negative power = Discharging (power flowing OUT of battery)
        
        Args:
            power: Raw battery power value from inverter
            invert: If True, invert the sign (for inverters with opposite convention)
            
        Returns:
            Normalized battery power (positive = charging, negative = discharging)
        """
        if power is None:
            return None
        normalized = float(power)
        if invert:
            normalized = -normalized
        return normalized
    
    @staticmethod
    def normalize_tou_window(window: Dict[str, Any], current_soc_pct: Optional[float] = None) -> Dict[str, Any]:
        """
        Normalize a TOU window to a generalized format that works for both:
        - Senergy: Separate charge/discharge windows (explicit type)
        - Powdrive: Bidirectional windows (auto-determined by target SOC vs current SOC)
        
        Generalized window format:
        {
            "start_time": "HH:MM",
            "end_time": "HH:MM",
            "power_w": int,  # Absolute power value
            "target_soc_pct": int,  # Target SOC for this window
            "type": "charge" | "discharge" | "auto"  # Direction
        }
        
        For Powdrive ("auto" type):
        - Direction is determined by comparing target_soc_pct to current_soc_pct
        - If target_soc_pct < current_soc_pct → discharge
        - If target_soc_pct > current_soc_pct → charge
        
        For Senergy ("charge" or "discharge" type):
        - Direction is explicit, use as-is
        
        Args:
            window: Window dict with adapter-specific fields
            current_soc_pct: Current battery SOC (required for "auto" type windows)
            
        Returns:
            Normalized window dict with standardized fields
        """
        normalized = {
            "start_time": window.get("start_time") or window.get("chg_start") or window.get("dch_start") or "00:00",
            "end_time": window.get("end_time") or window.get("chg_end") or window.get("dch_end") or "00:00",
            "power_w": abs(window.get("power_w") or window.get("charge_power_w") or window.get("discharge_power_w") or 0),
            "target_soc_pct": window.get("target_soc_pct") or window.get("charge_end_soc") or window.get("discharge_end_soc") or window.get("target_soc") or 100,
        }
        
        # Determine type
        window_type = window.get("type")
        if window_type in ("charge", "discharge", "auto"):
            normalized["type"] = window_type
        elif "charge_power_w" in window or "chg_start" in window or "charge_end_soc" in window:
            normalized["type"] = "charge"
        elif "discharge_power_w" in window or "dch_start" in window or "discharge_end_soc" in window:
            normalized["type"] = "discharge"
        else:
            # Default to auto for bidirectional windows
            normalized["type"] = "auto"
        
        # For auto type, determine actual direction based on current SOC
        if normalized["type"] == "auto" and current_soc_pct is not None:
            if normalized["target_soc_pct"] < current_soc_pct:
                normalized["type"] = "discharge"
            elif normalized["target_soc_pct"] > current_soc_pct:
                normalized["type"] = "charge"
            # If equal, keep as "auto" (no action needed)
        
        return normalized
    
    def get_tou_window_capability(self) -> Dict[str, Any]:
        """
        Returns the TOU window capability for this adapter:
        - max_windows: Maximum number of windows supported
        - bidirectional: Whether windows can be bidirectional (auto-determined direction)
        - separate_charge_discharge: Whether charge and discharge windows are separate
        
        Adapters should override this to specify their capabilities.
        Default assumes Senergy-style (3 charge + 3 discharge, separate).
        """
        return {
            "max_windows": 3,
            "bidirectional": False,
            "separate_charge_discharge": True,
            "max_charge_windows": 3,
            "max_discharge_windows": 3
        }


class ModbusClientMixin:
    """
    Mixin class to handle Modbus client event loop management.
    Provides methods to ensure Modbus clients are created in the correct event loop,
    handling migration between different event loops (e.g., API server loop vs polling loop).
    
    Adapters using this mixin must:
    - Define `self.client: Optional[AsyncModbusSerialClient] = None`
    - Define `self._client_loop: Optional[asyncio.AbstractEventLoop] = None`
    - Optionally define `self._modbus_lock: Optional[asyncio.Lock] = None` if locking is needed
    - Optionally define `self._client_migrated: bool = False` to track migration
    - Implement `_get_client_config()` method that returns client configuration dict
    """
    
    async def _get_client_config(self) -> Dict[str, Any]:
        """
        Get configuration for creating AsyncModbusSerialClient.
        Must be implemented by adapters using this mixin.
        
        Returns:
            Dict with keys: port, baudrate, parity, stopbits, bytesize, timeout
        """
        raise NotImplementedError("Adapters must implement _get_client_config()")
    
    async def _ensure_client_in_current_loop(self):
        """
        Ensure the Modbus client is created in the current event loop.
        Only recreates if we're actually in a different event loop and haven't migrated yet.
        """
        # FIRST: Check if client is already connected and working - if so, skip everything
        if hasattr(self, 'client') and self.client is not None:
            if hasattr(self.client, 'connected') and self.client.connected:
                # Client is connected - verify it's actually working by checking the port
                try:
                    config = await self._get_client_config()
                    port = config.get('port')
                    if port:
                        import os
                        if os.path.exists(port):
                            # Port exists and client is connected - we're good, return immediately
                            log.debug(f"Client already connected to {port}, skipping _ensure_client_in_current_loop")
                            return
                except Exception:
                    pass  # If check fails, continue with normal flow
        
        # Serialize client (re)creation to avoid concurrent close/connect races
        if not hasattr(self, '_client_recreate_guard'):
            self._client_recreate_guard = asyncio.Lock()
        async with self._client_recreate_guard:
            # Double-check connection state after acquiring lock (might have changed)
            if hasattr(self, 'client') and self.client is not None:
                if hasattr(self.client, 'connected') and self.client.connected:
                    log.debug("Client already connected after acquiring lock, skipping recreation")
                    return
            
            # Determine current loop with fallback
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = asyncio.get_event_loop()
            # Check if we need to recreate the client
            needs_recreate = False
            
            if not hasattr(self, 'client') or self.client is None:
                # Client doesn't exist, create it
                needs_recreate = True
                log.info("Creating Modbus client in current event loop")
            elif not hasattr(self, '_client_loop') or self._client_loop is None:
                # Client exists but loop reference is missing, recreate to be safe
                needs_recreate = True
                log.info("Recreating Modbus client (loop reference missing)")
            elif id(self._client_loop) != id(current_loop):
                # Check if we've already migrated
                if hasattr(self, '_client_migrated') and self._client_migrated:
                    # Already migrated, but verify client is still connected
                    if self.client and self.client.connected:
                        # Client is connected and migrated, don't recreate
                        log.debug("Client already migrated and connected, skipping recreation")
                        return
                    else:
                        # Client was migrated but is no longer connected, need to recreate
                        log.info("Client was migrated but is no longer connected, recreating")
                        needs_recreate = True
                else:
                    # We're in a different event loop and haven't migrated yet
                    needs_recreate = True
                    log.info("Recreating Modbus client in current event loop (different loop detected)")
            else:
                # Same loop - check if client is connected
                if self.client and hasattr(self.client, 'connected') and self.client.connected:
                    # Client exists, is in same loop, and is connected - we're good
                    log.debug("Client exists in same loop and is connected, skipping recreation")
                    return
                else:
                    # Client exists in same loop but is NOT connected - try to reconnect first
                    # This avoids unnecessary port close/reopen cycles which can be disruptive
                    if self.client and hasattr(self.client, 'connect'):
                        # Log why we think it's disconnected (for debugging)
                        connected_status = getattr(self.client, 'connected', 'N/A')
                        log.debug(f"Client exists in same loop but is not connected (connected={connected_status}), attempting to reconnect...")
                        try:
                            ok = await self.client.connect()
                            if ok and hasattr(self.client, 'connected') and self.client.connected:
                                log.debug("Successfully reconnected existing client without recreation")
                                return
                            else:
                                log.info(f"Reconnect attempt failed (ok={ok}, connected={getattr(self.client, 'connected', 'N/A')}), will recreate client")
                                needs_recreate = True
                        except Exception as reconnect_ex:
                            log.debug(f"Reconnect attempt raised exception: {reconnect_ex}, will recreate client")
                            needs_recreate = True
                    else:
                        # Client exists but has no connect method, or is None - need to recreate
                        log.info("Client exists in same loop but is not connected and cannot reconnect, recreating")
                        needs_recreate = True
            
            if needs_recreate:
                # Robustly close any previous client and ensure port release
                await self._force_close_client()
                
                # Additional wait after closing to ensure port is fully released
                # This is especially important when migrating from discovery to runtime
                await asyncio.sleep(0.5)
                
                # Get client configuration
                config = await self._get_client_config()
                
                # Determine transport type for logging
                transport = getattr(self, 'transport', 'rtu').lower() if hasattr(self, 'transport') else 'rtu'
                if transport == "tcp":
                    host = config.get('host', 'localhost')
                    port = config.get('port', 502)
                    connection_info = f"{host}:{port}"
                else:
                    port = config.get('port', 'unknown')
                    connection_info = f"port {port}"
                
                # Log where this connection attempt is coming from (for debugging)
                import traceback
                stack = traceback.extract_stack()
                # Get the last 3 callers for better context
                callers = []
                for i in range(min(3, len(stack) - 1)):
                    frame = stack[-(i+2)] if len(stack) > i+1 else None
                    if frame:
                        filename = frame.filename.split('/')[-1] if '/' in frame.filename else frame.filename.split('\\')[-1]
                        callers.append(f"{filename}:{frame.lineno}")
                caller_info = " <- ".join(callers) if callers else "unknown"
                log.info(f"_ensure_client_in_current_loop called from {caller_info}, attempting to create client for {connection_info}")
                
                # Retry connection with exponential backoff
                # Note: We don't check port existence here because:
                # 1. Port existence checks are unreliable (timing issues, Linux serial port behavior)
                # 2. If the port doesn't exist, the connection attempt will fail gracefully
                # 3. Port existence can temporarily fail even when the port is valid
                max_retries = 3
                retry_delay = 0.5
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        # Determine transport type (check adapter or use default RTU)
                        transport = getattr(self, 'transport', 'rtu').lower() if hasattr(self, 'transport') else 'rtu'
                        
                        # Create new client in current loop based on transport type
                        if transport == "tcp":
                            from pymodbus.client import AsyncModbusTcpClient
                            host = config.get('host', 'localhost')
                            port = config.get('port', 502)
                            log.debug(f"Creating Modbus TCP client for {host}:{port} (attempt {attempt+1}/{max_retries})")
                            self.client = AsyncModbusTcpClient(
                                host=host,
                                port=port,
                                timeout=config.get('timeout', 2.0),
                            )
                        else:  # RTU
                            from pymodbus.client import AsyncModbusSerialClient
                            log.debug(f"Creating Modbus RTU client for port {port} (attempt {attempt+1}/{max_retries})")
                            # Check port existence before attempting connection (RTU only)
                            import os
                            if port and not os.path.exists(port):
                                log.warning(f"Port {port} does not exist (attempt {attempt+1}/{max_retries})")
                                last_error = RuntimeError(f"Port {port} does not exist")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2
                                    continue
                                break
                            self.client = AsyncModbusSerialClient(
                                port=config['port'],
                                baudrate=config['baudrate'],
                                parity=config['parity'],
                                stopbits=config['stopbits'],
                                bytesize=config['bytesize'],
                                timeout=config.get('timeout', 2.0),
                            )
                        try:
                            ok = await self.client.connect()
                        except Exception as connect_ex:
                            # Connection attempt raised an exception
                            await self._force_close_client()
                            last_error = connect_ex
                            error_str = str(connect_ex).lower()
                            if transport == "tcp":
                                log.error(f"Modbus TCP connect() raised exception for {host}:{port} (attempt {attempt+1}/{max_retries}): {connect_ex}")
                            else:
                                log.error(f"Modbus RTU connect() raised exception for {port} (attempt {attempt+1}/{max_retries}): {connect_ex}")
                                log.error(f"  Exception type: {type(connect_ex).__name__}")
                                # Check for common RTU errors
                                if "no such file" in error_str or "no such device" in error_str:
                                    log.error(f"  Port {port} does not exist")
                                elif "could not exclusively lock" in error_str or "resource temporarily unavailable" in error_str:
                                    log.error(f"  Port {port} is locked (likely in use by another process)")
                                else:
                                    log.error(f"  Unknown RTU connection error")
                            if "no such file" in error_str or "no such device" in error_str:
                                break  # Don't retry if port doesn't exist
                            if attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                            continue
                        if ok and self.client.connected:
                            # Success - update the stored loop reference and mark as migrated
                            self._client_loop = current_loop
                            if hasattr(self, '_client_migrated'):
                                self._client_migrated = True
                            # Ensure lock bound to this loop when applicable
                            try:
                                await self._ensure_lock_in_current_loop()
                            except Exception:
                                pass
                            if transport == "tcp":
                                log.info(f"Modbus TCP client connected to {host}:{port} in current event loop")
                            else:
                                log.info(f"Modbus RTU client created/recreated on {port} in current event loop")
                            return
                        else:
                            # Connection failed, close and retry
                            await self._force_close_client()
                            if transport == "tcp":
                                connected_status = getattr(self.client, 'connected', 'N/A')
                                log.warning(f"Modbus TCP connection failed to {host}:{port} (ok={ok}, connected={connected_status}, attempt {attempt+1}/{max_retries})")
                                if not ok:
                                    log.warning(f"  connect() returned False - host may be unreachable, port may be blocked by firewall, or device may not be responding")
                                if connected_status is False:
                                    log.warning(f"  client.connected is False - connection was not established")
                                # Suggest network diagnostics
                                log.warning(f"  Troubleshooting: Check if {host} is reachable (ping), verify port {port} is open, check firewall rules")
                                last_error = RuntimeError(f"Modbus TCP connection failed to {host}:{port} (ok={ok}, connected={connected_status})")
                            else:
                                # RTU connection failed - provide detailed diagnostics
                                connected_status = getattr(self.client, 'connected', 'N/A')
                                log.warning(f"Modbus RTU connection failed on {port} (ok={ok}, connected={connected_status}, attempt {attempt+1}/{max_retries})")
                                if not ok:
                                    log.warning(f"  connect() returned False - port may be locked, device may be disconnected, or serial parameters may be incorrect")
                                if connected_status is False:
                                    log.warning(f"  client.connected is False - connection was not established")
                                # Check if port still exists
                                import os
                                if port and os.path.exists(port):
                                    log.warning(f"  Port {port} exists but connection failed - may be locked by another process")
                                else:
                                    log.warning(f"  Port {port} does not exist - device may be disconnected")
                                last_error = RuntimeError(f"Modbus RTU connection failed on {port} (ok={ok}, connected={connected_status})")
                    except Exception as e:
                        # Connection error, close and retry
                        await self._force_close_client()
                        last_error = e
                        error_str = str(e).lower()
                        # Don't retry if port doesn't exist
                        if "no such file" in error_str or "no such device" in error_str:
                            # Port doesn't exist, don't retry
                            log.debug(f"Port {config.get('port')} does not exist, not retrying")
                            break
                        if "Could not exclusively lock port" in error_str or "Resource temporarily unavailable" in error_str:
                            # Port is still locked, wait longer before retry
                            if attempt < max_retries - 1:
                                log.debug(f"Port locked, waiting {retry_delay}s before retry {attempt + 1}/{max_retries}")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2  # Exponential backoff
                                continue
                    
                    # If we get here, connection failed
                    if attempt < max_retries - 1:
                        log.debug(f"Connection attempt {attempt + 1}/{max_retries} failed, retrying...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                
                # All retries failed
                self.client = None
                if last_error:
                    # Only raise if it's not a "port not found" error (common during device changes)
                    error_str = str(last_error).lower()
                    if "no such file" in error_str or "no such device" in error_str:
                        # Port doesn't exist, log at debug level and raise
                        log.debug(f"Port {config.get('port')} does not exist: {last_error}")
                    raise last_error
                else:
                    raise RuntimeError("Modbus RTU connection failed after retries")
            # If client exists and we're in the same loop, do nothing
    
    async def _ensure_lock_in_current_loop(self):
        """
        Ensure the lock is created in the current event loop.
        Only needed for adapters that use internal locking (e.g., Powdrive).
        """
        if not hasattr(self, '_modbus_lock'):
            # This adapter doesn't use locks
            return
            
        try:
            current_loop = asyncio.get_running_loop()
            # Always recreate lock if we're in a different event loop
            # Use id() to compare loop identity since loop objects might not compare properly
            if (self._modbus_lock is None or 
                not hasattr(self, '_client_loop') or 
                self._client_loop is None or 
                id(self._client_loop) != id(current_loop)):
                # Recreate lock in current event loop
                # Don't try to use the old lock if it's bound to a different loop
                old_lock = self._modbus_lock
                self._modbus_lock = asyncio.Lock()
                self._client_loop = current_loop
                if old_lock is not None:
                    log.debug(f"Recreated Modbus lock in current event loop (was bound to different loop)")
                else:
                    log.debug("Created Modbus lock in current event loop")
        except RuntimeError:
            # No running loop, try to get event loop
            try:
                current_loop = asyncio.get_event_loop()
                if (self._modbus_lock is None or 
                    not hasattr(self, '_client_loop') or 
                    self._client_loop is None or 
                    id(self._client_loop) != id(current_loop)):
                    old_lock = self._modbus_lock
                    self._modbus_lock = asyncio.Lock()
                    self._client_loop = current_loop
                    if old_lock is not None:
                        log.debug(f"Recreated Modbus lock in current event loop (was bound to different loop)")
                    else:
                        log.debug("Created Modbus lock in current event loop")
            except RuntimeError:
                # If no event loop at all, create lock anyway
                if self._modbus_lock is None:
                    self._modbus_lock = asyncio.Lock()
                    log.debug("Created Modbus lock (no event loop context)")

    async def disconnect_connection(self):
        """Disconnect the Modbus client connection but keep the client object.
        This allows reconnecting the same client object later without recreating it.
        """
        if not hasattr(self, 'client') or self.client is None:
            log.debug("No client to disconnect")
            return
        
        try:
            log.info("Disconnecting Modbus client connection (keeping client object)")
            # Close the connection but keep the client object
            if hasattr(self.client, 'close'):
                import inspect
                if inspect.iscoroutinefunction(self.client.close):
                    await self.client.close()
                else:
                    self.client.close()
            
            # Close protocol/transport if exposed
            try:
                protocol = getattr(self.client, 'protocol', None)
                if protocol is not None:
                    transport = getattr(protocol, 'transport', None)
                    if transport and hasattr(transport, 'close'):
                        try:
                            transport.close()
                        except Exception:
                            pass
            except Exception:
                pass
            
            # Wait a bit to ensure port is released
            await asyncio.sleep(0.3)
            log.info("Modbus client connection disconnected (client object kept)")
        except Exception as e:
            log.warning(f"Error disconnecting Modbus client connection: {e}")
    
    async def reconnect_connection(self):
        """Reconnect the same Modbus client object with updated parameters.
        This reuses the existing client object instead of creating a new one.
        """
        # Log stack trace to see who's calling reconnect_connection()
        import traceback
        stack = traceback.extract_stack()
        callers = []
        for i in range(min(5, len(stack) - 1)):
            frame = stack[-(i+2)] if len(stack) > i+1 else None
            if frame:
                filename = frame.filename.split('/')[-1] if '/' in frame.filename else frame.filename.split('\\')[-1]
                callers.append(f"{filename}:{frame.lineno}({frame.name})")
        caller_info = " <- ".join(callers) if callers else "unknown"
        log.info(f"Modbus reconnect_connection() called from: {caller_info}")
        
        # FIRST: Early exit check before acquiring lock - if client is already connected, skip
        if hasattr(self, 'client') and self.client is not None:
            if hasattr(self.client, 'connected') and self.client.connected:
                # Also verify port exists to ensure connection is valid
                try:
                    config = await self._get_client_config()
                    port = config.get('port')
                    if port:
                        import os
                        if os.path.exists(port):
                            log.debug(f"Modbus client is already connected to {port}, skipping reconnection (called from: {caller_info})")
                            return
                except Exception:
                    pass  # If check fails, continue with normal flow
        
        # Use the same lock as _ensure_client_in_current_loop to prevent concurrent access
        if not hasattr(self, '_client_recreate_guard'):
            self._client_recreate_guard = asyncio.Lock()
        
        async with self._client_recreate_guard:
            # Double-check connection state after acquiring lock (might have changed)
            if hasattr(self, 'client') and self.client is not None:
                if hasattr(self.client, 'connected') and self.client.connected:
                    log.debug(f"Modbus client is already connected after acquiring lock, skipping reconnection (called from: {caller_info})")
                    return
            
            if not hasattr(self, 'client') or self.client is None:
                log.debug("No client object to reconnect, creating new client")
                # Release lock before calling _ensure_client_in_current_loop (it has its own lock)
                # We'll handle it by calling the recreate logic directly here
                pass
            
            try:
                # Get updated configuration first to log what port we're trying to connect to
                config = await self._get_client_config()
                port = config.get('port', 'unknown')
                log.debug(f"Reconnecting Modbus client (same client object) to port {port}")
                
                # Check if port exists before attempting reconnection
                if port and port != 'unknown':
                    try:
                        import os
                        if not os.path.exists(port):
                            log.warning(f"Port {port} does not exist - cannot reconnect. Device may be disconnected.")
                            raise RuntimeError(f"Port {port} does not exist")
                    except ImportError:
                        pass
                    except Exception as e:
                        log.debug(f"Error checking port existence: {e}")
                
                # If client exists but is disconnected, try to reconnect
                if hasattr(self, 'client') and self.client is not None:
                    # Double-check connection status (might have changed)
                    if hasattr(self.client, 'connected') and self.client.connected:
                        log.debug("Client already connected, skipping reconnection")
                        return
                    
                    # Client exists but is disconnected - try to reconnect
                    if hasattr(self.client, 'connect'):
                        ok = await self.client.connect()
                        if ok and hasattr(self.client, 'connected') and self.client.connected:
                            log.debug("Modbus client reconnected successfully (same client object)")
                            # Ensure lock is bound to current loop
                            await self._ensure_lock_in_current_loop()
                            return
                        else:
                            log.debug("Reconnect failed, will recreate client")
                            # Reconnect failed, recreate client
                            await self._force_close_client()
                    else:
                        log.debug("Client has no connect method, recreating client")
                        await self._force_close_client()
                
                # No client or reconnect failed - create new client
                await self._force_close_client()
                
                # Create new client
                from pymodbus.client import AsyncModbusSerialClient
                self.client = AsyncModbusSerialClient(
                    port=config['port'],
                    baudrate=config['baudrate'],
                    parity=config['parity'],
                    stopbits=config['stopbits'],
                    bytesize=config['bytesize'],
                    timeout=config.get('timeout', 2.0),
                )
                ok = await self.client.connect()
                if ok and hasattr(self.client, 'connected') and self.client.connected:
                    # Update loop reference
                    try:
                        self._client_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        self._client_loop = asyncio.get_event_loop()
                    if hasattr(self, '_client_migrated'):
                        self._client_migrated = True
                    await self._ensure_lock_in_current_loop()
                    log.debug("Modbus client recreated successfully")
                else:
                    raise RuntimeError("Modbus RTU connection failed")
                    
            except Exception as e:
                log.warning(f"Error reconnecting Modbus client: {e}")
                await self._force_close_client()
                # Don't call _ensure_client_in_current_loop here as it might cause recursion
                # Let the caller handle it
                raise
    
    async def _force_close_client(self):
        """Robustly close pymodbus AsyncModbusSerialClient and release the serial port.
        Best-effort: close(), protocol.transport.close(), clear refs, probe port via pyserial.
        """
        old_client = getattr(self, 'client', None)
        if not old_client:
            return
        try:
            # First, try to gracefully close the transport to cancel pending operations
            try:
                protocol = getattr(old_client, 'protocol', None)
                if protocol is not None:
                    transport = getattr(protocol, 'transport', None)
                    if transport:
                        # Close transport first to stop accepting new writes and cancel pending ones
                        if hasattr(transport, 'close'):
                            try:
                                # This should cancel pending write callbacks
                                transport.close()
                            except Exception:
                                pass
                        # Replace sync_serial with a dummy object to prevent AttributeError
                        # in any remaining callbacks that might still fire
                        # This is a workaround for pymodbus's intern_write_ready callback
                        if hasattr(transport, 'sync_serial'):
                            try:
                                # Create a dummy serial object that has a write method
                                # This prevents AttributeError but doesn't actually write
                                class DummySerial:
                                    def write(self, data):
                                        # Return length to satisfy pymodbus's expectations
                                        return len(data) if data else 0
                                transport.sync_serial = DummySerial()
                            except Exception:
                                pass
            except Exception:
                pass
            
            # Graceful close (supports async/sync)
            close_fn = getattr(old_client, 'close', None)
            if callable(close_fn):
                import inspect
                try:
                    if inspect.iscoroutinefunction(close_fn):
                        await close_fn()
                    else:
                        close_fn()
                except Exception:
                    pass
            # Close protocol/transport if exposed (redundant but safe)
            try:
                protocol = getattr(old_client, 'protocol', None)
                if protocol is not None:
                    transport = getattr(protocol, 'transport', None)
                    if transport and hasattr(transport, 'close'):
                        try:
                            transport.close()
                        except Exception:
                            pass
            except Exception:
                pass
        finally:
            # Clear ref immediately to prevent new operations
            self.client = None
            # Wait to allow pending callbacks to complete or be cancelled
            # Note: Some callbacks may still fire, but setting sync_serial=None above
            # should prevent AttributeError (though pymodbus may still log errors)
            await asyncio.sleep(0.3)
            # Wait and verify port release via pyserial (if available)
            try:
                await asyncio.sleep(0.2)  # Additional wait for port release
                cfg = await self._get_client_config()
                port = cfg.get('port')
                if port:
                    try:
                        import serial  # type: ignore
                    except Exception:
                        serial = None
                    if serial is not None:
                        for _ in range(4):
                            try:
                                s = await asyncio.to_thread(serial.Serial, port=port, timeout=0.1)
                                try:
                                    await asyncio.to_thread(s.close)
                                except Exception:
                                    pass
                                break
                            except Exception:
                                await asyncio.sleep(0.5)
            except Exception:
                pass


class BatteryAdapter(ABC):
    def __init__(self, bank_cfg):
        self.bank_cfg = bank_cfg

    @abstractmethod
    async def connect(self): ...
    @abstractmethod
    async def close(self): ...
    @abstractmethod
    async def poll(self) -> Any: ...  # returns BatteryBankTelemetry
    
    async def read_serial_number(self) -> Optional[str]:
        """
        Read battery bank serial number for identification.
        Must be implemented by adapters that support auto-discovery.
        Returns None if serial number cannot be read.
        """
        return None  # Default implementation returns None (not supported)
    
    async def check_connectivity(self) -> bool:
        """
        Check if the battery device is connected and responding.
        This method should use a device-specific command to verify connectivity.
        For example, Pytes batteries use 'pwr 1' command.
        
        Returns:
            True if device is connected and responding, False otherwise
        """
        # Default implementation tries to read serial number as connectivity check
        try:
            serial = await self.read_serial_number()
            return serial is not None
        except Exception:
            return False


class MeterAdapter(ABC):
    """Base class for energy meter adapters (grid meters, consumption meters, etc.)"""
    def __init__(self, meter_cfg):
        self.meter_cfg = meter_cfg

    @abstractmethod
    async def connect(self): ...
    
    @abstractmethod
    async def close(self): ...
    
    @abstractmethod
    async def poll(self) -> Any: ...  # returns MeterTelemetry
    
    async def read_serial_number(self) -> Optional[str]:
        """
        Read meter serial number for identification.
        Must be implemented by adapters that support auto-discovery.
        Returns None if serial number cannot be read.
        """
        return None  # Default implementation returns None (not supported)
    
    async def check_connectivity(self) -> bool:
        """
        Check if the meter device is connected and responding.
        This method should use a device-specific command to verify connectivity.
        
        Returns:
            True if device is connected and responding, False otherwise
        """
        # Default implementation tries to read serial number as connectivity check
        try:
            serial = await self.read_serial_number()
            return serial is not None
        except Exception:
            return False


class JsonRegisterMixin:
    """
    Shared helpers for JSON-defined register maps across adapters.

    Adapters using this mixin must implement low-level methods:
      - _read_holding_regs(addr: int, count: int) -> List[int]
      - _write_holding_u16(addr: int, value: int) -> None
      - _write_holding_u16_list(addr: int, values: List[int]) -> None
    and define:
      - self.regs: List[Dict[str, Any]]
      - self.addr_offset: int (optional, default 0)
    """

    regs: List[Dict[str, Any]] = []
    addr_offset: int = 0

    def load_register_map(self, file_path: str) -> None:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                self.regs = json.load(f)
        except Exception as e:
            self.regs = []
            raise RuntimeError(f"Could not load register map {file_path}: {e}")

    @staticmethod
    def _sanitize_key(s: str) -> str:
        return "".join(ch if ch.isalnum() else "_" for ch in str(s).lower()).strip("_")

    def _find_reg_by_id_or_name(self, ident: str) -> Dict[str, Any]:
        ident_s = self._sanitize_key(ident)
        for r in self.regs:
            rid = r.get("id") or r.get("name") or (f"reg_{int(r['addr']):04x}" if "addr" in r else None)
            if rid and self._sanitize_key(rid) == ident_s:
                return r
        for r in self.regs:
            nm = r.get("name")
            if isinstance(nm, str) and self._sanitize_key(nm) == ident_s:
                return r
        raise KeyError(f"register not found: {ident}")

    @staticmethod
    def _encode_hhmm(val: str) -> int:
        """
        Encode HH:MM time format as byte-packed: (H << 8) | M
        Used by Senergy inverters.
        Example: "23:59" -> 0x173B (5947 decimal)
        """
        import logging
        log = logging.getLogger(__name__)
        try:
            # Parse HH:MM format
            parts = str(val).split(":", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid time format '{val}': expected HH:MM")
            h, m = [int(x) for x in parts]
            if not (0 <= h <= 23):
                raise ValueError(f"Invalid hour '{h}' in time '{val}': must be 0-23")
            if not (0 <= m <= 59):
                raise ValueError(f"Invalid minute '{m}' in time '{val}': must be 0-59")
            encoded = ((h & 0xFF) << 8) | (m & 0xFF)
            log.debug(f"Encoded time '{val}' (byte-packed): hour={h}, minute={m} -> 0x{encoded:04X} ({encoded})")
            return encoded
        except Exception as e:
            log.error(f"Failed to encode time '{val}': {e}", exc_info=True)
            raise ValueError(f"Invalid time format '{val}': {e}") from e

    @staticmethod
    def _encode_hhmm_decimal(val: str) -> int:
        """
        Encode HH:MM time format as decimal integer: HH * 100 + MM
        Used by Powdrive inverters.
        Example: "23:59" -> 2359, "00:00" -> 0
        """
        import logging
        log = logging.getLogger(__name__)
        try:
            # Parse HH:MM format
            parts = str(val).split(":", 1)
            if len(parts) != 2:
                raise ValueError(f"Invalid time format '{val}': expected HH:MM")
            h, m = [int(x) for x in parts]
            if not (0 <= h <= 23):
                raise ValueError(f"Invalid hour '{h}' in time '{val}': must be 0-23")
            if not (0 <= m <= 59):
                raise ValueError(f"Invalid minute '{m}' in time '{val}': must be 0-59")
            # Powdrive format: HHMM as decimal (2359 = 23:59)
            encoded = h * 100 + m
            log.debug(f"Encoded time '{val}' (decimal HHMM): hour={h}, minute={m} -> {encoded} (0x{encoded:04X})")
            return encoded
        except Exception as e:
            log.error(f"Failed to encode time '{val}' (decimal format): {e}", exc_info=True)
            raise ValueError(f"Invalid time format '{val}': {e}") from e

    def _encode_value(self, r: Dict[str, Any], value: Any) -> List[int]:
        import logging
        log = logging.getLogger(__name__)
        enc = (r.get("encoder") or "").lower()
        size = max(1, int(r.get("size", 1)))
        t = (r.get("type") or "").lower()
        enum = r.get("enum") or None
        reg_id = r.get('id') or r.get('name') or 'unknown'
        
        log.debug(f"Encoding value for register '{reg_id}': value={value} (type={type(value).__name__}), encoder={enc}, type={t}, size={size}")
        
        # Bounds validation
        try:
            vnum = float(value)
            if "min" in r and isinstance(r["min"], (int, float)) and vnum < float(r["min"]):
                log.warning(f"Value {vnum} below minimum {r['min']} for register '{reg_id}', clamping to {r['min']}")
                vnum = float(r["min"])
            if "max" in r and isinstance(r["max"], (int, float)) and vnum > float(r["max"]):
                log.warning(f"Value {vnum} above maximum {r['max']} for register '{reg_id}', clamping to {r['max']}")
                vnum = float(r["max"])
            value = vnum
        except Exception as e:
            log.debug(f"Could not convert value to float for initial bounds check: {e}")
            pass

        # Enum coercion: allow label or raw
        if enum and isinstance(enum, dict):
            labels = {str(v): str(k) for k, v in enum.items()}
            sv = str(value)
            if sv in labels:
                value = labels[sv]

        if enc == "hhmm":
            # Check if this is Powdrive-style HHMM decimal format (2359 = 23:59)
            # vs byte-packed format ((H << 8) | M)
            # Powdrive registers have comment indicating decimal format
            comment = str(r.get("comment", "")).lower()
            is_powdrive_format = "2359" in comment or "format: 2359" in comment
            log.debug(f"Time encoding for register '{reg_id}': format detected as {'Powdrive decimal (HHMM)' if is_powdrive_format else 'Senergy byte-packed ((H<<8)|M)'}")
            if is_powdrive_format:
                # Powdrive-style: HHMM as decimal integer (2359 = 23:59)
                return [self._encode_hhmm_decimal(value)]
            else:
                # Senergy-style: byte-packed format ((H << 8) | M)
                return [self._encode_hhmm(value)]
        if enc == "bool":
            return [1 if (str(value).lower() in ("1","true","on","enable","enabled")) else 0]
        if enc == "ascii":
            s = str(value)
            # pack into 16-bit words big-endian per word
            out: List[int] = []
            buf = s.encode("ascii", errors="ignore")
            if len(buf) % 2 == 1:
                buf += b"\x00"
            for i in range(0, len(buf), 2):
                out.append(((buf[i] & 0xFF) << 8) | (buf[i+1] & 0xFF))
            return out[:size]

        # Numeric
        try:
            v = float(value)
        except Exception:
            log.error(f"Invalid numeric value '{value}' for register '{r.get('id') or r.get('name')}'")
            raise ValueError(f"{r.get('id') or r.get('name')}: invalid numeric value '{value}'")

        scale = r.get("scale")
        original_v = v
        if scale not in (None, 0) and isinstance(scale, (int, float)):
            v = v / float(scale)
            log.debug(f"Applied scale {scale} to value {original_v} -> {v}")
        
        # Check bounds after scaling
        if "min" in r and isinstance(r["min"], (int, float)):
            min_scaled = float(r["min"]) / float(scale) if scale not in (None, 0) else float(r["min"])
            if v < min_scaled:
                log.warning(f"Value {v} below minimum {min_scaled} for register '{r.get('id') or r.get('name')}', clamping to {min_scaled}")
                v = min_scaled
        if "max" in r and isinstance(r["max"], (int, float)):
            max_scaled = float(r["max"]) / float(scale) if scale not in (None, 0) else float(r["max"])
            if v > max_scaled:
                log.warning(f"Value {v} above maximum {max_scaled} for register '{r.get('id') or r.get('name')}', clamping to {max_scaled}")
                v = max_scaled
        
        iv = int(v)
        if size == 1:
            encoded = [iv & 0xFFFF]
            log.debug(f"Encoded numeric value {original_v} (after scale={scale}) -> {iv} (0x{iv:04X}) for register '{r.get('id') or r.get('name')}'")
            return encoded
        if size == 2:
            encoded = [(iv >> 16) & 0xFFFF, iv & 0xFFFF]
            log.debug(f"Encoded numeric value {original_v} (after scale={scale}) -> {iv} (0x{iv>>16:04X} 0x{iv&0xFFFF:04X}) for register '{r.get('id') or r.get('name')}'")
            return encoded
        raise ValueError(f"Unsupported size {size} for register '{r.get('id') or r.get('name')}'")

    def _decode_words(self, r: Dict[str, Any], regs: List[int]) -> Any:
        t = (r.get("type") or "").lower()
        size = max(1, int(r.get("size", 1)))
        scale = r.get("scale")
        enc = (r.get("encoder") or "").lower()

        # ASCII decoder for multi-word strings
        if enc == "ascii":
            buf = bytearray()
            for w in regs[:size]:
                w = int(w) & 0xFFFF
                buf.append((w >> 8) & 0xFF)
                buf.append(w & 0xFF)
            try:
                return bytes(buf).split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
            except Exception:
                return ""

        # Apply bitmask / higherBits before numeric decode when specified
        bitmask = r.get("bitmask")
        if bitmask and regs:
            regs = [(int(regs[0]) & int(bitmask))]
            if r.get("higherBits"):
                regs = [(regs[0] >> 8) & 0xFF]

        if size == 1 and regs:
            val = int(regs[0])
            if "s16" in t and val >= 0x8000:
                val = val - 0x10000
        elif size == 2 and regs and len(regs) >= 2:
            hi, lo = regs[0], regs[1]
            val = (hi << 16) | lo
            if "s32" in t and val & 0x80000000:
                val = -((~val & 0xFFFFFFFF) + 1)
        else:
            val = 0

        if scale and isinstance(val, (int, float)):
            val = val * scale
        # Map bit_enum to list of active labels if configured
        bit_enum = r.get("bit_enum")
        if isinstance(bit_enum, dict) and isinstance(val, int):
            msgs = []
            for k, v in bit_enum.items():
                try:
                    bit = int(k, 10)
                except Exception:
                    bit = int(str(k), 16) if str(k).lower().startswith("0x") else int(str(k))
                if val & (1 << bit):
                    msgs.append(str(v))
            return msgs if msgs else ["OK"]
        return val

    async def read_by_ident(self, ident: str) -> Any:
        r = self._find_reg_by_id_or_name(ident)
        if (r.get("kind") or "").lower() not in ("holding", "input"):
            raise RuntimeError("unsupported register kind for read")
        addr = int(r["addr"]) + getattr(self, "addr_offset", 0)
        size = max(1, int(r.get("size", 1)))
        regs = await self._read_holding_regs(addr, size)
        return self._decode_words(r, regs)
    
    async def read_all_registers(self) -> Dict[str, Any]:
        """
        Read all registers from the register map.
        
        Returns:
            Dictionary mapping register id to decoded value
        """
        values: Dict[str, Any] = {}
        for reg in self.regs:
            reg_id = reg.get("id")
            if not reg_id:
                continue
            
            # Skip write-only registers
            if str(reg.get("rw", "RO")).upper() in ("WO", "Write-Only"):
                continue
            
            # Only read holding/input registers
            kind = (reg.get("kind") or "").lower()
            if kind not in ("holding", "input"):
                continue
            
            try:
                value = await self.read_by_ident(reg_id)
                values[reg_id] = value
            except Exception as e:
                log.debug(f"Failed to read register {reg_id}: {e}")
                # Continue reading other registers even if one fails
                continue
        
        return values

    async def write_by_ident(self, ident: str, value: Any) -> None:
        r = self._find_reg_by_id_or_name(ident)
        if (r.get("kind") or "").lower() != "holding":
            raise RuntimeError(f"{ident}: register is not holding (write not allowed)")
        if str(r.get("rw", "RO")).upper() not in ("RW", "WO", "R/W"):
            raise RuntimeError(f"{ident}: register is read-only")
        words = self._encode_value(r, value)
        addr = int(r["addr"]) + getattr(self, "addr_offset", 0)
        
        # Log the write operation with details
        import logging
        log = logging.getLogger(__name__)
        log.debug(f"Writing register '{ident}' (addr=0x{addr:04X}, type={r.get('type')}, encoder={r.get('encoder')}): "
                  f"value={value} (type={type(value).__name__}) -> encoded={words}")
        
        # Log validation details
        if "min" in r or "max" in r:
            log.debug(f"Register '{ident}' bounds: min={r.get('min')}, max={r.get('max')}")
        if r.get("enum"):
            log.debug(f"Register '{ident}' has enum mapping: {r.get('enum')}")
        
        if len(words) == 1:
            await self._write_holding_u16(addr, words[0])
            log.debug(f"✓ Wrote register '{ident}' (addr=0x{addr:04X}): {words[0]}")
        else:
            await self._write_holding_u16_list(addr, words)
            log.debug(f"✓ Wrote register '{ident}' (addr=0x{addr:04X}): {words}")
