import logging
import asyncio
from typing import Any, Dict, Optional, List

from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

from solarhub.adapters.base import InverterAdapter, JsonRegisterMixin, ModbusClientMixin
from solarhub.models import Telemetry
from solarhub.timezone_utils import now_configured_iso
from solarhub.telemetry_mapper import TelemetryMapper


log = logging.getLogger(__name__)


def _s16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


class PowdriveAdapter(InverterAdapter, JsonRegisterMixin, ModbusClientMixin):
    """
    Minimal RTU adapter for Powdrive (12k) based on provided register spec.
    Produces standard Telemetry so higher layers (DB/API/Scheduler/UI) remain unchanged.

    Notes:
    - We start with a focused subset of registers required for the UI/scheduler.
    - Additional fields can be added later by extending _read_block/_decode methods.
    """

    def __init__(self, inv):
        super().__init__(inv)
        self.client: Optional[AsyncModbusSerialClient | AsyncModbusTcpClient] = None
        self.unit_id: int = getattr(inv.adapter, "unit_id", 1) or 1
        # Get transport from adapter config, defaulting to "rtu" if not specified
        transport_raw = getattr(inv.adapter, "transport", "rtu")
        self.transport: str = str(transport_raw).lower() if transport_raw else "rtu"
        log.info(f"PowdriveAdapter initialized for {inv.id}: transport={self.transport}, unit_id={self.unit_id}, "
                 f"adapter.type={getattr(inv.adapter, 'type', 'unknown')}, "
                 f"adapter.has_transport={hasattr(inv.adapter, 'transport')}, "
                 f"adapter.transport_value={getattr(inv.adapter, 'transport', 'NOT_SET')}")
        self.last_tel: Optional[Telemetry] = None
        # Initialize regs to empty list (will be populated by load_register_map)
        # Note: JsonRegisterMixin has regs as a class variable, but we initialize instance variable
        self.regs: List[Dict[str, Any]] = []
        self.addr_offset: int = 0
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None  # Event loop where client was created
        self._modbus_lock: Optional[asyncio.Lock] = None  # Lock to serialize Modbus operations
        self._client_migrated: bool = False  # Track if client has been migrated to current loop
        
        # JSON register map support - always try to load
        from pathlib import Path
        import os
        
        regfile = getattr(inv.adapter, "register_map_file", None) or "register_maps/powdrive_registers.json"
        tried_paths = []
        path = None
        
        # Strategy 1: If regfile is absolute, use it directly
        if Path(regfile).is_absolute():
            path = Path(regfile)
            tried_paths.append(str(path))
            if path.exists():
                log.debug("Using absolute path for register map: %s", path)
            else:
                path = None
        
        # Strategy 2: Resolve relative to project root (two levels up from adapters/)
        # From /home/solar-hub/solarhub/adapters/powdrive.py -> /home/solar-hub/register_maps/powdrive_registers.json
        # This is the primary path for server deployment
        if path is None:
            base = Path(__file__).resolve().parents[2]  # Goes: adapters -> solarhub -> solar-hub
            # Try explicit register_maps subdirectory first (most common case)
            default_path = (base / "register_maps" / "powdrive_registers.json").resolve()
            tried_paths.append(str(default_path))
            if default_path.exists():
                path = default_path
                log.debug("Using project root register_maps path for register map: %s", path)
            else:
                # Fallback to using regfile as-is (in case it contains the full relative path)
                cand = (base / regfile).resolve()
                tried_paths.append(str(cand))
                if cand.exists():
                    path = cand
                    log.debug("Using project-relative path for register map: %s", path)
        
        # Strategy 3b: Try one level up from solarhub (if solarhub is in project root)
        if path is None:
            solarhub_base = Path(__file__).resolve().parents[1]
            cand = (solarhub_base.parent / regfile).resolve()
            tried_paths.append(str(cand))
            if cand.exists():
                path = cand
                log.debug("Using parent-of-solarhub path for register map: %s", path)
        
        # Strategy 3c: Try one level up from solarhub with default filename
        if path is None:
            solarhub_base = Path(__file__).resolve().parents[1]
            default_path = (solarhub_base.parent / "register_maps/powdrive_registers.json").resolve()
            tried_paths.append(str(default_path))
            if default_path.exists():
                path = default_path
                log.debug("Using parent-of-solarhub default path for register map: %s", path)
        
        # Strategy 4: Try relative to current working directory
        if path is None:
            cwd_path = Path(os.getcwd()) / regfile
            tried_paths.append(str(cwd_path))
            if cwd_path.exists():
                path = cwd_path
                log.debug("Using CWD-relative path for register map: %s", path)
        
        # Strategy 5: Try relative to current working directory with default filename
        if path is None:
            cwd_default = Path(os.getcwd()) / "register_maps/powdrive_registers.json"
            tried_paths.append(str(cwd_default))
            if cwd_default.exists():
                path = cwd_default
                log.debug("Using CWD default path for register map: %s", path)
        
        # Strategy 6: Try in same directory as this file (for development)
        if path is None:
            file_dir = Path(__file__).resolve().parent
            cand = file_dir / regfile
            tried_paths.append(str(cand))
            if cand.exists():
                path = cand
                log.debug("Using same-dir-as-file path for register map: %s", path)
        
        # Strategy 7: Try in parent directories going up from __file__
        if path is None:
            current = Path(__file__).resolve()
            for level in range(1, 6):  # Try up to 5 levels up
                parent = current.parents[level]
                # Try with the specified filename
                cand = parent / regfile
                tried_paths.append(str(cand))
                if cand.exists():
                    path = cand
                    log.debug("Using parent-level-%d path for register map: %s", level, path)
                    break
                # Also try default filename
                default_cand = parent / "register_maps/powdrive_registers.json"
                tried_paths.append(str(default_cand))
                if default_cand.exists():
                    path = default_cand
                    log.debug("Using parent-level-%d default path for register map: %s", level, path)
                    break
        
        # Strategy 8: Try inside solarhub/register_maps (for package-based deployments)
        if path is None:
            solarhub_dir = Path(__file__).resolve().parent.parent
            cand = solarhub_dir / "register_maps" / "powdrive_registers.json"
            tried_paths.append(str(cand))
            if cand.exists():
                path = cand
                log.debug("Using solarhub/register_maps path for register map: %s", path)
        
        # Strategy 9: Try in register_maps subdirectory of each parent level
        if path is None:
            current = Path(__file__).resolve()
            for level in range(1, 6):  # Try up to 5 levels up
                parent = current.parents[level]
                cand = parent / "register_maps" / "powdrive_registers.json"
                tried_paths.append(str(cand))
                if cand.exists():
                    path = cand
                    log.debug("Using parent-level-%d register_maps path for register map: %s", level, path)
                    break
        
        # Always try to load - fail loudly if file doesn't exist
        if path is None or not path.exists():
            log.error("Powdrive register map file not found after trying all paths")
            log.error("Tried paths: %s", ", ".join(tried_paths))
            log.error("Current working directory: %s", os.getcwd())
            log.error("__file__ location: %s", __file__)
            log.error("__file__ parents: %s", [str(p) for p in Path(__file__).resolve().parents[:6]])
            if 'base' in locals():
                log.error("Base path (parents[2]): %s", base)
            raise FileNotFoundError(f"Powdrive register map file not found. Tried: {', '.join(tried_paths)}")
        
        # Load the register map
        try:
            log.debug("Loading Powdrive register map from: %s", path)
            self.load_register_map(str(path))
            if not self.regs or len(self.regs) == 0:
                log.error("Powdrive register map loaded but is empty: %s", path)
                raise ValueError(f"Register map file is empty or invalid: {path}")
            log.info("Powdrive register map loaded successfully: %s (%d regs)", path, len(self.regs))
            
            # Create telemetry mapper for standardized field names
            self.mapper = TelemetryMapper(self.regs)
            log.debug("Telemetry mapper created with %d mappings", len(self.mapper.device_to_standard))
        except Exception as e:
            log.error("Failed to load Powdrive register map from %s: %s", path, e, exc_info=True)
            raise RuntimeError(f"Failed to load Powdrive register map: {e}") from e

    async def connect(self):
        # Use the same lock as _ensure_client_in_current_loop to prevent concurrent access
        if not hasattr(self, '_client_recreate_guard'):
            self._client_recreate_guard = asyncio.Lock()
        
        async with self._client_recreate_guard:
            # Log stack trace to see who's calling connect()
            import traceback
            stack = traceback.extract_stack()
            callers = []
            for i in range(min(5, len(stack) - 1)):
                frame = stack[-(i+2)] if len(stack) > i+1 else None
                if frame:
                    filename = frame.filename.split('/')[-1] if '/' in frame.filename else frame.filename.split('\\')[-1]
                    callers.append(f"{filename}:{frame.lineno}({frame.name})")
            caller_info = " <- ".join(callers) if callers else "unknown"
            log.info(f"Powdrive connect() called from: {caller_info}")
            
            # FIRST: Check if client is already connected - if so, skip connection attempt
            if hasattr(self, 'client') and self.client is not None:
                if hasattr(self.client, 'connected') and self.client.connected:
                    # For RTU: verify port exists; for TCP: just check connection status
                    if self.transport == "rtu":
                        port = self.inv.adapter.serial_port
                        if port:
                            try:
                                import os
                                if os.path.exists(port):
                                    log.debug(f"Powdrive client already connected to {port}, skipping connect() (called from: {caller_info})")
                                    return
                            except Exception:
                                pass  # If check fails, continue with normal flow
                    else:  # TCP
                        log.debug(f"Powdrive TCP client already connected, skipping connect() (called from: {caller_info})")
                        return
            
            # Double-check after acquiring lock (might have changed)
            if hasattr(self, 'client') and self.client is not None:
                if hasattr(self.client, 'connected') and self.client.connected:
                    if self.transport == "rtu":
                        port = self.inv.adapter.serial_port
                        if port:
                            try:
                                import os
                                if os.path.exists(port):
                                    log.debug(f"Powdrive client already connected to {port} after lock acquisition, skipping connect()")
                                    return
                            except Exception:
                                pass
                    else:  # TCP
                        log.debug(f"Powdrive TCP client already connected after lock acquisition, skipping connect()")
                        return
            
            # Validate transport and required parameters
            if self.transport == "tcp":
                # TCP Modbus connection
                if not self.inv.adapter.host:
                    raise RuntimeError("host is required for TCP transport")
                port = getattr(self.inv.adapter, "port", 502)
                
                log.info(
                    "Powdrive connecting via TCP (host=%s, port=%s, unit_id=%s, timeout=%s) - called from: %s",
                    self.inv.adapter.host,
                    port,
                    self.unit_id,
                    getattr(self.inv.adapter, "timeout", 2.0),
                    caller_info,
                )
                
                # Use longer timeout for TCP connections (default 5.0s instead of 2.0s)
                # TCP connections may take longer due to network latency, firewall checks, etc.
                tcp_timeout = getattr(self.inv.adapter, "timeout", 5.0)
                self.client = AsyncModbusTcpClient(
                    host=self.inv.adapter.host,
                    port=port,
                    timeout=tcp_timeout,
                )
                log.info(f"Attempting TCP connection to {self.inv.adapter.host}:{port} (timeout={tcp_timeout}s)...")
                try:
                    ok = await self.client.connect()
                except Exception as connect_ex:
                    log.error(f"TCP connect() raised exception: {connect_ex}")
                    log.error(f"  Exception type: {type(connect_ex).__name__}")
                    log.error(f"  Troubleshooting: Check if {self.inv.adapter.host} is reachable (ping), verify port {port} is open, check firewall rules")
                    raise RuntimeError(f"Modbus TCP connection failed to {self.inv.adapter.host}:{port}: {connect_ex}") from connect_ex
                
                if not ok:
                    log.error(f"TCP connect() returned False for {self.inv.adapter.host}:{port}")
                    log.error(f"  Troubleshooting: Host may be unreachable, port may be blocked by firewall, or device may not be responding")
                    log.error(f"  Try: ping {self.inv.adapter.host}, telnet {self.inv.adapter.host} {port}, or check device status")
                    raise RuntimeError(f"Modbus TCP connection failed to {self.inv.adapter.host}:{port} (connect() returned False)")
                if not self.client.connected:
                    log.error(f"TCP client.connected is False for {self.inv.adapter.host}:{port}")
                    log.error(f"  Troubleshooting: Connection was not established - check network connectivity and device status")
                    raise RuntimeError(f"Modbus TCP connection failed to {self.inv.adapter.host}:{port} (client.connected is False)")
                log.info(f"✓ PowdriveAdapter connected via TCP to {self.inv.adapter.host}:{port}")
                
            elif self.transport == "rtu":
                # RTU Modbus connection (serial)
                if not self.inv.adapter.serial_port:
                    raise RuntimeError("serial_port is required for RTU transport")
                
                port = self.inv.adapter.serial_port
                
                # Check if port exists before attempting connection
                if port:
                    try:
                        import os
                        if not os.path.exists(port):
                            log.warning(f"Powdrive port {port} does not exist - cannot connect. Device may be disconnected. Called from: {caller_info}")
                            raise RuntimeError(f"Port {port} does not exist")
                    except ImportError:
                        pass
                    except Exception as e:
                        log.debug(f"Error checking port existence: {e}")

                log.info(
                    "Powdrive connecting via RTU (port=%s, baud=%s, parity=%s, stopbits=%s, bytesize=%s, unit_id=%s) - called from: %s",
                    port,
                    self.inv.adapter.baudrate,
                    self.inv.adapter.parity,
                    self.inv.adapter.stopbits,
                    self.inv.adapter.bytesize,
                    self.unit_id,
                    caller_info,
                )
                
                self.client = AsyncModbusSerialClient(
                    port=port,
                    baudrate=self.inv.adapter.baudrate,
                    parity=self.inv.adapter.parity,
                    stopbits=self.inv.adapter.stopbits,
                    bytesize=self.inv.adapter.bytesize,
                    timeout=getattr(self.inv.adapter, "timeout", 2.0),
                )
                try:
                    ok = await self.client.connect()
                except Exception as connect_ex:
                    log.error(f"RTU connect() raised exception: {connect_ex}")
                    log.error(f"  Exception type: {type(connect_ex).__name__}")
                    raise RuntimeError(f"Modbus RTU connection failed to {port}: {connect_ex}") from connect_ex
                
                if not ok:
                    log.error(f"RTU connect() returned False for {port}")
                    raise RuntimeError(f"Modbus RTU connection failed to {port} (connect() returned False)")
                if not self.client.connected:
                    log.error(f"RTU client.connected is False for {port}")
                    raise RuntimeError(f"Modbus RTU connection failed to {port} (client.connected is False)")
                log.info("Powdrive RTU client connected on %s (ok=%s, connected=%s)", self.inv.adapter.serial_port, ok, self.client.connected)
            else:
                raise RuntimeError(f"Unsupported transport type: {self.transport}. Must be 'rtu' or 'tcp'")
            
            # Store the event loop where the client was created
            try:
                self._client_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._client_loop = asyncio.get_event_loop()
            # Do not create the lock here to avoid binding it to the wrong loop.
            # The lock will be (re)created lazily in the current loop via _ensure_lock_in_current_loop().

    async def close(self):
        try:
            log.info("Powdrive close() called - starting client shutdown")
            # Use robust close to ensure port release
            if hasattr(self, '_force_close_client'):
                await self._force_close_client()
            else:
                if self.client:
                    close_fn = getattr(self.client, "close", None)
                    if callable(close_fn):
                        import inspect
                        if inspect.iscoroutinefunction(close_fn):
                            await close_fn()
                        else:
                            close_fn()
                self.client = None
            log.info("Powdrive close() completed - client reference cleared")
        except Exception as e:
            log.warning(f"Powdrive close() encountered error: {e}")
        finally:
            # Drop the loop-bound lock so it is recreated in the next active loop
            if hasattr(self, '_modbus_lock'):
                self._modbus_lock = None
            self._client_migrated = False  # Reset migration flag when closing
    
    async def _get_client_config(self) -> Dict[str, Any]:
        """Get configuration for creating Modbus client (RTU or TCP)."""
        if self.transport == "tcp":
            return {
                'host': self.inv.adapter.host,
                'port': getattr(self.inv.adapter, "port", 502),
                'timeout': getattr(self.inv.adapter, "timeout", 5.0),  # Default 5.0s for TCP (longer than RTU)
            }
        else:  # RTU
            return {
                'port': self.inv.adapter.serial_port,
                'baudrate': self.inv.adapter.baudrate,
                'parity': self.inv.adapter.parity,
                'stopbits': self.inv.adapter.stopbits,
                'bytesize': self.inv.adapter.bytesize,
                'timeout': getattr(self.inv.adapter, "timeout", 2.0),
            }

    async def _read_u16(self, addr: int, count: int = 1) -> List[int]:
        # Get connection identifier for logging (port for RTU, host:port for TCP)
        if self.transport == "tcp":
            conn_id = f"{self.inv.adapter.host}:{getattr(self.inv.adapter, 'port', 502)}"
        else:
            conn_id = getattr(self.inv.adapter, 'serial_port', 'unknown')
        
        if not self.client:
            log.warning(f"POWDRIVE _read_u16: No client for {self.inv.id} on {conn_id} (addr=0x{addr:04X})")
            raise RuntimeError("client not connected")
        
        # Check if client is connected
        # Note: We trust client.connected for now. If the connection is actually broken,
        # the read operation below will fail and we handle that in the exception handler.
        # The health check was causing too many false positives with RTU connections.
        if not hasattr(self.client, 'connected') or not self.client.connected:
            # Client not connected - check port existence first (RTU only) to avoid spam
            if self.transport == "rtu":
                import os
                port = self.inv.adapter.serial_port
                if port and not os.path.exists(port):
                    # Port doesn't exist - fail immediately without trying to reconnect
                    log.debug(f"POWDRIVE _read_u16: Port {port} does not exist for {self.inv.id} (addr=0x{addr:04X}) - failing immediately")
                    raise RuntimeError(f"Port {port} does not exist")
            
            # Client not connected - try to reconnect
            log.info(f"POWDRIVE _read_u16: Client not connected for {self.inv.id} on {conn_id} (addr=0x{addr:04X}), ensuring client in current loop...")
            try:
                # Use _ensure_client_in_current_loop which has proper locking
                await self._ensure_client_in_current_loop()
                await self._ensure_lock_in_current_loop()
                # Verify connection after ensuring client
                if not self.client:
                    log.error(f"POWDRIVE _read_u16: Client is None after _ensure_client_in_current_loop for {self.inv.id} on {conn_id} (addr=0x{addr:04X})")
                    raise RuntimeError("client is None after _ensure_client_in_current_loop")
                if not hasattr(self.client, 'connected'):
                    log.error(f"POWDRIVE _read_u16: Client has no 'connected' attribute for {self.inv.id} on {conn_id} (addr=0x{addr:04X})")
                    raise RuntimeError("client has no 'connected' attribute")
                if not self.client.connected:
                    # For TCP, try to get more diagnostic info
                    if self.transport == "tcp":
                        host = getattr(self.inv.adapter, 'host', 'unknown')
                        port = getattr(self.inv.adapter, 'port', 502)
                        log.error(f"POWDRIVE _read_u16: TCP client not connected for {self.inv.id} on {host}:{port} (addr=0x{addr:04X})")
                        log.error(f"  Client type: {type(self.client)}")
                        log.error(f"  Client connected status: {getattr(self.client, 'connected', 'N/A')}")
                        # Try to get socket info if available
                        if hasattr(self.client, 'socket'):
                            log.error(f"  Socket: {self.client.socket}")
                    else:
                        log.error(f"POWDRIVE _read_u16: RTU client not connected for {self.inv.id} on {conn_id} (addr=0x{addr:04X})")
                    raise RuntimeError("client not connected after _ensure_client_in_current_loop")
                log.info(f"POWDRIVE _read_u16: Successfully ensured client connection for {self.inv.id} on {conn_id}")
            except Exception as e:
                # Log reconnection errors with more detail
                error_str = str(e).lower()
                if self.transport == "rtu":
                    if "no such file" in error_str or "no such device" in error_str or "does not exist" in error_str:
                        log.warning(f"POWDRIVE _read_u16: Port {conn_id} does not exist for {self.inv.id} (addr=0x{addr:04X}): {e}")
                    elif "could not exclusively lock" in error_str or "resource temporarily unavailable" in error_str:
                        log.warning(f"POWDRIVE _read_u16: Port {conn_id} is locked (likely in use) for {self.inv.id} (addr=0x{addr:04X}): {e}")
                    else:
                        log.warning(f"POWDRIVE _read_u16: Failed to ensure RTU client connection for {self.inv.id} on {conn_id} (addr=0x{addr:04X}): {e}")
                else:  # TCP
                    host = getattr(self.inv.adapter, 'host', 'unknown')
                    port = getattr(self.inv.adapter, 'port', 502)
                    log.error(f"POWDRIVE _read_u16: Failed to ensure TCP client connection for {self.inv.id} on {host}:{port} (addr=0x{addr:04X})")
                    log.error(f"  Error: {e}")
                    log.error(f"  Error type: {type(e).__name__}")
                    # Check if host/port are configured
                    if not hasattr(self.inv.adapter, 'host') or not self.inv.adapter.host:
                        log.error(f"  ⚠️  Host not configured in adapter!")
                    if not hasattr(self.inv.adapter, 'port'):
                        log.error(f"  ⚠️  Port not configured in adapter (using default 502)")
                raise RuntimeError(f"client not connected: {e}") from e
        
        # Final check before calling pymodbus - ensure client is actually connected
        # This prevents pymodbus from trying to auto-reconnect internally
        if not self.client or not hasattr(self.client, 'connected') or not self.client.connected:
            log.warning(f"POWDRIVE _read_u16: Client not connected before read for {self.inv.id} on {conn_id} (addr=0x{addr:04X})")
            raise RuntimeError("client not connected before read")
        
        # Note: We don't verify socket/transport here because:
        # 1. Pymodbus doesn't expose these attributes reliably
        # 2. The actual read operation will fail if the connection is broken
        # 3. We handle read errors below and force reconnection if needed
        # 4. Checking client.connected is sufficient - if it's wrong, the read will fail and we'll handle it
        
        # Use lock to serialize Modbus operations (RTU is half-duplex)
        # Ensure lock is in current loop before using it
        await self._ensure_lock_in_current_loop()
        
        if self._modbus_lock:
            try:
                async with self._modbus_lock:
                    rr = await self.client.read_holding_registers(address=addr, count=count, device_id=self.inv.adapter.unit_id)
                    if rr.isError():  # type: ignore
                        raise RuntimeError(f"read error at 0x{addr:04X}: {rr}")
                    return list(rr.registers)  # type: ignore[attr-defined]
            except (RuntimeError, ValueError, AttributeError, OSError, FileNotFoundError) as e:
                # Catch FileNotFoundError (port doesn't exist) and handle it
                error_str = str(e).lower()
                if self.transport == "rtu" and ("no such file" in error_str or "no such device" in error_str or isinstance(e, FileNotFoundError)):
                    log.warning(f"POWDRIVE _read_u16: Port {conn_id} does not exist during read for {self.inv.id} (addr=0x{addr:04X}) - connection may be broken")
                    # Mark connection as broken and force reconnection
                    if hasattr(self.client, 'connected'):
                        self.client.connected = False
                    # Force reconnection attempt
                    await self._force_close_client()
                    await asyncio.sleep(0.5)
                    await self._ensure_client_in_current_loop()
                    await self._ensure_lock_in_current_loop()
                    # Retry the read
                    async with self._modbus_lock:
                        rr = await self.client.read_holding_registers(address=addr, count=count, device_id=self.inv.adapter.unit_id)
                        if rr.isError():  # type: ignore
                            raise RuntimeError(f"read error at 0x{addr:04X} after reconnection: {rr}")
                        return list(rr.registers)  # type: ignore[attr-defined]
                # If lock is bound to different event loop (ours or pymodbus's), recreate client and retry
                error_str = str(e)  # Re-assign for remaining checks
                if "bound to a different event loop" in error_str or "different event loop" in error_str.lower():
                    log.warning("Lock bound to different loop, recreating client and lock in current loop")
                    # Recreate the client (which will recreate its internal lock) in the current loop
                    await self._force_close_client()
                    await asyncio.sleep(0.1)  # Brief delay before recreating
                    await self._ensure_client_in_current_loop()
                    await self._ensure_lock_in_current_loop()
                    async with self._modbus_lock:
                        rr = await self.client.read_holding_registers(address=addr, count=count, device_id=self.inv.adapter.unit_id)
                        if rr.isError():  # type: ignore
                            raise RuntimeError(f"read error at 0x{addr:04X}: {rr}")
                        return list(rr.registers)  # type: ignore[attr-defined]
                if "Bad file descriptor" in error_str:
                    log.warning("Bad file descriptor, recreating client and retrying read")
                    await self._force_close_client()
                    await asyncio.sleep(0.5)
                    await self._ensure_client_in_current_loop()
                    await self._ensure_lock_in_current_loop()
                    async with self._modbus_lock:
                        rr = await self.client.read_holding_registers(address=addr, count=count, device_id=self.inv.adapter.unit_id)
                        if rr.isError():  # type: ignore
                            raise RuntimeError(f"read error at 0x{addr:04X}: {rr}")
                        return list(rr.registers)  # type: ignore[attr-defined]
                else:
                    raise
        else:
            # Fallback if lock not initialized
            rr = await self.client.read_holding_registers(address=addr, count=count, device_id=self.inv.adapter.unit_id)
            if rr.isError():  # type: ignore
                raise RuntimeError(f"read error at 0x{addr:04X}: {rr}")
            return list(rr.registers)  # type: ignore[attr-defined]

    # JsonRegisterMixin low-level hooks
    async def _read_holding_regs(self, addr: int, count: int) -> List[int]:
        return await self._read_u16(addr, count)

    async def _write_holding_u16(self, addr: int, value: int) -> None:
        """
        Write a single holding register.
        
        According to Powdrive spec: registers 60-499 must use function code 16 (0x10)
        "Write Multiple Holding Registers", even for single register writes.
        This matches minimalmodbus library behavior which uses function code 16 for writes.
        
        Function code 6 (0x06) "Write Single Holding Register" is only for registers < 60
        (special single-byte functions).
        
        Function codes:
        - 0x06 (6): Write Single Holding Register - for registers < 60
        - 0x10 (16): Write Multiple Holding Registers - for registers >= 60 (matches minimalmodbus)
        """
        if not self.client:
            raise RuntimeError("client not connected")
        
        # Ensure client and lock are in current event loop
        await self._ensure_client_in_current_loop()
        await self._ensure_lock_in_current_loop()
        
        # According to Powdrive spec: registers 60-499 use function code 16 (0x10)
        # even for single register writes. This matches minimalmodbus library behavior.
        # Function code 6 (0x06) is only for special cases with addresses < 60.
        use_function_16 = addr >= 60
        
        func_code = '16 (0x10)' if use_function_16 else '6 (0x06)'
        log.info(f"Modbus write: addr=0x{addr:04X} (dec={addr}), value={value} (0x{value:04X}), "
                 f"unit_id={self.inv.adapter.unit_id}, using function_code={func_code} "
                 f"(addr >= 60: {use_function_16})")
        
        # Use lock to serialize Modbus operations (RTU is half-duplex)
        if self._modbus_lock:
            try:
                async with self._modbus_lock:
                    try:
                        if use_function_16:
                            # Use function code 16 (0x10) - Write Multiple Holding Registers for registers >= 60
                            # This matches minimalmodbus library behavior
                            wr = await self.client.write_registers(address=addr, values=[value], device_id=self.inv.adapter.unit_id)
                        else:
                            # Use function code 6 (0x06) - Write Single Holding Register for registers < 60
                            wr = await self.client.write_register(address=addr, value=value, device_id=self.inv.adapter.unit_id)
                        
                        if hasattr(wr, "isError") and wr.isError():  # type: ignore
                            log.error(f"Modbus write failed: addr=0x{addr:04X}, value={value}, error={wr}")
                            raise RuntimeError(f"Modbus write error at 0x{addr:04X}: {wr}")
                        log.debug(f"✓ Modbus write successful: addr=0x{addr:04X}, value={value}")
                    except Exception as e:
                        log.error(f"Modbus write exception: addr=0x{addr:04X}, value={value}, error={e}", exc_info=True)
                        raise
            except (RuntimeError, ValueError, AttributeError, OSError) as e:
                # If lock is bound to different event loop (ours or pymodbus's), recreate client and retry
                error_str = str(e)
                if "bound to a different event loop" in error_str or "different event loop" in error_str.lower() or "Bad file descriptor" in error_str:
                    log.warning(f"Event loop or file descriptor issue detected: {error_str}, recreating client and retrying write")
                    # Force close old client first - handle errors gracefully
                    old_client = self.client
                    if old_client:
                        try:
                            # Check if client is still valid before trying to close
                            if hasattr(old_client, 'connected'):
                                try:
                                    # Try to check connection status - this might fail if fd is bad
                                    _ = old_client.connected
                                    if old_client.connected:
                                        if hasattr(old_client, 'close') and callable(old_client.close):
                                            import inspect
                                            if inspect.iscoroutinefunction(old_client.close):
                                                await old_client.close()
                                            else:
                                                old_client.close()
                                except (OSError, AttributeError, RuntimeError):
                                    # File descriptor is already invalid, just clear the reference
                                    log.debug("Client file descriptor already invalid, skipping close")
                        except Exception as close_err:
                            log.debug(f"Error closing old client (expected if fd is bad): {close_err}")
                        # Clear reference immediately to prevent reuse
                        self.client = None
                        # Wait longer for port to be fully released by OS
                        await asyncio.sleep(1.0)  # Increased wait time for port release
                    # Force recreate client (this will also recreate pymodbus's internal lock)
                    self._client_migrated = False
                    # Additional wait to ensure port is fully released before recreating
                    await asyncio.sleep(0.5)
                    try:
                        # Recreate client directly instead of calling _ensure_client_in_current_loop
                        # to avoid double-closing and ensure proper timing
                        config = await self._get_client_config()
                        if self.transport == "tcp":
                            from pymodbus.client import AsyncModbusTcpClient
                            self.client = AsyncModbusTcpClient(
                                host=config['host'],
                                port=config['port'],
                                timeout=config.get('timeout', 2.0),
                            )
                        else:  # RTU
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
                        if not ok or not self.client.connected:
                            transport_name = "TCP" if self.transport == "tcp" else "RTU"
                            raise RuntimeError(f"Modbus {transport_name} connection failed")
                        # Update loop reference
                        try:
                            self._client_loop = asyncio.get_running_loop()
                        except RuntimeError:
                            self._client_loop = asyncio.get_event_loop()
                        self._client_migrated = True
                        # Recreate lock in current loop
                        await self._ensure_lock_in_current_loop()
                        # Retry the operation
                        async with self._modbus_lock:
                            if use_function_16:
                                wr = await self.client.write_registers(address=addr, values=[value], device_id=self.inv.adapter.unit_id)
                            else:
                                wr = await self.client.write_register(address=addr, value=value, device_id=self.inv.adapter.unit_id)
                            
                            if hasattr(wr, "isError") and wr.isError():  # type: ignore
                                log.error(f"Modbus write failed: addr=0x{addr:04X}, value={value}, error={wr}")
                                raise RuntimeError(f"Modbus write error at 0x{addr:04X}: {wr}")
                            log.debug(f"✓ Modbus write successful: addr=0x{addr:04X}, value={value}")
                    except Exception as retry_err:
                        log.error(f"Failed to recreate client and retry write: {retry_err}")
                        raise
                else:
                    raise
        else:
            # Fallback if lock not initialized
            try:
                if use_function_16:
                    # Use function code 16 (0x10) - Write Multiple Holding Registers for registers >= 60
                    # This matches minimalmodbus library behavior
                    wr = await self.client.write_registers(address=addr, values=[value], device_id=self.inv.adapter.unit_id)
                else:
                    # Use function code 6 (0x06) - Write Single Holding Register for registers < 60
                    wr = await self.client.write_register(address=addr, value=value, device_id=self.inv.adapter.unit_id)
                    
                if hasattr(wr, "isError") and wr.isError():  # type: ignore
                    log.error(f"Modbus write failed (no lock): addr=0x{addr:04X}, value={value}, error={wr}")
                    raise RuntimeError(f"Modbus write error at 0x{addr:04X}: {wr}")
                log.debug(f"✓ Modbus write successful (no lock): addr=0x{addr:04X}, value={value}")
            except Exception as e:
                log.error(f"Modbus write exception (no lock): addr=0x{addr:04X}, value={value}, error={e}", exc_info=True)
                raise

    async def _write_holding_u16_list(self, addr: int, values: List[int]) -> None:
        if not self.client:
            raise RuntimeError("client not connected")
        # Ensure client and lock are in current event loop
        await self._ensure_client_in_current_loop()
        await self._ensure_lock_in_current_loop()
        log.debug(f"Modbus write multiple: addr=0x{addr:04X} (dec={addr}), values={values}, count={len(values)}, unit_id={self.unit_id}")
        # Use lock to serialize Modbus operations (RTU is half-duplex)
        if self._modbus_lock:
            try:
                async with self._modbus_lock:
                    try:
                        wr = await self.client.write_registers(address=addr, values=values, device_id=self.unit_id)
                        if hasattr(wr, "isError") and wr.isError():  # type: ignore
                            log.error(f"Modbus write multiple failed: addr=0x{addr:04X}, values={values}, error={wr}")
                            raise RuntimeError(f"Modbus write error at 0x{addr:04X}: {wr}")
                        log.debug(f"✓ Modbus write multiple successful: addr=0x{addr:04X}, values={values}")
                    except Exception as e:
                        log.error(f"Modbus write multiple exception: addr=0x{addr:04X}, values={values}, error={e}", exc_info=True)
                        raise
            except (RuntimeError, ValueError, AttributeError, OSError) as e:
                # If lock is bound to different event loop (ours or pymodbus's), recreate client and retry
                error_str = str(e)
                if "bound to a different event loop" in error_str or "different event loop" in error_str.lower() or "Bad file descriptor" in error_str:
                    log.warning(f"Event loop or file descriptor issue detected: {error_str}, recreating client and retrying write multiple")
                    # Force close old client first - handle errors gracefully
                    old_client = self.client
                    if old_client:
                        try:
                            # Check if client is still valid before trying to close
                            if hasattr(old_client, 'connected'):
                                try:
                                    # Try to check connection status - this might fail if fd is bad
                                    _ = old_client.connected
                                    if old_client.connected:
                                        if hasattr(old_client, 'close') and callable(old_client.close):
                                            import inspect
                                            if inspect.iscoroutinefunction(old_client.close):
                                                await old_client.close()
                                            else:
                                                old_client.close()
                                except (OSError, AttributeError, RuntimeError):
                                    # File descriptor is already invalid, just clear the reference
                                    log.debug("Client file descriptor already invalid, skipping close")
                        except Exception as close_err:
                            log.debug(f"Error closing old client (expected if fd is bad): {close_err}")
                        # Clear reference immediately to prevent reuse
                        self.client = None
                        # Wait longer for port to be fully released by OS
                        await asyncio.sleep(1.0)  # Increased wait time for port release
                    # Force recreate client (this will also recreate pymodbus's internal lock)
                    self._client_migrated = False
                    # Additional wait to ensure port is fully released before recreating
                    await asyncio.sleep(0.5)
                    try:
                        # Recreate client directly instead of calling _ensure_client_in_current_loop
                        # to avoid double-closing and ensure proper timing
                        config = await self._get_client_config()
                        if self.transport == "tcp":
                            from pymodbus.client import AsyncModbusTcpClient
                            self.client = AsyncModbusTcpClient(
                                host=config['host'],
                                port=config['port'],
                                timeout=config.get('timeout', 2.0),
                            )
                        else:  # RTU
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
                        if not ok or not self.client.connected:
                            transport_name = "TCP" if self.transport == "tcp" else "RTU"
                            raise RuntimeError(f"Modbus {transport_name} connection failed")
                        # Update loop reference
                        try:
                            self._client_loop = asyncio.get_running_loop()
                        except RuntimeError:
                            self._client_loop = asyncio.get_event_loop()
                        self._client_migrated = True
                        # Recreate lock in current loop
                        await self._ensure_lock_in_current_loop()
                        # Retry the operation
                        async with self._modbus_lock:
                            wr = await self.client.write_registers(address=addr, values=values, device_id=self.unit_id)
                            if hasattr(wr, "isError") and wr.isError():  # type: ignore
                                log.error(f"Modbus write multiple failed: addr=0x{addr:04X}, values={values}, error={wr}")
                                raise RuntimeError(f"Modbus write error at 0x{addr:04X}: {wr}")
                            log.debug(f"✓ Modbus write multiple successful: addr=0x{addr:04X}, values={values}")
                    except Exception as retry_err:
                        log.error(f"Failed to recreate client and retry write multiple: {retry_err}")
                        raise
                else:
                    raise
        else:
            # Fallback if lock not initialized
            try:
                wr = await self.client.write_registers(address=addr, values=values, device_id=self.unit_id)
                if hasattr(wr, "isError") and wr.isError():  # type: ignore
                    log.error(f"Modbus write multiple failed (no lock): addr=0x{addr:04X}, values={values}, error={wr}")
                    raise RuntimeError(f"Modbus write error at 0x{addr:04X}: {wr}")
                log.debug(f"✓ Modbus write multiple successful (no lock): addr=0x{addr:04X}, values={values}")
            except Exception as e:
                log.error(f"Modbus write multiple exception (no lock): addr=0x{addr:04X}, values={values}, error={e}", exc_info=True)
                raise

    async def poll(self) -> Telemetry:
        """
        Read all registers from register map and normalize to Telemetry.
        Uses TelemetryMapper to convert device-specific field names to standardized names.
        """
        # Log connection state before poll
        # Log stack trace to see who's calling poll()
        import traceback
        stack = traceback.extract_stack()
        callers = []
        for i in range(min(5, len(stack) - 1)):
            frame = stack[-(i+2)] if len(stack) > i+1 else None
            if frame:
                filename = frame.filename.split('/')[-1] if '/' in frame.filename else frame.filename.split('\\')[-1]
                callers.append(f"{filename}:{frame.lineno}({frame.name})")
        caller_info = " <- ".join(callers) if callers else "unknown"
        
        client_state = "None"
        # Get connection identifier for logging
        if self.transport == "tcp":
            conn_id = f"{self.inv.adapter.host}:{getattr(self.inv.adapter, 'port', 502)}"
        else:
            conn_id = getattr(self.inv.adapter, 'serial_port', 'unknown')
        if hasattr(self, 'client') and self.client is not None:
            if hasattr(self.client, 'connected'):
                client_state = f"connected={self.client.connected}"
            else:
                client_state = "exists (no connected attr)"
        log.info(f"POWDRIVE POLL: Starting poll for {self.inv.id} ({self.transport.upper()}={conn_id}, regs_loaded={bool(self.regs)}, client={client_state}) - called from: {caller_info}")
        
        # Ensure client is connected before polling (lazy connection)
        # Note: We don't check port existence here because:
        # 1. If client is already connected, the port obviously exists
        # 2. Port existence checks can be unreliable (timing issues, Linux serial port behavior)
        # 3. The connection attempt itself will handle port errors gracefully
        try:
            # FIRST: Check if client is already connected - if so, skip connection logic
            if self.client and hasattr(self.client, 'connected') and self.client.connected:
                # Client is connected - just ensure lock is in current loop and proceed
                log.debug(f"POWDRIVE POLL: Client already connected for {self.inv.id} on {conn_id}, ensuring lock in current loop...")
                await self._ensure_lock_in_current_loop()
                log.debug(f"POWDRIVE POLL: Client confirmed connected for {self.inv.id} on {conn_id}, proceeding with register reads")
            else:
                # Client not connected - ensure client and lock are in current event loop
                log.info(f"POWDRIVE POLL: Client not connected for {self.inv.id} on {conn_id}, ensuring client in current loop...")
                try:
                    # Use _ensure_client_in_current_loop which has proper locking
                    await self._ensure_client_in_current_loop()
                    await self._ensure_lock_in_current_loop()
                    # Verify connection after ensuring client
                    if not self.client or not self.client.connected:
                        log.warning(f"POWDRIVE POLL: Client still not connected after _ensure_client_in_current_loop for {self.inv.id} on {conn_id}")
                        raise RuntimeError("Client not connected after _ensure_client_in_current_loop")
                    log.info(f"POWDRIVE POLL: Successfully ensured client connection for {self.inv.id} on {conn_id}, proceeding with register reads")
                except Exception as connect_err:
                    # Check if it's a "port not found" error (common during device changes, RTU only)
                    error_str = str(connect_err).lower()
                    if self.transport == "rtu":
                        if "no such file" in error_str or "no such device" in error_str or "does not exist" in error_str:
                            log.warning(f"POWDRIVE POLL: Port {conn_id} does not exist for {self.inv.id}: {connect_err}")
                        elif "could not exclusively lock" in error_str or "resource temporarily unavailable" in error_str:
                            log.warning(f"POWDRIVE POLL: Port {conn_id} is locked (likely in use) for {self.inv.id}: {connect_err}")
                        else:
                            log.warning(f"POWDRIVE POLL: Failed to ensure client connection for {self.inv.id} on {conn_id}: {connect_err}")
                    else:  # TCP
                        log.warning(f"POWDRIVE POLL: Failed to ensure TCP client connection for {self.inv.id} on {conn_id}: {connect_err}")
                    raise RuntimeError(f"Powdrive adapter not connected: {connect_err}") from connect_err
        except RuntimeError:
            # Re-raise RuntimeErrors (connection errors)
            raise
        except Exception as e:
            log.error(f"POWDRIVE POLL: Connection check failed for {self.inv.id} on {conn_id} during poll: {e}")
            raise RuntimeError(f"Powdrive adapter not connected: {e}") from e
        
        # Read all registers from register map
        device_data: Dict[str, Any] = {}
        if self.regs:
            try:
                # Read all registers from the register map
                device_data = await self.read_all_registers()
                log.debug(f"Read {len(device_data)} registers from device")
            except Exception as e:
                log.warning(f"Failed to read all registers, falling back to individual reads: {e}")
                # Fallback to individual reads for critical registers
                try:
                    device_data["grid_power_w"] = int(await self.read_by_ident("grid_power_w"))
                    device_data["load_power_w"] = int(await self.read_by_ident("load_power_w"))
                    device_data["pv1_power_w"] = int(await self.read_by_ident("pv1_power_w"))
                    device_data["pv2_power_w"] = int(await self.read_by_ident("pv2_power_w"))
                    device_data["battery_voltage_v"] = float(await self.read_by_ident("battery_voltage_v"))
                    device_data["battery_current_a"] = float(await self.read_by_ident("battery_current_a"))
                    device_data["battery_power_w"] = int(await self.read_by_ident("battery_power_w"))
                    device_data["battery_soc_pct"] = float(await self.read_by_ident("battery_soc_pct"))
                    device_data["inverter_temp_c"] = float(await self.read_by_ident("inverter_temp_c"))
                except Exception as e2:
                    log.error(f"Fallback register reads also failed: {e2}")
                    raise
        else:
            # Fallback to direct register reads if register map not loaded
            try:
                device_data["grid_power_w"] = _s16((await self._read_u16(625, 1))[0])
                device_data["load_power_w"] = _s16((await self._read_u16(653, 1))[0])
                device_data["pv1_power_w"] = _s16((await self._read_u16(672, 1))[0])
                device_data["pv2_power_w"] = _s16((await self._read_u16(673, 1))[0])
                device_data["battery_voltage_v"] = (await self._read_u16(587, 1))[0] * 0.01
                device_data["battery_current_a"] = _s16((await self._read_u16(591, 1))[0]) * 0.01 * -1
                device_data["battery_power_w"] = _s16((await self._read_u16(590, 1))[0])
                device_data["battery_soc_pct"] = (await self._read_u16(588, 1))[0]
                device_data["inverter_temp_c"] = (await self._read_u16(540, 1))[0] * 0.1
            except Exception as e:
                log.error("Powdrive poll failed: %s", e)
                raise
        
        # Map device-specific data to standardized field names
        if hasattr(self, 'mapper') and self.mapper:
            standardized_data = self.mapper.map_to_standard(device_data)
        else:
            # No mapper available, use device data as-is
            standardized_data = device_data.copy()
            standardized_data["extra"] = device_data.copy()
        
        # Extract key values for Telemetry object (use standardized names)
        pv1_w = int(standardized_data.get("pv1_power_w", 0))
        pv2_w = int(standardized_data.get("pv2_power_w", 0))
        pv_w = pv1_w + pv2_w
        grid_w = int(standardized_data.get("grid_power_w", 0))
        load_w = int(standardized_data.get("load_power_w", 0))
        batt_v = float(standardized_data.get("batt_voltage_v") or standardized_data.get("battery_voltage_v", 0))
        batt_i = float(standardized_data.get("batt_current_a") or standardized_data.get("battery_current_a", 0))
        batt_p = int(standardized_data.get("batt_power_w") or standardized_data.get("battery_power_w", 0))
        batt_soc = float(standardized_data.get("batt_soc_pct") or standardized_data.get("battery_soc_pct", 0))
        inv_temp = float(standardized_data.get("inverter_temp_c", 0))

        # Normalize battery power to standard convention BEFORE storing
        # Positive power = Charging, Negative power = Discharging
        # Powdrive's register has inverted convention, so we invert it
        normalized_batt_p = self.normalize_battery_power(batt_p, invert=True)
        
        # Use standardized data as extra, but ensure all values are properly set
        extra = standardized_data.get("extra", {})
        extra.update(standardized_data)  # Ensure all standardized fields are in extra
        
        # Add computed values
        extra["pv_power_w"] = pv_w
        extra["batt_power_w"] = int(normalized_batt_p) if normalized_batt_p is not None else batt_p
        extra["batt_voltage_v"] = batt_v
        extra["batt_current_a"] = batt_i
        extra["batt_soc_pct"] = batt_soc
        extra["inverter_temp_c"] = inv_temp
        
        # Backward compatibility aliases
        extra["pv_power"] = pv_w
        extra["battery_voltage_v"] = batt_v
        extra["battery_current_a"] = batt_i
        extra["battery_power_w"] = int(normalized_batt_p) if normalized_batt_p is not None else batt_p
        extra["battery_soc_pct"] = batt_soc
        extra["battery_voltage"] = batt_v
        extra["battery_current"] = batt_i
        extra["battery_power"] = int(normalized_batt_p) if normalized_batt_p is not None else batt_p
        extra["battery_soc"] = batt_soc
        extra["inner_temperature"] = inv_temp

        # Extract energy values from standardized data
        day_gen_kwh = float(standardized_data.get("today_energy", 0))
        pv_today_kwh = float(standardized_data.get("today_energy", 0))  # Use today_energy as PV energy
        load_today_kwh = float(standardized_data.get("today_load_energy", 0))
        grid_import_today_kwh = float(standardized_data.get("today_import_energy", 0))
        grid_export_today_kwh = float(standardized_data.get("today_export_energy", 0))
        batt_charge_today_kwh = float(standardized_data.get("today_battery_charge_energy", 0))
        batt_discharge_today_kwh = float(standardized_data.get("today_battery_discharge_energy", 0))
        
        # Get array_id from inverter config
        array_id = getattr(self.inv, 'array_id', None)
        
        tel = Telemetry(
            ts=now_configured_iso(),
            pv_power_w=int(pv_w),
            grid_power_w=int(grid_w),
            load_power_w=int(load_w),
            batt_voltage_v=round(batt_v, 2),
            batt_current_a=round(batt_i, 2),
            batt_power_w=int(normalized_batt_p) if normalized_batt_p is not None else None,
            batt_soc_pct=float(batt_soc),
            inverter_temp_c=round(inv_temp, 1),
            battery_daily_charge_energy=batt_charge_today_kwh,
            battery_daily_discharge_energy=batt_discharge_today_kwh,
            daily_energy_to_eps=load_today_kwh,
            array_id=array_id,
            extra=extra,
        )

        # Read working mode (register 500) - always try to read, even if regs not loaded
        try:
            if self.regs:
                working_mode_raw = int(await self.read_by_ident("working_mode_raw"))
            else:
                # Fallback: read directly from register 500
                working_mode_raw = (await self._read_u16(500, 1))[0]
            
            mode_map = {
                0: "Standby",
                1: "Self-check",
                2: "Normal",
                3: "Alarm",
                4: "Fault"
            }
            inverter_mode = mode_map.get(working_mode_raw, f"Unknown({working_mode_raw})")
            tel.extra["inverter_mode"] = inverter_mode
            # Also set hybrid_work_mode for backward compatibility with InverterManager
            tel.extra["hybrid_work_mode"] = inverter_mode
            # Set inverter_mode on Telemetry object if possible (for compatibility)
            if hasattr(tel, 'inverter_mode'):
                tel.inverter_mode = inverter_mode
            log.debug(f"Powdrive working mode decoded: {working_mode_raw} -> {inverter_mode}")
        except Exception as e:
            log.warning(f"Failed to read/decode working mode: {e}", exc_info=True)
            tel.extra["inverter_mode"] = "Unknown"
            tel.extra["hybrid_work_mode"] = "Unknown"

        self.last_tel = tel
        
        # Log what we've read so far for debugging
        log.debug(f"Powdrive poll - Basic telemetry: PV={pv_w}W, Load={load_w}W, Grid={grid_w}W, "
                  f"Batt={batt_p}W (normalized={normalized_batt_p}W), SOC={batt_soc}%, "
                  f"Temp={inv_temp}°C, Today={day_gen_kwh}kWh")

        # Compute per-phase aggregates when available via JSON map
        try:
            if self.regs:
                i1 = float(await self.read_by_ident("inverter_l1_current_a"))
                i2 = float(await self.read_by_ident("inverter_l2_current_a"))
                i3 = float(await self.read_by_ident("inverter_l3_current_a"))
                g1 = float(await self.read_by_ident("grid_l1_current_a"))
                g2 = float(await self.read_by_ident("grid_l2_current_a"))
                g3 = float(await self.read_by_ident("grid_l3_current_a"))
                total_inv_a = round(i1 + i2 + i3, 2)
                total_grid_a = round(g1 + g2 + g3, 2)
                tel.extra["inverter_current_a"] = total_inv_a
                tel.extra["grid_current_a"] = total_grid_a
                
                # Read Load per-phase power, voltage, and compute current
                try:
                    load_l1_p = int(await self.read_by_ident("load_l1_power_w"))
                    load_l2_p = int(await self.read_by_ident("load_l2_power_w"))
                    load_l3_p = int(await self.read_by_ident("load_l3_power_w"))
                    load_l1_v = float(await self.read_by_ident("load_l1_voltage_v"))
                    load_l2_v = float(await self.read_by_ident("load_l2_voltage_v"))
                    load_l3_v = float(await self.read_by_ident("load_l3_voltage_v"))
                    load_freq = float(await self.read_by_ident("load_frequency_hz"))
                    tel.extra["load_l1_power_w"] = load_l1_p
                    tel.extra["load_l2_power_w"] = load_l2_p
                    tel.extra["load_l3_power_w"] = load_l3_p
                    tel.extra["load_l1_voltage_v"] = load_l1_v
                    tel.extra["load_l2_voltage_v"] = load_l2_v
                    tel.extra["load_l3_voltage_v"] = load_l3_v
                    tel.extra["load_frequency_hz"] = load_freq
                    # Compute load current from power and voltage (I = P / V)
                    if load_l1_v > 0:
                        tel.extra["load_l1_current_a"] = round(abs(load_l1_p) / load_l1_v, 2)
                    if load_l2_v > 0:
                        tel.extra["load_l2_current_a"] = round(abs(load_l2_p) / load_l2_v, 2)
                    if load_l3_v > 0:
                        tel.extra["load_l3_current_a"] = round(abs(load_l3_p) / load_l3_v, 2)
                except Exception as e:
                    log.debug(f"Failed to read load per-phase data: {e}")
                    pass
                
                # Read Grid per-phase power, voltage, and current
                try:
                    grid_l1_p = int(await self.read_by_ident("grid_l1_power_w"))
                    grid_l2_p = int(await self.read_by_ident("grid_l2_power_w"))
                    grid_l3_p = int(await self.read_by_ident("grid_l3_power_w"))
                    grid_l1_v = float(await self.read_by_ident("grid_l1_voltage_v"))
                    grid_l2_v = float(await self.read_by_ident("grid_l2_voltage_v"))
                    grid_l3_v = float(await self.read_by_ident("grid_l3_voltage_v"))
                    grid_freq = float(await self.read_by_ident("grid_frequency_hz"))
                    tel.extra["grid_l1_power_w"] = grid_l1_p
                    tel.extra["grid_l2_power_w"] = grid_l2_p
                    tel.extra["grid_l3_power_w"] = grid_l3_p
                    tel.extra["grid_l1_voltage_v"] = grid_l1_v
                    tel.extra["grid_l2_voltage_v"] = grid_l2_v
                    tel.extra["grid_l3_voltage_v"] = grid_l3_v
                    tel.extra["grid_frequency_hz"] = grid_freq
                    # Grid current already read above
                except Exception as e:
                    log.debug(f"Failed to read grid per-phase data: {e}")
                    pass
                
                # Read battery temperature
                try:
                    batt_temp = float(await self.read_by_ident("battery_temp_c"))
                    tel.extra["battery_temp_c"] = batt_temp
                    log.debug(f"Read battery temperature: {batt_temp}°C")
                except Exception as e:
                    log.warning(f"Failed to read battery temperature: {e}", exc_info=True)
                    pass
                
                # Read device information (registers 0-8)
                try:
                    device_type = int(await self.read_by_ident("inverter_type"))
                    device_sn = await self.read_by_ident("device_serial_number")
                    # rated_power_w is U32 (2 words) - read_by_ident should handle it correctly
                    rated_power_raw = await self.read_by_ident("rated_power_w")
                    # Handle U32 - read_by_ident should return the decoded value with scale applied
                    if isinstance(rated_power_raw, (int, float)):
                        rated_power = float(rated_power_raw)
                    else:
                        # Fallback: read directly as U32
                        regs = await self._read_u16(20, 2)
                        rated_power = (regs[0] * 65536 + regs[1]) * 0.1
                    tel.extra["device_model"] = f"Type-{device_type:04X}"
                    tel.extra["device_serial_number"] = str(device_sn) if device_sn else "N/A"
                    tel.extra["rated_power_w"] = rated_power
                    tel.extra["inverter_type"] = device_type  # Store raw value for phase detection
                    
                    # Detect phase type from inverter_type register
                    # Powdrive enum: {"2": "Inverter", "3": "Hybrid Inverter", "4": "Micro Inverter", "5": "3 Phase Hybrid Inverter"}
                    from solarhub.inverter_metadata import InverterMetadata
                    detected_phase_type = InverterMetadata.detect_phase_type_from_register(device_type)
                    if detected_phase_type:
                        tel.extra["phase_type"] = detected_phase_type
                        log.debug(f"Detected phase type from inverter_type register: {detected_phase_type} (device_type={device_type})")
                    
                    log.debug(f"Read device info: type={device_type:04X}, serial={device_sn}, rated_power={rated_power}W, phase_type={detected_phase_type}")
                except Exception as e:
                    log.warning(f"Failed to read device info: {e}", exc_info=True)
                    pass
                
                # Read phase-to-phase voltages
                try:
                    grid_v_ab = float(await self.read_by_ident("grid_line_voltage_ab_v"))
                    grid_v_bc = float(await self.read_by_ident("grid_line_voltage_bc_v"))
                    grid_v_ca = float(await self.read_by_ident("grid_line_voltage_ca_v"))
                    tel.extra["grid_line_voltage_ab_v"] = grid_v_ab
                    tel.extra["grid_line_voltage_bc_v"] = grid_v_bc
                    tel.extra["grid_line_voltage_ca_v"] = grid_v_ca
                except Exception:
                    pass
                
                # Decode grid status (register 552) for off-grid detection
                # Bit 2 = Grid relay (1=connected, 0=disconnected)
                try:
                    grid_status = int(await self.read_by_ident("grid_status_raw"))
                    grid_relay_connected = bool(grid_status & (1 << 2))
                    off_grid_mode = not grid_relay_connected
                    tel.extra["off_grid_mode"] = off_grid_mode
                    tel.extra["grid_relay_connected"] = grid_relay_connected
                    tel.extra["grid_status_raw"] = grid_status
                except Exception:
                    pass
                
                # Read power limit settings (stored as current in Amps, convert to Watts)
                # These are needed for the Settings page to display current values
                try:
                    # Get current battery voltage for conversion
                    batt_voltage = tel.batt_voltage_v if tel.batt_voltage_v else 52.0  # Default to 52V if not available
                    
                    # Read maximum charge current (register 108) and convert to power
                    max_charge_current_a = int(await self.read_by_ident("battery_max_charge_current_a"))
                    max_charge_power_w = int(max_charge_current_a * batt_voltage)
                    tel.extra["maximum_charger_power"] = max_charge_power_w
                    tel.extra["battery_max_charge_current_a"] = max_charge_current_a
                    log.debug(f"Read max charge: {max_charge_current_a}A = {max_charge_power_w}W (at {batt_voltage}V)")
                    
                    # Read maximum discharge current (register 109) and convert to power
                    max_discharge_current_a = int(await self.read_by_ident("battery_max_discharge_current_a"))
                    max_discharge_power_w = int(max_discharge_current_a * batt_voltage)
                    tel.extra["maximum_discharger_power"] = max_discharge_power_w
                    tel.extra["battery_max_discharge_current_a"] = max_discharge_current_a
                    log.debug(f"Read max discharge: {max_discharge_current_a}A = {max_discharge_power_w}W (at {batt_voltage}V)")
                    
                    # Read grid charge battery current (if register exists) and convert to power
                    try:
                        grid_charge_current_a = int(await self.read_by_ident("grid_charge_battery_current_a"))
                        grid_charge_power_w = int(grid_charge_current_a * batt_voltage)
                        tel.extra["maximum_grid_charger_power"] = grid_charge_power_w
                        tel.extra["grid_charge_battery_current_a"] = grid_charge_current_a
                        log.debug(f"Read grid charge: {grid_charge_current_a}A = {grid_charge_power_w}W (at {batt_voltage}V)")
                    except Exception as e:
                        log.debug(f"grid_charge_battery_current_a register not found or not readable: {e}")
                        # If register doesn't exist, set to None
                        tel.extra["maximum_grid_charger_power"] = None
                    
                    # Read zero export power (register 104) - this is the feed-in limit
                    try:
                        zero_export_power_w = int(await self.read_by_ident("zero_export_power_w"))
                        tel.extra["maximum_feed_in_grid_power"] = zero_export_power_w
                        tel.extra["zero_export_power_w"] = zero_export_power_w
                        log.debug(f"Read zero export (feed-in limit): {zero_export_power_w}W")
                    except Exception as e:
                        log.debug(f"zero_export_power_w register not found or not readable: {e}")
                        # If register doesn't exist, set to None
                        tel.extra["maximum_feed_in_grid_power"] = None
                except Exception as e:
                    log.warning(f"Failed to read power limit settings: {e}", exc_info=True)
                    pass
                
                # Extract error codes from fault words (555-558)
                try:
                    fault_word_0 = int(await self.read_by_ident("fault_word_0"))
                    fault_word_1 = int(await self.read_by_ident("fault_word_1"))
                    fault_word_2 = int(await self.read_by_ident("fault_word_2"))
                    fault_word_3 = int(await self.read_by_ident("fault_word_3"))
                    tel.extra["fault_word_0"] = fault_word_0
                    tel.extra["fault_word_1"] = fault_word_1
                    tel.extra["fault_word_2"] = fault_word_2
                    tel.extra["fault_word_3"] = fault_word_3
                    
                    # Extract error codes if any fault bits are set
                    # Fault codes are typically in specific bits, but we'll store the raw values
                    # and let higher layers decode them based on fault code table
                    if fault_word_0 or fault_word_1 or fault_word_2 or fault_word_3:
                        # Combine fault words into a single error code identifier
                        # For now, we'll use the first non-zero fault word as the primary error
                        error_code = None
                        if fault_word_0:
                            error_code = f"F0:{fault_word_0:04X}"
                        elif fault_word_1:
                            error_code = f"F1:{fault_word_1:04X}"
                        elif fault_word_2:
                            error_code = f"F2:{fault_word_2:04X}"
                        elif fault_word_3:
                            error_code = f"F3:{fault_word_3:04X}"
                        tel.extra["error_code"] = error_code
                except Exception:
                    pass
        except Exception:
            pass
        return tel
    
    def get_tou_window_capability(self) -> Dict[str, Any]:
        """
        Powdrive supports 6 bidirectional TOU windows (registers 148-177).
        - Time points (148-153): Start time of window N, also end time of window N-1
        - Power (154-159): Charge/discharge power for each window
        - Target voltage (160-165): Used if register 111=0 (voltage mode)
        - Target SOC (166-171): Used if register 111=1 (capacity mode)
        - Charge enable (172-177): Bit manipulation for grid/gen charging and Spanish modes
        Direction is auto-determined by comparing target SOC/voltage to current value.
        """
        return {
            "max_windows": 6,  # Powdrive supports 6 windows (not 5)
            "bidirectional": True,
            "separate_charge_discharge": False,
            "max_charge_windows": 6,
            "max_discharge_windows": 6
        }

    async def write_by_ident(self, ident: str, value: Any) -> None:
        """
        Override write_by_ident to use decimal HHMM format for time registers in Powdrive.
        This ensures time is encoded as HHMM decimal (2359 = 23:59) instead of byte-packed.
        """
        # Find the register
        r = self._find_reg_by_id_or_name(ident)
        
        # If it's a time register with hhmm encoder, use decimal format
        if (r.get("encoder") or "").lower() == "hhmm":
            # Parse time and encode as decimal HHMM
            parts = str(value).split(":", 1)
            if len(parts) == 2:
                h, m = [int(x) for x in parts]
                if 0 <= h <= 23 and 0 <= m <= 59:
                    # Powdrive format: HHMM as decimal (2359 = 23:59)
                    encoded_value = h * 100 + m
                    log.debug(f"Powdrive time encoding override: '{value}' -> {encoded_value} (decimal HHMM)")
                    # Write directly using address
                    addr = int(r["addr"]) + getattr(self, "addr_offset", 0)
                    await self._write_holding_u16(addr, encoded_value)
                    return
        
        # For all other registers, use parent class method
        await super().write_by_ident(ident, value)

    async def handle_command(self, cmd: Dict[str, Any]):
        """
        Write support:
          - {"action":"write", "id": "register_name", "value": X}  # name-based write
          - {"action":"write", "addr": 172, "value": X}  # direct address write
          - {"action":"set_tou_window{1-6}", ...}  # TOU window setting
          - The smart scheduler may also emit generic actions used by other adapters
            (e.g., senergy). For Powdrive these are either not applicable or are
            managed via TOU windows. We accept them as no-ops to avoid warnings.
        """
        action = str(cmd.get("action", "")).lower()
        
        # --- Map generic scheduler actions to Powdrive registers when possible ---
        if action == "set_work_mode":
            # Map to TOU enable register: bit0 enable, bits1-7 days, bit8 Spanish mode
            # Requirement: even for self-use, TOU must be enabled.
            desired = 0
            desired |= (1 << 0)  # Enable TOU
            # enable all weekdays by default
            for b in range(1, 8):
                desired |= (1 << b)
            try:
                await self.write_by_ident("tou_selling", desired)
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "reason": str(e)}

        if action == "set_grid_charge":
            # Register 130: ac_charge_battery, enum {0: Enabled, 1: Disabled}
            enable = bool(cmd.get("enable", False))
            raw = 0 if enable else 1
            try:
                await self.write_by_ident("ac_charge_battery", raw)
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "reason": str(e)}

        # Helper: compute amps from requested watts and current battery voltage
        async def _amps_from_power_w(power_w: int) -> int:
            try:
                # Prefer live voltage from adapter register map
                v = None
                try:
                    v = await self.read_by_ident("battery_voltage_v")
                except Exception:
                    pass
                if v is None and getattr(self, "last_tel", None) and getattr(self.last_tel, "batt_voltage_v", None) is not None:
                    v = float(self.last_tel.batt_voltage_v)
                if v is None:
                    v = 52.0  # safe default
                v = max(1.0, float(v))
                amps = int(round(float(power_w) / v))
                # Clamp to device-supported range 0..185 A
                amps = max(0, min(185, amps))
                return amps
            except Exception:
                # Fallback conservative
                return max(0, min(185, int(round((power_w or 0) / 52.0))))

        if action == "set_max_grid_charge_power_w":
            val_w = int(cmd.get("value", 0))
            amps = await _amps_from_power_w(val_w)
            try:
                await self.write_by_ident("grid_charge_battery_current_a", amps)
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "reason": str(e)}

        if action == "set_max_charge_power_w":
            val_w = int(cmd.get("value", 0))
            amps = await _amps_from_power_w(val_w)
            try:
                await self.write_by_ident("battery_max_charge_current_a", amps)
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "reason": str(e)}

        if action == "set_max_discharge_power_w":
            val_w = int(cmd.get("value", 0))
            amps = await _amps_from_power_w(val_w)
            try:
                await self.write_by_ident("battery_max_discharge_current_a", amps)
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "reason": str(e)}

        # Handle set_discharge_limits - sets the battery shutdown capacity percentage
        if action == "set_discharge_limits":
            end_soc = cmd.get("end_soc") or cmd.get("value")
            if end_soc is None:
                return {"ok": True}  # No-op if no value provided
            try:
                # battery_shutdown_capacity_pct (register 115) sets minimum SOC before shutdown
                await self.write_by_ident("battery_shutdown_capacity_pct", int(end_soc))
                log.info(f"Set Powdrive discharge limit (shutdown capacity) to {end_soc}%")
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "reason": str(e)}

        # Accept remaining generic actions as no-ops to avoid noisy warnings
        if action in ("set_grid_charge_end_soc", "set_charge_end_soc", "set_discharge_end_soc"):
            return {"ok": True}

        if action == "write":
            ident = cmd.get("id")
            if ident is not None and self.regs:
                try:
                    await self.write_by_ident(str(ident), cmd.get("value"))
                    if self.last_tel and self.last_tel.extra is not None:
                        self.last_tel.extra[self._sanitize_key(str(ident))] = cmd.get("value")
                    return {"ok": True}
                except Exception as e:
                    return {"ok": False, "reason": str(e)}
            # Fallback to direct address write
            addr = cmd.get("addr")
            if addr is None:
                try:
                    addr = int(str(ident), 0)
                except Exception:
                    return {"ok": False, "reason": "addr (or numeric id) required"}
            try:
                await self._write_holding_u16(int(addr), int(cmd.get("value")))
                if self.last_tel and self.last_tel.extra is not None:
                    self.last_tel.extra[f"reg_{int(addr):04x}"] = int(cmd.get("value"))
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "reason": str(e)}

        # Handle batch writes
        if action == "write_many":
            writes = cmd.get("writes", [])
            if not writes:
                return {"ok": False, "reason": "missing 'writes' array"}

            results = []
            for write_cmd in writes:
                ident = write_cmd.get("id") or write_cmd.get("name")
                value = write_cmd.get("value")

                if not ident:
                    results.append({"ok": False, "reason": "missing id/name in write"})
                    continue

                try:
                    await self.write_by_ident(str(ident), value)
                    if self.last_tel and self.last_tel.extra is not None:
                        self.last_tel.extra[self._sanitize_key(str(ident))] = value
                    results.append({"ok": True, "id": str(ident)})
                except Exception as e:
                    results.append({"ok": False, "id": str(ident), "reason": str(e)})

            # Return success if all writes succeeded
            all_ok = all(r.get("ok", False) for r in results)
            return {"ok": all_ok, "results": results}

        # Handle TOU window setting (bidirectional windows)
        # Powdrive TOU structure: 148-153=times (start of window N, end of window N-1), 
        # 154-159=powers, 160-165=voltages (if reg111=0), 166-171=capacities (if reg111=1), 172-177=charge enable bits
        if action.startswith("set_tou_window"):
            import re
            m = re.match(r"set_tou_window([1-6])$", action)
            if not m:
                return {"ok": False, "reason": "bad window index (1-6)"}
            idx = int(m.group(1))
            
            # Get current SOC and battery mode source (register 111)
            current_soc = None
            battery_mode_source = 1  # Default to capacity mode (1)
            if self.last_tel and self.last_tel.batt_soc_pct is not None:
                current_soc = float(self.last_tel.batt_soc_pct)
            
            # Read battery_mode_source (register 111) to determine voltage vs capacity mode
            try:
                if self.regs:
                    battery_mode_source = int(await self.read_by_ident("battery_mode_source"))
            except Exception:
                pass  # Default to capacity mode if read fails
            
            # Normalize window to generalized format
            window = self.normalize_tou_window(cmd, current_soc_pct=current_soc)
            
            start_time = window.get("start_time", "00:00")
            end_time = window.get("end_time", "00:00")
            power_w = abs(window.get("power_w", 0))  # Always positive (absolute value)
            target_soc_pct = window.get("target_soc_pct", 100)
            target_voltage_v = window.get("target_voltage_v")  # Optional voltage target
            window_type = window.get("type", "auto")
            
            log.info(f"Setting Powdrive TOU window {idx}: {start_time}-{end_time}, "
                    f"power: {power_w}W, target SOC: {target_soc_pct}%, mode_source={battery_mode_source}, type: {window_type}")
            
            try:
                import asyncio
                
                # Step 0: Enable TOU and set days if needed (register 146)
                # Bit 0: Enable TOU (0=disable, 1=enable)
                # Bits 1-7: Monday-Sunday (0=disable, 1=enable)
                # Bit 8: Spanish mode (optional)
                log.info(f"[TOU Window {idx}] Step 0/5: Checking and setting TOU enable register (tou_selling)")
                try:
                    # Add extra delay before TOU enable register operation to avoid conflicts with polling
                    await asyncio.sleep(0.3)
                    
                    # Read current value with retry logic
                    current_tou_enable = None
                    for retry in range(3):
                        try:
                            current_tou_enable = await self.read_by_ident("tou_selling")
                            log.debug(f"[TOU Window {idx}] Current TOU enable register value: 0x{current_tou_enable:04X} ({current_tou_enable})")
                            break
                        except Exception as read_err:
                            if retry < 2:
                                log.warning(f"[TOU Window {idx}] Step 0/5: Read attempt {retry+1}/3 failed: {read_err}, retrying...")
                                await asyncio.sleep(0.2)
                            else:
                                log.warning(f"[TOU Window {idx}] Step 0/5: Failed to read TOU enable register after 3 attempts, assuming 0")
                                current_tou_enable = 0
                    
                    # Build desired value: enable TOU (bit 0) and all days (bits 1-7)
                    desired_tou_enable = 0
                    desired_tou_enable |= (1 << 0)  # Bit 0: Enable TOU
                    desired_tou_enable |= (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 6) | (1 << 7)  # Bits 1-7: All days enabled
                    
                    # Check if Spanish mode should be enabled (optional, from command)
                    if cmd.get("enable_spanish_mode", False):
                        desired_tou_enable |= (1 << 8)  # Bit 8: Spanish mode
                    
                    # Only write if current value is different
                    if current_tou_enable != desired_tou_enable:
                        log.info(f"[TOU Window {idx}] Step 0/5: Setting TOU enable register: 0x{current_tou_enable:04X} -> 0x{desired_tou_enable:04X}")
                        log.info(f"[TOU Window {idx}] Step 0/5: TOU enable bits - TOU={bool(desired_tou_enable & 1)}, "
                                f"Mon={bool(desired_tou_enable & 2)}, Tue={bool(desired_tou_enable & 4)}, "
                                f"Wed={bool(desired_tou_enable & 8)}, Thu={bool(desired_tou_enable & 16)}, "
                                f"Fri={bool(desired_tou_enable & 32)}, Sat={bool(desired_tou_enable & 64)}, "
                                f"Sun={bool(desired_tou_enable & 128)}, Spanish={bool(desired_tou_enable & 256)}")
                        
                        # Write with retry logic
                        write_success = False
                        for retry in range(3):
                            try:
                                await asyncio.sleep(0.2)  # Extra delay before each write attempt
                                await self.write_by_ident("tou_selling", desired_tou_enable)
                                log.info(f"[TOU Window {idx}] Step 0/5: ✓ Successfully set TOU enable register")
                                write_success = True
                                await asyncio.sleep(0.2)  # Delay after successful write
                                break
                            except Exception as write_err:
                                if retry < 2:
                                    log.warning(f"[TOU Window {idx}] Step 0/5: Write attempt {retry+1}/3 failed: {write_err}, retrying...")
                                    await asyncio.sleep(0.3)
                                else:
                                    log.error(f"[TOU Window {idx}] Step 0/5: ✗ Failed to write TOU enable register after 3 attempts: {write_err}")
                                    raise
                        
                        if not write_success:
                            raise RuntimeError("Failed to write TOU enable register after retries")
                    else:
                        log.info(f"[TOU Window {idx}] Step 0/5: TOU enable register already has correct value (0x{current_tou_enable:04X}) - skipping")
                except Exception as e:
                    log.warning(f"[TOU Window {idx}] Step 0/5: ⚠ Failed to read/write TOU enable register: {e} - continuing anyway", exc_info=True)
                    # Continue even if TOU enable fails - might already be set
                    await asyncio.sleep(0.2)  # Delay before continuing
                
                # Set start time (prog{idx}_time) - register 148-153
                # Note: In Powdrive, time point N is start of window N and end of window N-1
                log.info(f"[TOU Window {idx}] Step 1/5: Writing start time '{start_time}' to register prog{idx}_time")
                try:
                    await asyncio.sleep(0.2)  # Extra delay before write to avoid Modbus conflicts
                    await self.write_by_ident(f"prog{idx}_time", start_time)
                    log.info(f"[TOU Window {idx}] Step 1/5: ✓ Successfully wrote start time '{start_time}'")
                except Exception as e:
                    log.error(f"[TOU Window {idx}] Step 1/5: ✗ Failed to write start time '{start_time}': {e}", exc_info=True)
                    raise
                await asyncio.sleep(0.2)  # Increased delay between writes
                
                # If this is not the last window, set the end time for previous window
                # End time of window N is start time of window N+1
                # For window 1, end time is window 2 start time (handled when setting window 2)
                
                # Set power (prog{idx}_power_w) - register 154-159
                # Power is always positive, direction determined by target vs current SOC
                log.info(f"[TOU Window {idx}] Step 2/5: Writing power {power_w}W to register prog{idx}_power_w")
                try:
                    await asyncio.sleep(0.2)  # Extra delay before write to avoid Modbus conflicts
                    await self.write_by_ident(f"prog{idx}_power_w", int(power_w))
                    log.info(f"[TOU Window {idx}] Step 2/5: ✓ Successfully wrote power {power_w}W")
                except Exception as e:
                    log.error(f"[TOU Window {idx}] Step 2/5: ✗ Failed to write power {power_w}W: {e}", exc_info=True)
                    raise
                await asyncio.sleep(0.2)  # Increased delay between writes
                
                # Set target based on battery_mode_source (register 111)
                # If register 111 = 0 (voltage mode): use registers 160-165 (voltage)
                # If register 111 = 1 (capacity mode): use registers 166-171 (SOC)
                if battery_mode_source == 0:
                    # Voltage mode: set target voltage (registers 160-165)
                    if target_voltage_v is not None:
                        # Note: The register has scale 0.01, so we pass the voltage value directly
                        # The encoder in base.py will apply the scale automatically
                        log.info(f"[TOU Window {idx}] Step 3/5: Writing target voltage {target_voltage_v}V to register prog{idx}_voltage_v (scale=0.01)")
                        log.debug(f"[TOU Window {idx}] Step 3/5: Voltage value before encoding: {target_voltage_v}V (type: {type(target_voltage_v).__name__})")
                        try:
                            # Pass voltage directly - the encoder will handle scaling
                            await self.write_by_ident(f"prog{idx}_voltage_v", target_voltage_v)
                            log.info(f"[TOU Window {idx}] Step 3/5: ✓ Successfully wrote target voltage {target_voltage_v}V")
                        except Exception as e:
                            log.error(f"[TOU Window {idx}] Step 3/5: ✗ Failed to write target voltage {target_voltage_v}V: {e}", exc_info=True)
                            raise
                        await asyncio.sleep(0.2)  # Increased delay between writes
                    else:
                        # If no voltage provided, try to calculate from SOC (approximate)
                        # This is a fallback - ideally voltage should be provided
                        log.warning(f"[TOU Window {idx}] Step 3/5: Voltage mode but no target_voltage_v provided - skipping voltage write")
                else:
                    # Capacity mode: set target SOC (registers 166-171)
                    log.info(f"[TOU Window {idx}] Step 3/5: Writing target SOC {target_soc_pct}% to register prog{idx}_capacity_pct")
                    try:
                        await asyncio.sleep(0.2)  # Extra delay before write to avoid Modbus conflicts
                        await self.write_by_ident(f"prog{idx}_capacity_pct", int(target_soc_pct))
                        log.info(f"[TOU Window {idx}] Step 3/5: ✓ Successfully wrote target SOC {target_soc_pct}%")
                    except Exception as e:
                        log.error(f"[TOU Window {idx}] Step 3/5: ✗ Failed to write target SOC {target_soc_pct}%: {e}", exc_info=True)
                        raise
                    await asyncio.sleep(0.2)  # Increased delay between writes
                
                # Set charge enable (prog{idx}_charge_mode) - register 172-177
                # Bit manipulation: Bit0=grid charging, Bit1=gen charging, Bit2=Spanish GM, Bit3=Spanish BU, Bit4=Spanish CH
                charge_mode_value = 0
                
                # Determine if this is a charge or discharge window
                # If power is 0, this is a clear operation - disable all modes
                if power_w == 0:
                    is_charge_window = False
                    log.info(f"Window {idx} is being cleared (power=0) - disabling all modes")
                else:
                    is_charge_window = False
                    if window_type == "charge":
                        is_charge_window = True
                    elif window_type == "discharge":
                        is_charge_window = False
                    elif window_type == "auto" and current_soc is not None:
                        # Auto mode: compare target to current SOC
                        if battery_mode_source == 0:
                            # Voltage mode: assume charge if target > current (approximate)
                            # For voltage mode, we'd need current voltage which we don't have here
                            # Default to charge if target_soc_pct > current_soc
                            is_charge_window = (target_soc_pct > current_soc)
                        else:
                            # Capacity mode: compare target SOC to current SOC
                            is_charge_window = (target_soc_pct > current_soc)
                
                # Set bit 0 (grid charging enable) if charge window
                if is_charge_window:
                    charge_mode_value |= (1 << 0)  # Bit 0 = 1 (enable grid charging)
                    log.info(f"Window {idx} is charge window - enabling grid charging")
                else:
                    log.info(f"Window {idx} is discharge window or cleared - disabling grid charging")
                
                # Bit 1 (gen charging enable) - optional, can be set via command if needed
                # For now, we'll leave it at 0 (disabled) unless specified in command
                if cmd.get("enable_gen_charging", False):
                    charge_mode_value |= (1 << 1)  # Bit 1 = 1 (enable gen charging)
                
                # Spanish modes (Bits 2-4) - optional, can be set via command if needed
                if cmd.get("enable_spanish_gm", False):
                    charge_mode_value |= (1 << 2)  # Bit 2 = Spanish GM mode
                if cmd.get("enable_spanish_bu", False):
                    charge_mode_value |= (1 << 3)  # Bit 3 = Spanish BU mode
                if cmd.get("enable_spanish_ch", False):
                    charge_mode_value |= (1 << 4)  # Bit 4 = Spanish CH mode
                
                # Set charge enable (prog{idx}_charge_mode) - register 172-177
                log.info(f"[TOU Window {idx}] Step 4/5: Writing charge_mode 0x{charge_mode_value:04X} to register prog{idx}_charge_mode")
                log.info(f"[TOU Window {idx}] Step 4/5: Charge mode bits - grid={bool(charge_mode_value & 1)}, gen={bool(charge_mode_value & 2)}, GM={bool(charge_mode_value & 4)}, BU={bool(charge_mode_value & 8)}, CH={bool(charge_mode_value & 16)}")
                try:
                    await asyncio.sleep(0.2)  # Extra delay before write to avoid Modbus conflicts
                    await self.write_by_ident(f"prog{idx}_charge_mode", charge_mode_value)
                    log.info(f"[TOU Window {idx}] Step 4/5: ✓ Successfully wrote charge_mode 0x{charge_mode_value:04X}")
                except Exception as e:
                    log.error(f"[TOU Window {idx}] Step 4/5: ✗ Failed to write charge_mode 0x{charge_mode_value:04X}: {e}", exc_info=True)
                    raise
                await asyncio.sleep(0.2)  # Increased delay after final write
                
                log.info(f"[TOU Window {idx}] ✓ All 5 register writes completed successfully")
                return {"ok": True}
            except Exception as e:
                log.error(f"[TOU Window {idx}] ✗ Failed to set TOU window: {e}", exc_info=True)
                return {"ok": False, "reason": str(e)}

        return {"ok": False, "reason": "unsupported action"}
    
    async def check_connectivity(self) -> bool:
        """Check if Powdrive device is connected and responding by reading serial number register."""
        try:
            if not self.client or not self.client.connected:
                # Use _ensure_client_in_current_loop which has proper locking
                await self._ensure_client_in_current_loop()
                await self._ensure_lock_in_current_loop()
            
            # Try to read serial number register as connectivity check
            # This is a reliable way to verify the device is responding
            try:
                serial = await self.read_by_ident("device_serial_number")
                if serial and isinstance(serial, str):
                    serial = serial.strip().replace('\x00', '').strip()
                    if serial:
                        log.debug(f"Powdrive connectivity check passed: device responded with serial")
                        return True
            except Exception as e:
                log.debug(f"Powdrive connectivity check via register map failed: {e}")
            
            # Fallback: try direct register read (address 3, size 5)
            try:
                regs = await self._read_holding_regs(3, 5)
                if regs and len(regs) > 0:
                    log.debug(f"Powdrive connectivity check passed: device responded to direct register read")
                    return True
            except Exception as e:
                log.debug(f"Powdrive connectivity check via direct register failed: {e}")
            
            return False
        except Exception as e:
            log.debug(f"Powdrive connectivity check failed: {e}")
            return False
    
    async def read_serial_number(self) -> Optional[str]:
        """Read device serial number for identification."""
        try:
            if not self.client or not self.client.connected:
                # Use _ensure_client_in_current_loop which has proper locking
                await self._ensure_client_in_current_loop()
                await self._ensure_lock_in_current_loop()
            
            # Try to read serial number from register map (address 3, size 5, ASCII)
            try:
                serial = await self.read_by_ident("device_serial_number")
                if serial and isinstance(serial, str):
                    # Clean up serial number (remove nulls, spaces)
                    serial = serial.strip().replace('\x00', '').strip()
                    if serial:
                        log.debug(f"Read serial number from Powdrive device: {serial}")
                        return serial
            except Exception as e:
                log.debug(f"Could not read serial via register map: {e}")
            
            # Fallback: try direct register read (address 3, size 5)
            try:
                regs = await self._read_holding_regs(3, 5)
                if regs:
                    # Decode ASCII from registers
                    buf = bytearray()
                    for w in regs:
                        w = int(w) & 0xFFFF
                        buf.append((w >> 8) & 0xFF)
                        buf.append(w & 0xFF)
                    serial = bytes(buf).split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
                    if serial:
                        log.debug(f"Read serial number via direct register: {serial}")
                        return serial
            except Exception as e:
                log.debug(f"Could not read serial via direct register: {e}")
            
            return None
        except Exception as e:
            log.warning(f"Error reading serial number from Powdrive device: {e}")
            return None


