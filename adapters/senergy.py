import json, re, logging
import threading
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from solarhub.adapters.base import InverterAdapter, JsonRegisterMixin, ModbusClientMixin
from solarhub.models import Telemetry
from solarhub.telemetry_mapper import TelemetryMapper
from typing import Any, Dict, List, Optional
import re
from pathlib import Path
import asyncio


log = logging.getLogger(__name__)

def now_iso() -> str:
    from solarhub.timezone_utils import now_configured_iso
    return now_configured_iso()

def _first_num(values, *keys):
    for k in keys:
        v = values.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def _coerce_enum_map(r: dict) -> dict[int, str] | None:
    """Convert JSON-provided enum map to {int: str}."""
    enum_obj = r.get("enum")
    if not isinstance(enum_obj, dict) or not enum_obj:
        return None
    out: dict[int, str] = {}
    for k, v in enum_obj.items():
        if isinstance(k, int):
            out[k] = str(v)
        else:
            ks = str(k).strip().lower()
            if ks.startswith("0x"):
                out[int(ks, 16)] = str(v)
            else:
                out[int(ks, 10)] = str(v)
    return out


def _int_auto(x):
    s = str(x).strip().lower()
    base = 16 if s.startswith("0x") else 10
    # Handle float strings like "30.0" by converting to float first, then int
    if '.' in s and not s.startswith("0x"):
        return int(float(s))
    return int(s, base)

def _coerce_bit_enum(r: dict, val: int) -> List[str] | None:
    """
    Decode bitmask enums from JSON: r['bit_enum'] = { "0":"desc", "1":"desc", ... }
    Returns list of active flag strings, or ["OK"] if none set. Returns None if not applicable.
    """
    bit_enum = r.get("bit_enum")
    if not isinstance(bit_enum, dict) or not isinstance(val, int):
        return None
    msgs: List[str] = []
    for k, v in bit_enum.items():
        try:
            bit = int(k, 10)
        except Exception:
            bit = int(str(k), 16) if str(k).lower().startswith("0x") else int(str(k))
        if val & (1 << bit):
            msgs.append(str(v))
    return msgs if msgs else ["OK"]

def _regs_to_ascii(raw_regs: List[int], byteorder: str = "big") -> str:
    """
    Convert a list of 16-bit register values into an ASCII string.
    byteorder = "big": [hi, lo] per word (most common in Modbus specs)
    byteorder = "little": [lo, hi] per word
    """
    buf = bytearray()
    for w in raw_regs:
        w = int(w) & 0xFFFF
        if byteorder == "big":
            buf.append((w >> 8) & 0xFF)
            buf.append(w & 0xFF)
        else:
            buf.append(w & 0xFF)
            buf.append((w >> 8) & 0xFF)
    s = bytes(buf).split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
    return s

