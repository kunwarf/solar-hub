"""
Protocol configuration loader.

Loads protocol definitions from YAML configuration files.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .definitions import (
    CommandConfig,
    DeviceType,
    IdentificationConfig,
    ModbusConfig,
    PollingConfig,
    ProtocolDefinition,
    ProtocolType,
    SerialNumberConfig,
)

logger = logging.getLogger(__name__)


class ProtocolLoader:
    """
    Loads protocol definitions from YAML configuration files.

    Provides methods to parse and validate protocol configurations,
    converting them into ProtocolDefinition objects.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the protocol loader.

        Args:
            config_dir: Directory containing protocol YAML files.
                       Defaults to system_b/config if not specified.
        """
        if config_dir is None:
            # Default to system_b/config relative to this file
            self.config_dir = Path(__file__).parent.parent.parent / "config"
        else:
            self.config_dir = Path(config_dir)

    def load_from_file(self, file_path: Path) -> List[ProtocolDefinition]:
        """
        Load protocols from a single YAML file.

        Args:
            file_path: Path to the YAML configuration file.

        Returns:
            List of ProtocolDefinition objects.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            yaml.YAMLError: If the file contains invalid YAML.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Protocol config file not found: {file_path}")

        logger.info(f"Loading protocols from {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning(f"Empty protocol config file: {file_path}")
            return []

        protocols_data = data.get("protocols", [])
        if not protocols_data:
            logger.warning(f"No protocols defined in {file_path}")
            return []

        protocols = []
        for proto_data in protocols_data:
            try:
                protocol = self._parse_protocol(proto_data)
                protocols.append(protocol)
                logger.debug(
                    f"Loaded protocol: {protocol.protocol_id} "
                    f"({protocol.device_type.value})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to parse protocol {proto_data.get('id', 'unknown')}: {e}"
                )
                continue

        logger.info(f"Loaded {len(protocols)} protocols from {file_path}")
        return protocols

    def load_all(self) -> List[ProtocolDefinition]:
        """
        Load all protocol definitions from config directory.

        Loads protocols.yaml and any additional YAML files in the directory.

        Returns:
            List of all ProtocolDefinition objects.
        """
        all_protocols = []

        # Load main protocols.yaml first
        main_config = self.config_dir / "protocols.yaml"
        if main_config.exists():
            try:
                protocols = self.load_from_file(main_config)
                all_protocols.extend(protocols)
            except Exception as e:
                logger.error(f"Failed to load main protocols config: {e}")

        # Load any additional protocol files (protocols_*.yaml)
        for config_file in self.config_dir.glob("protocols_*.yaml"):
            try:
                protocols = self.load_from_file(config_file)
                all_protocols.extend(protocols)
            except Exception as e:
                logger.error(f"Failed to load {config_file}: {e}")

        logger.info(f"Loaded {len(all_protocols)} protocols total")
        return all_protocols

    def _parse_protocol(self, data: Dict[str, Any]) -> ProtocolDefinition:
        """
        Parse a protocol definition from dictionary data.

        Args:
            data: Dictionary containing protocol configuration.

        Returns:
            ProtocolDefinition object.

        Raises:
            ValueError: If required fields are missing.
        """
        # Required fields
        protocol_id = data.get("id")
        if not protocol_id:
            raise ValueError("Protocol 'id' is required")

        name = data.get("name", protocol_id)
        device_type = self._parse_device_type(data.get("device_type", "unknown"))
        protocol_type = self._parse_protocol_type(data)

        # Parse sub-configurations
        identification = self._parse_identification(data.get("identification", {}))
        serial_number = self._parse_serial_number(data.get("serial_number", {}))
        polling = self._parse_polling(data.get("polling", {}))
        modbus = self._parse_modbus(data.get("modbus", {}))
        command = self._parse_command(data.get("command", {}))

        return ProtocolDefinition(
            protocol_id=protocol_id,
            name=name,
            device_type=device_type,
            protocol_type=protocol_type,
            priority=data.get("priority", 100),
            register_map_file=data.get("register_map"),
            identification=identification,
            serial_number=serial_number,
            polling=polling,
            modbus=modbus if protocol_type in (
                ProtocolType.MODBUS_TCP, ProtocolType.MODBUS_RTU
            ) else None,
            command=command if protocol_type == ProtocolType.COMMAND else None,
            adapter_class=data.get("adapter_class"),
            manufacturer=data.get("manufacturer"),
            model_pattern=data.get("model_pattern"),
            description=data.get("description"),
        )

    def _parse_device_type(self, value: str) -> DeviceType:
        """Parse device type from string."""
        try:
            return DeviceType(value.lower())
        except ValueError:
            logger.warning(f"Unknown device type: {value}, defaulting to 'unknown'")
            return DeviceType.UNKNOWN

    def _parse_protocol_type(self, data: Dict[str, Any]) -> ProtocolType:
        """Determine protocol type from configuration."""
        # Explicit protocol_type field
        if "protocol_type" in data:
            try:
                return ProtocolType(data["protocol_type"].lower())
            except ValueError:
                pass

        # Infer from other fields
        if data.get("command_based", False):
            return ProtocolType.COMMAND
        if data.get("ble", False):
            return ProtocolType.BLE

        # Check identification config
        ident = data.get("identification", {})
        if ident.get("command"):
            return ProtocolType.COMMAND

        # Default to Modbus TCP for data logger connections
        return ProtocolType.MODBUS_TCP

    def _parse_identification(self, data: Dict[str, Any]) -> IdentificationConfig:
        """Parse identification configuration."""
        return IdentificationConfig(
            register=data.get("register"),
            size=data.get("size", 1),
            expected_values=data.get("expected_values", []),
            command=data.get("command"),
            expected_response=data.get("expected_response"),
            timeout=data.get("timeout", 5.0),
        )

    def _parse_serial_number(self, data: Dict[str, Any]) -> SerialNumberConfig:
        """Parse serial number configuration."""
        return SerialNumberConfig(
            register=data.get("register"),
            size=data.get("size", 8),
            encoding=data.get("encoding", "ascii"),
            command=data.get("command"),
            parse_regex=data.get("parse_regex"),
        )

    def _parse_polling(self, data: Dict[str, Any]) -> PollingConfig:
        """Parse polling configuration."""
        return PollingConfig(
            default_interval=data.get("default_interval", 10),
            min_interval=data.get("min_interval", 5),
            max_interval=data.get("max_interval", 300),
            timeout=data.get("timeout", 5.0),
            max_consecutive_failures=data.get("max_consecutive_failures", 5),
            retry_delay=data.get("retry_delay", 1.0),
        )

    def _parse_modbus(self, data: Dict[str, Any]) -> ModbusConfig:
        """Parse Modbus configuration."""
        return ModbusConfig(
            unit_id=data.get("unit_id", 1),
            timeout=data.get("timeout", 5.0),
            retries=data.get("retries", 3),
            retry_delay=data.get("retry_delay", 0.5),
            baudrate=data.get("baudrate", 9600),
            parity=data.get("parity", "N"),
            stopbits=data.get("stopbits", 1),
            bytesize=data.get("bytesize", 8),
        )

    def _parse_command(self, data: Dict[str, Any]) -> CommandConfig:
        """Parse command protocol configuration."""
        return CommandConfig(
            line_ending=data.get("line_ending", "\r\n"),
            response_timeout=data.get("response_timeout", 5.0),
            command_delay=data.get("command_delay", 0.1),
        )