class SenergyAdapter(InverterAdapter, JsonRegisterMixin, ModbusClientMixin):
    """
    Pure data-driven adapter:
    - All registers come from JSON map (addr, size, kind, type, unit, scale, rw, id, encoder, enum, bit_enum).
    - No hard-coded addresses in Python.
    """

    def __init__(self, inv):
        super().__init__(inv)
        self.client: Optional[AsyncModbusSerialClient | AsyncModbusTcpClient] = None
        self.transport: str = getattr(inv.adapter, "transport", "rtu").lower()
        self.regs: List[Dict[str, Any]] = []
        self.addr_offset: int = getattr(inv.adapter, "addr_offset", 0) or 0
        self._kind_cache: Dict[int, str] = {}  # discovered kind fixes
        self.last_tel: Dict[str, Any] = {}  # store latest telemetry data
        # No internal locking - command queue handles serialization
        self._client_loop: Optional[asyncio.AbstractEventLoop] = None  # Event loop where client was created
        regfile = inv.adapter.register_map_file
        try:
            # Use shared loader (JsonRegisterMixin)
            self.load_register_map(regfile)
            # Create telemetry mapper for standardized field names
            if self.regs:
                self.mapper = TelemetryMapper(self.regs)
                log.debug("Telemetry mapper created with %d mappings", len(self.mapper.device_to_standard))
            else:
                self.mapper = None
        except Exception as e:
            log.warning("Could not load register map %s: %s", regfile, e)
            self.regs = []
            self.mapper = None

    # --------------- Modbus primitives ---------------

    async def connect(self):
        # Store the event loop where the client is created
        try:
            self._client_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._client_loop = asyncio.get_event_loop()
        
        if self.transport == "tcp":
            # TCP Modbus connection
            if not self.inv.adapter.host:
                raise RuntimeError("host is required for TCP transport")
            port = getattr(self.inv.adapter, "port", 502)
            
            self.client = AsyncModbusTcpClient(
                host=self.inv.adapter.host,
                port=port,
                timeout=1.5,
            )
            await self.client.connect()
            if not self.client.connected:
                raise RuntimeError(f"Modbus TCP connection failed to {self.inv.adapter.host}:{port}")
            log.info(f"SenergyAdapter connected via TCP to {self.inv.adapter.host}:{port}")
        elif self.transport == "rtu":
            # RTU Modbus connection
            if not self.inv.adapter.serial_port:
                raise RuntimeError("serial_port is required for RTU transport")
            
            self.client = AsyncModbusSerialClient(
                port=self.inv.adapter.serial_port,
                baudrate=self.inv.adapter.baudrate,
                parity=self.inv.adapter.parity,
                stopbits=self.inv.adapter.stopbits,
                bytesize=self.inv.adapter.bytesize,
                timeout=1.5,
            )
            await self.client.connect()
            if not self.client.connected:
                raise RuntimeError(f"Modbus RTU connection failed on {self.inv.adapter.serial_port}")
            log.info(f"SenergyAdapter connected via RTU on {self.inv.adapter.serial_port}")
        else:
            raise RuntimeError(f"Unsupported transport type: {self.transport}. Use 'rtu' or 'tcp'")

    async def close(self):
        try:
            log.info("Senergy close() called - starting client shutdown")
            # Use robust close to ensure port release
            if hasattr(self, '_force_close_client'):
                await self._force_close_client()
            else:
                if self.client:
                    await self.client.close()
                self.client = None
            log.info("Senergy close() completed - client reference cleared")
        except Exception as e:
            log.warning(f"Senergy close() encountered error: {e}")
        # Reset migration flag when closing
        if hasattr(self, '_client_migrated'):
            self._client_migrated = False
        # Drop the loop-bound lock so it is recreated in the next active loop
        if hasattr(self, '_modbus_lock'):
            self._modbus_lock = None
    
    async def _get_client_config(self) -> Dict[str, Any]:
        """Get configuration for creating Modbus client (RTU or TCP)."""
        if self.transport == "tcp":
            return {
                'host': self.inv.adapter.host,
                'port': getattr(self.inv.adapter, "port", 502),
                'timeout': 1.5,
            }
        else:  # RTU
            return {
                'port': self.inv.adapter.serial_port,
                'baudrate': self.inv.adapter.baudrate,
                'parity': self.inv.adapter.parity,
                'stopbits': self.inv.adapter.stopbits,
                'bytesize': self.inv.adapter.bytesize,
                'timeout': 1.5,
            }

    async def _read_input_regs(self, address: int, count: int) -> List[int]:
        assert self.client
        # Ensure client is in current event loop
        await self._ensure_client_in_current_loop()
        # Verify client is connected
        if not self.client.connected:
            log.warning("Client not connected, attempting to reconnect")
            await self._ensure_client_in_current_loop()
            if not self.client.connected:
                raise RuntimeError("client not connected")
        rr = await self.client.read_holding_registers(address=address, count=count, device_id=self.inv.adapter.unit_id)
        if rr.isError():
            raise RuntimeError(f"Modbus read error @{address}")
        return list(rr.registers)

    async def _read_holding_regs(self, address: int, count: int) -> List[int]:
        assert self.client
        # Ensure client is in current event loop
        await self._ensure_client_in_current_loop()
        # Verify client is connected
        if not self.client.connected:
            log.warning("Client not connected, attempting to reconnect")
            await self._ensure_client_in_current_loop()
            if not self.client.connected:
                raise RuntimeError("client not connected")
        rr = await self.client.read_holding_registers(address=address, count=count, device_id=self.inv.adapter.unit_id)
        if rr.isError():
            raise RuntimeError(f"Modbus read error @{address}")
        return list(rr.registers)

    async def _write_holding_u16(self, address: int, value: int) -> None:
        assert self.client
        # Ensure client is in current event loop
        await self._ensure_client_in_current_loop()
        # Verify client is connected
        if not self.client.connected:
            log.warning("Client not connected, attempting to reconnect")
            await self._ensure_client_in_current_loop()
            if not self.client.connected:
                raise RuntimeError("client not connected")
        log.debug(f"Modbus write: addr=0x{address:04X} (dec={address}), value={value} (0x{value:04X}), unit_id={self.inv.adapter.unit_id}")
        try:
            rq = await self.client.write_register(address=address, value=value, device_id=self.inv.adapter.unit_id)
            if rq.isError():
                log.error(f"Modbus write failed: addr=0x{address:04X}, value={value}, error={rq}")
                raise RuntimeError(f"Modbus write error at 0x{address:04X}: {rq}")
            log.debug(f"✓ Modbus write successful: addr=0x{address:04X}, value={value}")
        except (RuntimeError, ValueError, AttributeError) as e:
            # If lock is bound to different event loop (pymodbus's), recreate client and retry
            error_str = str(e)
            if "bound to a different event loop" in error_str or "different event loop" in error_str.lower():
                log.warning("Lock bound to different event loop, recreating client and retrying write")
                # Force recreate client (this will also recreate pymodbus's internal lock)
                if hasattr(self, '_client_migrated'):
                    self._client_migrated = False
                self.client = None
                await self._ensure_client_in_current_loop()
                # Retry the operation
                rq = await self.client.write_register(address=address, value=value, device_id=self.inv.adapter.unit_id)
                if rq.isError():
                    log.error(f"Modbus write failed: addr=0x{address:04X}, value={value}, error={rq}")
                    raise RuntimeError(f"Modbus write error at 0x{address:04X}: {rq}")
                log.debug(f"✓ Modbus write successful: addr=0x{address:04X}, value={value}")
            else:
                raise

    async def _write_holding_u16_list(self, address: int, values: List[int]) -> None:
        assert self.client
        # Ensure client is in current event loop
        await self._ensure_client_in_current_loop()
        # Verify client is connected
        if not self.client.connected:
            log.warning("Client not connected, attempting to reconnect")
            await self._ensure_client_in_current_loop()
            if not self.client.connected:
                raise RuntimeError("client not connected")
        log.debug(f"Modbus write multiple: addr=0x{address:04X} (dec={address}), values={values}, count={len(values)}, unit_id={self.inv.adapter.unit_id}")
        try:
            rq = await self.client.write_registers(address, values, unit=self.inv.adapter.unit_id)
            if rq.isError():
                log.error(f"Modbus write multiple failed: addr=0x{address:04X}, values={values}, error={rq}")
                raise RuntimeError(f"Modbus write error at 0x{address:04X}: {rq}")
            log.debug(f"✓ Modbus write multiple successful: addr=0x{address:04X}, values={values}")
        except (RuntimeError, ValueError, AttributeError) as e:
            # If lock is bound to different event loop (pymodbus's), recreate client and retry
            error_str = str(e)
            if "bound to a different event loop" in error_str or "different event loop" in error_str.lower():
                log.warning("Lock bound to different event loop, recreating client and retrying write multiple")
                # Force recreate client (this will also recreate pymodbus's internal lock)
                if hasattr(self, '_client_migrated'):
                    self._client_migrated = False
                self.client = None
                await self._ensure_client_in_current_loop()
                # Retry the operation
                rq = await self.client.write_registers(address, values, unit=self.inv.adapter.unit_id)
                if rq.isError():
                    log.error(f"Modbus write multiple failed: addr=0x{address:04X}, values={values}, error={rq}")
                    raise RuntimeError(f"Modbus write error at 0x{address:04X}: {rq}")
                log.debug(f"✓ Modbus write multiple successful: addr=0x{address:04X}, values={values}")
            else:
                raise

    @staticmethod
    def _sanitize_key(s: str) -> str:
        return re.sub(r"[^a-z0-9_]+","_", s.strip().lower())

    async def _read_range_kind(self, kind: str, start: int, count: int) -> List[int]:
        base = start + self.addr_offset
        if kind == "input":
            return await self._read_input_regs(base, count)
        return await self._read_holding_regs(base, count)

    async def _write_by_ident(self, ident: str, value: Any) -> None:
        """Backwards-compatible wrapper -> shared mixin write_by_ident."""
        log.info(f"Writing to inverter register {ident}={value}")
        await self.write_by_ident(ident, value)
        log.info(f"Successfully wrote to inverter register {ident}")

    async def _read_by_ident(self, ident: str) -> Any:
        """Backwards-compatible wrapper -> shared mixin read_by_ident."""
        return await self.read_by_ident(ident)
        r = self._find_reg_by_id_or_name(ident)
        addr = int(r["addr"]) + self.addr_offset
        size = max(1, r.get("size", 1))
        
        # Read the register
        regs = await self._read_holding_regs(addr, size)
        
        # Decode the value (simplified version of the poll method)
        t = (r.get("type") or "").lower()
        enc = (r.get("encoder") or "").lower()
        scale = r.get("scale")
        
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
        
        # Apply scaling
        if scale and isinstance(val, (int, float)):
            val = val * scale
        
        return val

    def _enum_label_or_raw(self, ident: str, value: Any) -> Any:
        """
        If the target register has an 'enum', allow label input; otherwise return as-is.
        Your existing 'write' branch already supports this, but we mirror it here for
        the direct helpers above.
        """
        r = self._find_reg_by_id_or_name(ident)
        enum = r.get("enum") or None
        if not enum:
            return value
        raw_keys = set(str(k) for k in enum.keys())
        labels = {str(v): str(k) for k, v in enum.items()}
        s = str(value)
        if s in raw_keys:
            return s
        if s in labels:
            return labels[s]
        # also accept hex-like ints
        try:
            _ = int(s, 0)
            return s
        except Exception:
            raise ValueError(f"{ident}: value '{value}' not in allowed options {list(enum.values())}")

    # --------------- JSON lookup & encoding helpers ---------------

    def _find_reg_by_id_or_name(self, ident: str) -> Dict[str, Any]:
        """
        Find a register JSON object by:
          - exact 'id' match (preferred), or
          - sanitized 'name' match.
        Raises KeyError if not found.
        """
        ident_s = self._sanitize_key(ident)
        for r in self.regs:
            if "ha_key" not in r:
                rid = r.get("id") or r.get("name") or f"reg_{int(r['addr']):04x}"
                r["ha_key"] = self._sanitize_key(str(rid))
            else:
                rid = r.get("id") or r.get("name") or f"reg_{int(r['addr']):04x}"
            if isinstance(rid, str) and self._sanitize_key(rid) == ident_s:
                return r
        for r in self.regs:
            nm = r.get("name")
            if isinstance(nm, str) and self._sanitize_key(nm) == ident_s:
                return r
        raise KeyError(f"register not found: {ident}")

    @staticmethod
    def _encode_hhmm(val: str) -> int:
        h, m = [int(x) for x in val.split(":", 1)]
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Invalid HH:MM")
        return ((h & 0xFF) << 8) | (m & 0xFF)

    def _encode_value(self, r: Dict[str, Any], value: Any) -> List[int]:
        """
        Convert a high-level value → list of 16-bit words according to JSON fields:
          - type: U16/S16/U32/S32
          - size: number of 16-bit registers
          - scale: numeric scaling to invert on write (value / scale)
          - encoder: "hhmm", "ascii", "bool", "month_day"
        """
        enc = (r.get("encoder") or "").lower()
        typ = (r.get("type") or "").upper()
        size = int(r.get("size") or 1)
        scale = r.get("scale")

        # --- helper for bool parsing ---
        def _to_bool(v: Any) -> bool:
            if isinstance(v, bool):
                return v
            s = str(v).strip().lower()
            return s in ("1", "true", "on", "yes", "y")

        # --- encoders take precedence ---
        if enc == "hhmm":
            raw_u16 = self._encode_hhmm(str(value))
            return [raw_u16]

        if enc == "bool":
            return [1 if _to_bool(value) else 0]

        if enc == "ascii":
            s = str(value)
            # pack 2 chars per 16-bit word, big-endian
            words: List[int] = []
            if len(s) % 2 == 1:
                s = s + "\x00"
            for i in range(0, len(s), 2):
                hi = ord(s[i]) & 0xFF
                lo = ord(s[i + 1]) & 0xFF
                words.append((hi << 8) | lo)
            # truncate/extend to size
            words = (words + [0] * size)[:size]
            return words

        if enc == "month_day":
            # Accept "MM-DD", "MM/DD", {"month": M, "day": D}, or (M, D)
            m = d = None
            if isinstance(value, dict):
                m = int(value.get("month"))
                d = int(value.get("day"))
            elif isinstance(value, (list, tuple)) and len(value) >= 2:
                m = int(value[0])
                d = int(value[1])
            else:
                s = str(value).strip().replace("/", "-")
                parts = s.split("-", 1)
                if len(parts) == 2:
                    m = int(parts[0])
                    d = int(parts[1])
            if m is None or d is None:
                raise ValueError(
                    f"month_day encoder expects 'MM-DD', 'MM/DD', {{'month':..,'day':..}} or (m,d); got {value!r}")
            if not (1 <= m <= 12 and 1 <= d <= 31):
                raise ValueError(f"month_day out of range: month={m}, day={d}")
            raw_u16 = ((m & 0xFF) << 8) | (d & 0xFF)
            return [raw_u16]

        if enc == "second":
            sec = int(value)
            if not (0 <= sec <= 59):
                raise ValueError(f"second out of range: {sec}")
            raw_u16 = ((sec & 0xFF) << 8) | 0x00
            return [raw_u16]
        # --- numeric types (apply inverse scaling on write) ---
        if isinstance(value, (int, float)) and scale:
            try:
                value = int(round(float(value) / float(scale)))
            except Exception:
                pass

        if typ in ("U16", "S16") or size == 1:
            return [_int_auto(value) & 0xFFFF]

        if typ in ("U32", "S32") or size == 2:
            v = int(value) & 0xFFFFFFFF
            hi = (v >> 16) & 0xFFFF
            lo = v & 0xFFFF
            return [hi, lo]

        # generic list (caller may pass pre-split values)
        if isinstance(value, list):
            return [int(x) & 0xFFFF for x in value][:size]

        # fallback: zero-fill
        return [0] * size

    # --------------- Poll (read) ---------------

    async def poll(self) -> Telemetry:
        # Ensure client is connected before polling (lazy connection)
        await self._ensure_client_in_current_loop()
        # group by (effective) kind with cache corrections
        by_kind: Dict[str, List[Dict[str, Any]]] = {"input": [], "holding": []}
        for r in self.regs:
            addr = int(r["addr"])
            k = self._kind_cache.get(addr, (r.get("kind") or "input"))
            rr = dict(r)
            rr["kind"] = k if k in ("input", "holding") else "input"
            by_kind[rr["kind"]].append(rr)

        values: Dict[str, Any] = {}

        async def decode_into(items: List[Dict[str, Any]], regs: List[int], window_start: int):
            for r in items:
                off = r["addr"] - window_start
                size = max(1, r.get("size", 1))
                raw = regs[off:off+size] if off >= 0 else []
                t = (r.get("type") or "").lower()
                u = (r.get("unit") or "").lower()
                enc = (r.get("encoder") or "").lower()

                # ASCII / string fields
                is_ascii = ("ascii" in u) or ("ascii" in t) or ("string" in t)
                if is_ascii:
                    val: Any = _regs_to_ascii(raw, byteorder="big")
                    # Debug logging for ASCII fields
                    reg_id = r.get("id", "unknown")
                    if reg_id in ["device_model", "device_serial_number"]:
                        log.debug(f"ASCII field {reg_id}: raw={raw}, decoded='{val}'")
                else:
                    # --- special single-word encoders (decode) ---
                    if size == 1 and raw:
                        w = int(raw[0]) & 0xFFFF
                        if enc == "hhmm":
                            hh = (w >> 8) & 0xFF
                            mm = w & 0xFF
                            # clamp to sensible ranges just in case
                            if 0 <= hh <= 23 and 0 <= mm <= 59:
                                val = f"{hh:02d}:{mm:02d}"
                            else:
                                val = {"hour": (hh & 0xFF), "minute": (mm & 0xFF)}
                        elif enc == "month_day":
                            m = (w >> 8) & 0xFF
                            d = w & 0xFF
                            if 1 <= m <= 12 and 1 <= d <= 31:
                                val = f"{m:02d}-{d:02d}"
                            else:
                                val = {"month": (m & 0xFF), "day": (d & 0xFF)}
                        elif enc == "second":
                            sec = (w >> 8) & 0xFF
                            # low byte is spec'd as 0; ignore it on decode
                            if 0 <= sec <= 59:
                                val = sec
                            else:
                                val = {"second": (sec & 0xFF)}
                        else:
                            val = None  # fall through to numeric decode below
                    else:
                        val = None

                    # --- numeric (default) decode if not handled above ---
                    if val is None:
                        if size == 1:
                            val = int(raw[0]) if raw else None
                            if "s16" in t and val is not None and val >= 0x8000:
                                val = val - 0x10000
                        elif size == 2:
                            if raw and len(raw) >= 2:
                                hi, lo = raw[0], raw[1]
                                v = (hi << 16) | lo
                                if "s32" in t and v & 0x80000000:
                                    v = -((~v & 0xFFFFFFFF) + 1)
                                val = v
                            else:
                                val = None
                        else:
                            # keep list for non-ascii multiword numeric/opaque fields
                            val = raw

                    # --- apply bit_enum / enum / scale ---
                    if isinstance(val, int):
                        bit_msgs = _coerce_bit_enum(r, val)
                        if bit_msgs is not None:
                            val = bit_msgs
                        else:
                            enum_map = _coerce_enum_map(r)
                            if enum_map is not None:
                                val = enum_map.get(val, f"UNKNOWN({val})")
                            else:
                                sc = r.get("scale")
                                if sc and isinstance(val, (int, float)):
                                    val = round(val * sc, 3)



                key = r.get("ha_key") or self._sanitize_key(r.get("name") or r.get("id") or f"reg_{r['addr']:04X}")
                values[key] = val
                # Debug logging for key device fields
                reg_id = r.get("id", "unknown")
                if reg_id in ["device_model", "device_serial_number"]:
                    log.debug(f"Stored {reg_id} with key '{key}' = '{val}'")
                
                # Debug logging for energy registers
                if reg_id in ["battery_daily_charge_energy", "battery_daily_discharge_energy", "daily_energy_to_eps"]:
                    log.debug(f"Energy register {reg_id}: raw={raw}, decoded={val}, key='{key}'")

        # Ensure client is in current event loop before polling
        await self._ensure_client_in_current_loop()
        
        # read each kind in small, safe chunks and fallback if needed
        MAX_CHUNK = 20
        MAX_GAP = 4
        for kind, items in by_kind.items():
            items = sorted(items, key=lambda x: x["addr"])
            i = 0
            while i < len(items):
                start = items[i]["addr"]
                end = start + max(1, items[i].get("size", 1))
                j = i + 1
                while j < len(items):
                    a = items[j]["addr"]
                    sz = max(1, items[j].get("size", 1))
                    if a - end > MAX_GAP or (a + sz - start) > MAX_CHUNK:
                        break
                    end = max(end, a + sz)
                    j += 1
                count = end - start
                window = items[i:j]

                try:
                    regs = await self._read_range_kind(kind, start, count)
                    await decode_into(window, regs, start)
                except Exception:
                    log.debug("Chunk read failed (%s @0x%04X len=%d), falling back per-register",
                              kind, start, count)
                    other = "holding" if kind == "input" else "input"
                    for r in window:
                        addr = r["addr"]
                        size = max(1, r.get("size", 1))
                        ok = False
                        # Check cache first
                        cached_kind = self._kind_cache.get(addr)
                        if cached_kind:
                            try_kinds = [cached_kind]
                        else:
                            try_kinds = [r["kind"], other]
                        
                        for try_kind in try_kinds:
                            try:
                                regs = await self._read_range_kind(try_kind, addr, size)
                                await decode_into([r], regs, addr)
                                if try_kind != r["kind"]:
                                    # Only log if not already cached (first discovery)
                                    if addr not in self._kind_cache:
                                        log.info("Adjusted kind for 0x%04X -> %s (cached for future use)", addr, try_kind)
                                    else:
                                        log.debug("Using cached kind for 0x%04X -> %s", addr, try_kind)
                                    self._kind_cache[addr] = try_kind
                                ok = True
                                break
                            except Exception:
                                continue
                        if not ok:
                            reg_id = r.get("id", "unknown")
                            if reg_id in ["battery_daily_charge_energy", "battery_daily_discharge_energy", "daily_energy_to_eps"]:
                                log.error("Failed to read energy register %s at 0x%04X (size=%d)", reg_id, addr, size)
                            else:
                                log.warning("Skip unreadable register 0x%04X (size=%d)", addr, size)
                i = j

                # --- derive pv_power from MPPTx if available ---
                # mppt_number tells how many MPPTs are active (1..N); sum mppt1_power..mpptN_power
            mppt_count = None
            for k in ("mppt_number", "mppt_num", "mppt_count"):
                v = values.get(k)
                if isinstance(v, (int, float)):
                    mppt_count = int(v)
                    break

            if mppt_count and mppt_count > 0:
                pv_sum = 0.0
                found = False
                for i in range(1, mppt_count + 1):
                    # Prefer standardized IDs, fallback to deprecated
                    for key in (f"pv{i}_power_w", f"mppt{i}_power_w", f"mppt{i}_power"):
                        vv = values.get(key)
                        if isinstance(vv, (int, float)):
                            pv_sum += float(vv)
                            found = True
                            break
                if found:
                    values["pv_power"] = round(pv_sum, 0)
        load_r = _first_num(values, "load_phase_r_w", "phase_r_watt_of_load")
        eps_r = _first_num(values, "eps_r_power", "phase_r_watt_of_eps")

        load_power = round(load_r + eps_r, 0) if (load_r or eps_r) else None
        grid_w = _first_num(values, "grid_phase_r_w", "phase_r_watt_of_grid", "grid_power_w")
        
        # Prefer standardized IDs, fallback to deprecated for backward compatibility
        batt_v = values.get("battery_voltage_v") or values.get("battery_voltage")
        batt_i = values.get("battery_current_a") or values.get("battery_current")
        batt_p_raw = values.get("battery_power_w") or values.get("battery_power")
        batt_soc = values.get("battery_soc_pct") or values.get("battery_soc")
        inv_temp = values.get("inverter_temp_c") or values.get("inner_temperature")
        
        # Map device-specific data to standardized field names
        if hasattr(self, 'mapper') and self.mapper:
            standardized_values = self.mapper.map_to_standard(values)
            # Use standardized values for extra, but keep original values too for backward compatibility
            extra = standardized_values.get("extra", {})
            extra.update(standardized_values)  # Ensure all standardized fields are in extra
            extra.update(values)  # Keep original device-specific keys for backward compatibility
        else:
            # No mapper available, use values as-is
            extra = values.copy()
        
        # Detect phase type from telemetry data
        from solarhub.inverter_metadata import InverterMetadata
        detected_phase_type = InverterMetadata.detect_phase_type_from_telemetry(extra)
        if detected_phase_type:
            extra["phase_type"] = detected_phase_type
            log.debug(f"Detected phase type from telemetry data: {detected_phase_type}")
        
        # Get array_id from inverter config
        array_id = getattr(self.inv, 'array_id', None)
        
        tel = Telemetry(
            ts=now_iso(),
            pv_power_w=values.get("pv_power") ,
            grid_power_w=grid_w,
            load_power_w= load_power,
            batt_voltage_v=batt_v,
            batt_current_a=batt_i,
            batt_power_w=self.normalize_battery_power(
                self._calculate_battery_power(batt_v, batt_i, batt_p_raw),
                invert=False  # Senergy's V*I calculation already matches standard convention
            ),
            batt_soc_pct=batt_soc,
            inverter_temp_c=inv_temp,
            # Additional energy fields
            battery_daily_charge_energy=values.get("battery_daily_charge_energy"),
            battery_daily_discharge_energy=values.get("battery_daily_discharge_energy"),
            daily_energy_to_eps=values.get("daily_energy_to_eps"),
            array_id=array_id,
            extra=extra,
        )
        
        # Store the latest telemetry data for access by other components
        # Store the Telemetry object itself, not just the raw values
        self.last_tel = tel
        return tel
    
    def _calculate_battery_power(self, voltage: Optional[float], current: Optional[float], raw_power: Optional[float] = None) -> Optional[float]:
        """
        Calculate battery power from voltage and current, with comparison to raw register value.
        
        Args:
            voltage: Battery voltage in volts
            current: Battery current in amperes (positive = charging, negative = discharging)
            raw_power: Raw battery power from inverter register (for comparison)
            
        Returns:
            Battery power in watts (positive = discharging, negative = charging)
        """
        try:
            if voltage is None or current is None:
                log.debug("Cannot calculate battery power: missing voltage or current data")
                return None
            
            # Ensure we have valid numeric values
            voltage = float(voltage)
            current = float(current)
            
            # Calculate power: P = V * I
            # Consistent sign convention:
            # - Positive current = charging (power flowing into battery) → Positive power = charging
            # - Negative current = discharging (power flowing out of battery) → Negative power = discharging
            calculated_power = voltage * current
            
            # Round to 1 decimal place for consistency
            calculated_power = round(calculated_power, 1)
            
            # Compare with raw register value if available
            if raw_power is not None:
                try:
                    raw_power = float(raw_power)
                    
                    # Check for invalid/error values (near 2^32-1 suggests register error/overflow)
                    # Also check for values that are clearly impossible for battery power
                    if raw_power > 4000000000 or raw_power < -4000000000:  # > 4 billion watts is clearly invalid
                        log.warning(f"Battery power register appears invalid/overflow: raw={raw_power}W, using calculated value {calculated_power}W")
                        return calculated_power
                    
                    # Check for reasonable battery power range (typically -10kW to +10kW for residential systems)
                    if abs(raw_power) > 20000:  # > 20kW is likely invalid for residential battery
                        log.warning(f"Battery power register value seems unreasonable: raw={raw_power}W, using calculated value {calculated_power}W")
                        return calculated_power
                    
                    difference = abs(calculated_power - raw_power)
                    difference_pct = (difference / abs(raw_power)) * 100 if raw_power != 0 else 0
                    
                    # Log significant discrepancies (>5% difference)
                    if difference_pct > 5:
                        log.warning(f"Battery power discrepancy: calculated={calculated_power}W, raw={raw_power}W, diff={difference_pct:.1f}%")
                    else:
                        log.debug(f"Battery power comparison: calculated={calculated_power}W, raw={raw_power}W, diff={difference_pct:.1f}%")
                        
                except (ValueError, TypeError):
                    log.debug(f"Could not compare with raw battery power value: {raw_power}")
            
            log.debug(f"Battery power calculation: {voltage}V × {current}A = {calculated_power}W (current: {'positive=charging' if current > 0 else 'negative=discharging'}, power: {'positive=charging' if calculated_power > 0 else 'negative=discharging'})")
            return calculated_power
            
        except (ValueError, TypeError) as e:
            log.warning(f"Failed to calculate battery power from voltage={voltage}, current={current}: {e}")
            return None

    # --------------- Generic write API (JSON-driven) ---------------

    async def handle_command(self, cmd: Dict[str, Any]):
        """
        JSON-driven writing. Supported forms:
          - {"action":"write", "id":"work_mode", "value": 2}
          - {"action":"write_many", "writes":[{"id":"charge_start_time_1","value":"07:00"}, {"id":"charge_end_time_1","value":"17:30"}]}

        Where each JSON register has:
          {
            "id": "work_mode",        # stable key (recommended)
            "name": "Work Mode",      # human name
            "addr": 0x2100,
            "kind": "holding",        # must be holding for writes
            "rw": "RW",               # or WO
            "size": 1,                # number of 16-bit words
            "type": "U16",            # U16/S16/U32/S32
            "scale": null,            # optional scale for numeric fields
            "encoder": "hhmm|bool|ascii", # optional, for special formats
          }
        """
        action = (cmd.get("action") or "").lower()
        log.info(f"Executing command: {action} with parameters: {cmd}")
        
        # Command queue handles serialization - no internal locking needed
        return await self._handle_command_unsafe(cmd)
    
    async def _handle_command_unsafe(self, cmd: Dict[str, Any]):
        """Internal command handler - command queue handles serialization."""
        # Ensure we have a client in the current event loop
        await self._ensure_client_in_current_loop()
        
        action = (cmd.get("action") or "").lower()

        if action == "set_work_mode":
            mode = cmd.get("mode")
            log.info(f"Setting work mode to: {mode}")
            raw = self._enum_label_or_raw("hybrid_work_mode", mode)
            await self._write_by_ident("hybrid_work_mode", raw)
            log.info(f"Work mode set successfully to: {mode}")
            return {"ok": True}

        if action == "set_grid_charge":
            enable = bool(cmd.get("enable"))
            end_soc = cmd.get("end_soc", None)
            log.info(f"Setting grid charge: enable={enable}, end_soc={end_soc}%")
            await self._write_by_ident("grid_charge", 1 if enable else 0)
            if end_soc is not None:
                await self._write_by_ident("capacity_of_grid_charger_end", int(end_soc))
            log.info(f"Grid charge settings applied successfully")
            return {"ok": True}

        if action.startswith("set_tou_window"):
            m = re.match(r"set_tou_window([1-3])$", action)
            if not m:
                return {"ok": False, "reason": "bad window index"}
            idx = int(m.group(1))
            s = str(cmd.get("chg_start", "00:00"))
            e = str(cmd.get("chg_end", "00:00"))
            power = cmd.get("charge_power_w", 0)
            end_soc = cmd.get("charge_end_soc", 100)
            frequency = cmd.get("frequency", "Everyday")
            
            log.info(f"Setting TOU charge window {idx}: {s}-{e}, power: {power}W, end_soc: {end_soc}%, frequency: {frequency}")
            
            # Set start and end times
            await self._write_by_ident(f"charge_start_time_{idx}", s)  # encoder "hhmm" in JSON
            await self._write_by_ident(f"charge_end_time_{idx}", e)
            
            # Set frequency for this window
            frequency_raw = self._enum_label_or_raw(f"charge_frequency_{idx}", frequency)
            await self._write_by_ident(f"charge_frequency_{idx}", frequency_raw)
            
            # Set individual window charge power
            if power is not None and power > 0:
                await self._write_by_ident(f"charge_power_{idx}", int(power))
                log.info(f"Set charge window {idx} power: {power}W")
            
            # Set individual window charge end SOC
            if end_soc is not None:
                await self._write_by_ident(f"charger_end_soc_{idx}", int(end_soc))
                log.info(f"Set charge window {idx} end SOC: {end_soc}%")
            
            return {"ok": True}

            # Optional discharge TOU windows (use if you program them)
        if action.startswith("set_tou_discharge_window"):
            m = re.match(r"set_tou_discharge_window([1-3])$", action)
            if not m:
                return {"ok": False, "reason": "bad discharge window index"}
            idx = int(m.group(1))
            s = str(cmd.get("dch_start", "00:00"))
            e = str(cmd.get("dch_end", "00:00"))
            power = cmd.get("discharge_power_w", 0)
            end_soc = cmd.get("discharge_end_soc", 30)
            frequency = cmd.get("frequency", "Everyday")
            
            log.info(f"Setting TOU discharge window {idx}: {s}-{e}, power: {power}W, end_soc: {end_soc}%, frequency: {frequency}")
            
            # Set start and end times
            await self._write_by_ident(f"discharge_start_time_{idx}", s)
            await self._write_by_ident(f"discharge_end_time_{idx}", e)
            
            # Set frequency for this window
            frequency_raw = self._enum_label_or_raw(f"discharge_frequency_{idx}", frequency)
            await self._write_by_ident(f"discharge_frequency_{idx}", frequency_raw)
            
            # Set individual window discharge power
            if power is not None and power > 0:
                await self._write_by_ident(f"discharge_power_{idx}", int(power))
                log.info(f"Set discharge window {idx} power: {power}W")
            
            # Set individual window discharge end SOC
            if end_soc is not None:
                await self._write_by_ident(f"discharge_end_soc_{idx}", int(end_soc))
                log.info(f"Set discharge window {idx} end SOC: {end_soc}%")
            
            return {"ok": True}

        if action == "set_discharge_limits":
            end_soc = int(cmd.get("end_soc", 20))
            log.info(f"Setting discharge limits: end_soc={end_soc}%")
            await self._write_by_ident("capacity_of_discharger_end_eod_", end_soc)
            log.info(f"Discharge limits set successfully")
            return {"ok": True}

        if action == "set_max_grid_charge_power_w":
            val = int(cmd.get("value", 1000))
            log.info(f"Setting max grid charge power: {val}W")
            await self._write_by_ident("maximum_grid_charge_power", val)
            log.info(f"Max grid charge power set successfully")
            return {"ok": True}

        if action == "set_max_charge_power_w":
            val = int(cmd.get("value", 5000))
            log.info(f"Setting max charge power: {val}W")
            await self._write_by_ident("max_charge_power", val)
            log.info(f"Max charge power set successfully")
            return {"ok": True}

        if action == "set_max_discharge_power_w":
            val = int(cmd.get("value", 5000))
            log.info(f"Setting max discharge power: {val}W")
            await self._write_by_ident("max_discharge_power", val)
            log.info(f"Max discharge power set successfully")
            return {"ok": True}

        if action == "write":
            ident = cmd.get("id") or cmd.get("name")
            if not ident:
                return {"ok": False, "reason": "missing id/name"}
            try:
                r = self._find_reg_by_id_or_name(ident)
            except KeyError as e:
                return {"ok": False, "reason": str(e)}
            if (r.get("kind") or "").lower() != "holding":
                return {"ok": False, "reason": "register is not holding (write not allowed)"}
            if str(r.get("rw","RO")).upper() not in ("RW","WO"):
                return {"ok": False, "reason": "register is read-only"}

            # --- Bounds/enum validation before encode ---
            enc = (r.get("encoder") or "").lower()
            enum = r.get("enum") or None
            scale = r.get("scale")

            # If user passes strings for numbers, try to coerce early (leave bool/ascii/hhmm/month_day to encoders)
            value = cmd.get("value")
            candidate = value
            if enc not in ("ascii", "hhmm", "month_day", "second", "bool") and enum is None:
                try:
                    candidate = float(value)
                except Exception:
                    pass

            # Validate against enum (selects)
            if enum:
                # allow either raw key (e.g., "0x0001" or "1") OR label ("Time-based control")
                raw_keys = set(str(k) for k in enum.keys())
                labels = {str(v): str(k) for k, v in enum.items()}
                sv = str(value)
                if sv in raw_keys:
                    pass  # ok
                elif sv in labels:
                    value = labels[sv]  # convert label back to raw key for encoding
                else:
                    raise ValueError(f"Value '{value}' not in allowed options: {list(enum.values())}")

            # Validate min/max for numeric writables (bounds are specified in *scaled/user* units)
            if isinstance(candidate, (int, float)) and (("min" in r) or ("max" in r)):
                v_user = float(candidate)
                v_min = r.get("min", None)
                v_max = r.get("max", None)
                if v_min is not None and v_user < float(v_min):
                    raise ValueError(f"value {v_user} < min {v_min} for {ident}")
                if v_max is not None and v_user > float(v_max):
                    raise ValueError(f"value {v_user} > max {v_max} for {ident}")
                # normalize back to 'value' so scaling/encoding below uses the validated user value
                value = v_user
            words = self._encode_value(r, value)
            addr = int(r["addr"]) + self.addr_offset
            try:
                if len(words) == 1:
                    await self._write_holding_u16(addr, words[0])
                else:
                    await self._write_holding_u16_list(addr, words)
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "reason": str(e)}

        if action == "write_many":
            writes = cmd.get("writes") or []
            errors: List[Tuple[str,str]] = []
            for w in writes:
                ident = w.get("id") or w.get("name")
                if not ident:
                    errors.append(("<missing>", "missing id/name"))
                    continue
                try:
                    r = self._find_reg_by_id_or_name(ident)
                    if (r.get("kind") or "").lower() != "holding":
                        raise RuntimeError("register is not holding (write not allowed)")
                    if str(r.get("rw","RO")).upper() not in ("RW","WO"):
                        raise RuntimeError("register is read-only")
                    # --- Bounds/enum validation before encode ---
                    enc = (r.get("encoder") or "").lower()
                    enum = r.get("enum") or None
                    scale = r.get("scale")
                    value = w.get("value")
                    candidate = value
                    if enc not in ("ascii", "hhmm", "month_day", "second", "bool") and enum is None:
                        try:
                            candidate = float(value)
                        except Exception:
                            pass

                    # Validate against enum (selects)
                    if enum:
                        # allow either raw key (e.g., "0x0001" or "1") OR label ("Time-based control")
                        raw_keys = set(str(k) for k in enum.keys())
                        labels = {str(v): str(k) for k, v in enum.items()}
                        sv = str(value)
                        if sv in raw_keys:
                            pass  # ok
                        elif sv in labels:
                            value = labels[sv]  # convert label back to raw key for encoding
                        else:
                            raise ValueError(f"Value '{value}' not in allowed options: {list(enum.values())}")

                    # Validate min/max for numeric writables (bounds are specified in *scaled/user* units)
                    if isinstance(candidate, (int, float)) and (("min" in r) or ("max" in r)):
                        v_user = float(candidate)
                        v_min = r.get("min", None)
                        v_max = r.get("max", None)
                        if v_min is not None and v_user < float(v_min):
                            raise ValueError(f"value {v_user} < min {v_min} for {r.get('id')}")
                        if v_max is not None and v_user > float(v_max):
                            raise ValueError(f"value {v_user} > max {v_max} for {r.get('id')}")
                        # normalize back to 'value' so scaling/encoding below uses the validated user value
                        value = v_user
                    words = self._encode_value(r, value)
                    addr = int(r["addr"]) + self.addr_offset
                    if len(words) == 1:
                        await self._write_holding_u16(addr, words[0])
                    else:
                        await self._write_holding_u16_list(addr, words)
                except Exception as e:
                    errors.append((ident, str(e)))
            return {"ok": len(errors)==0, "errors": errors}

        return {"ok": False, "reason": "unknown action; use 'write' or 'write_many'"}
    
    async def check_connectivity(self) -> bool:
        """Check if Senergy device is connected and responding by reading serial number register."""
        try:
            if not self.client or not self.client.connected:
                await self.connect()
            
            # Try to read serial number register as connectivity check
            # This is a reliable way to verify the device is responding
            try:
                serial = await self.read_by_ident("device_serial_number")
                if serial and isinstance(serial, str):
                    serial = serial.strip().replace('\x00', '').strip()
                    if serial:
                        log.debug(f"Senergy connectivity check passed: device responded with serial")
                        return True
            except Exception as e:
                log.debug(f"Senergy connectivity check via register map failed: {e}")
            
            # Fallback: try direct register read (address 6672, size 8)
            try:
                regs = await self._read_holding_regs(6672, 8)
                if regs and len(regs) > 0:
                    log.debug(f"Senergy connectivity check passed: device responded to direct register read")
                    return True
            except Exception as e:
                log.debug(f"Senergy connectivity check via direct register failed: {e}")
            
            return False
        except Exception as e:
            log.debug(f"Senergy connectivity check failed: {e}")
            return False
    
    async def read_serial_number(self) -> Optional[str]:
        """Read device serial number for identification."""
        try:
            if not self.client or not self.client.connected:
                await self.connect()
            
            # Try to read serial number from register map
            try:
                serial = await self.read_by_ident("device_serial_number")
                if serial and isinstance(serial, str):
                    # Clean up serial number (remove nulls, spaces)
                    serial = serial.strip().replace('\x00', '').strip()
                    if serial:
                        log.debug(f"Read serial number from Senergy device: {serial}")
                        return serial
            except Exception as e:
                log.debug(f"Could not read serial via register map: {e}")
            
            # Fallback: try direct register read (address 6672, size 8)
            try:
                regs = await self._read_holding_regs(6672, 8)
                if regs:
                    serial = _regs_to_ascii(regs, byteorder="big")
                    serial = serial.strip().replace('\x00', '').strip()
                    if serial:
                        log.debug(f"Read serial number via direct register: {serial}")
                        return serial
            except Exception as e:
                log.debug(f"Could not read serial via direct register: {e}")
            
            return None
        except Exception as e:
            log.warning(f"Error reading serial number from Senergy device: {e}")
            return None