"""
Command-based device identification.

Probes devices using text commands (e.g., Pytes batteries)
or binary commands (e.g., JK-BMS).
"""
import asyncio
import logging
import re
from typing import Optional

from ..connection.tcp_connection import TCPConnection
from ..connection.connection_manager import IdentifiedDevice
from ..protocols.definitions import ProtocolDefinition, ProtocolType

logger = logging.getLogger(__name__)


class CommandProber:
    """
    Command-based device prober.

    Sends identification commands and parses responses to
    identify device type and extract serial numbers.
    """

    def __init__(self, timeout: float = 5.0):
        """
        Initialize the command prober.

        Args:
            timeout: Timeout for command operations.
        """
        self.timeout = timeout

    async def send_text_command(
        self,
        connection: TCPConnection,
        command: str,
        line_ending: str = "\r\n",
        response_timeout: float = 5.0,
        max_response_lines: int = 100,
    ) -> Optional[str]:
        """
        Send a text command and read response.

        Args:
            connection: TCP connection to device.
            command: Command string to send.
            line_ending: Line ending to use.
            response_timeout: Timeout for response.
            max_response_lines: Maximum lines to read.

        Returns:
            Response string, or None on error.
        """
        try:
            # Send command
            cmd_bytes = (command + line_ending).encode("utf-8")
            await connection.write(cmd_bytes, timeout=self.timeout)

            # Read response
            # First try to read until we get a complete response
            response_lines = []
            end_time = asyncio.get_event_loop().time() + response_timeout

            while asyncio.get_event_loop().time() < end_time:
                try:
                    remaining = max(
                        0.1, end_time - asyncio.get_event_loop().time()
                    )
                    line = await connection.read_until(
                        line_ending.encode("utf-8"),
                        timeout=remaining,
                    )
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded:
                        response_lines.append(decoded)

                    # Stop if we've received enough
                    if len(response_lines) >= max_response_lines:
                        break

                    # Check for end of response markers
                    if decoded.startswith(">") or decoded == "":
                        break

                except asyncio.TimeoutError:
                    # Timeout means no more data
                    break
                except Exception:
                    break

            return "\n".join(response_lines) if response_lines else None

        except asyncio.TimeoutError:
            logger.debug(f"Timeout sending command: {command}")
            return None
        except Exception as e:
            logger.debug(f"Error sending command: {e}")
            return None

    async def send_binary_command(
        self,
        connection: TCPConnection,
        command: bytes,
        expected_response_length: int = 0,
        response_timeout: float = 5.0,
    ) -> Optional[bytes]:
        """
        Send a binary command and read response.

        Args:
            connection: TCP connection to device.
            command: Command bytes to send.
            expected_response_length: Expected response length (0 = read available).
            response_timeout: Timeout for response.

        Returns:
            Response bytes, or None on error.
        """
        try:
            # Send command
            await connection.write(command, timeout=self.timeout)

            # Read response
            if expected_response_length > 0:
                response = await connection.read(
                    expected_response_length,
                    timeout=response_timeout,
                )
            else:
                # Read whatever is available
                response = await connection.read_available(
                    max_bytes=4096,
                    timeout=response_timeout,
                )

            return response if response else None

        except asyncio.TimeoutError:
            logger.debug("Timeout sending binary command")
            return None
        except Exception as e:
            logger.debug(f"Error sending binary command: {e}")
            return None

    async def probe_pytes(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
    ) -> Optional[IdentifiedDevice]:
        """
        Probe for Pytes battery.

        Args:
            connection: TCP connection to probe.
            protocol: Protocol definition.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        ident_config = protocol.identification
        command_config = protocol.command

        # Send identification command
        command = ident_config.command or "info"
        line_ending = command_config.line_ending if command_config else "\r\n"

        response = await self.send_text_command(
            connection,
            command,
            line_ending=line_ending,
            response_timeout=ident_config.timeout,
        )

        if not response:
            return None

        # Check for expected response
        expected = ident_config.expected_response
        if expected and expected.lower() not in response.lower():
            logger.debug(
                f"Pytes: expected '{expected}' not found in response"
            )
            return None

        logger.info(f"Identified Pytes battery on {connection.remote_addr}")

        # Try to read serial number
        serial_number = None
        serial_config = protocol.serial_number

        if serial_config.command:
            sn_response = await self.send_text_command(
                connection,
                serial_config.command,
                line_ending=line_ending,
            )

            if sn_response and serial_config.parse_regex:
                match = re.search(serial_config.parse_regex, sn_response)
                if match:
                    serial_number = match.group(1)

        if not serial_number:
            # Generate fallback
            serial_number = f"pytes_{connection.remote_ip}_{connection.remote_port}"

        return IdentifiedDevice(
            protocol_id=protocol.protocol_id,
            serial_number=serial_number,
            device_type=protocol.device_type.value,
            model="Pytes Battery",
            manufacturer="Pytes",
            extra_data={"info_response": response[:200]},
        )

    async def probe_jkbms(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
    ) -> Optional[IdentifiedDevice]:
        """
        Probe for JK-BMS.

        Args:
            connection: TCP connection to probe.
            protocol: Protocol definition.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        ident_config = protocol.identification

        # JK-BMS uses binary protocol
        # Request header: 4E 57 (NW)
        command = ident_config.command
        if isinstance(command, str):
            if command.startswith("\\x"):
                # Parse escaped bytes
                command = bytes.fromhex(command.replace("\\x", ""))
            else:
                command = command.encode("utf-8")

        # Send request and read response
        response = await self.send_binary_command(
            connection,
            command,
            expected_response_length=0,  # Read available
            response_timeout=ident_config.timeout,
        )

        if not response:
            return None

        # Check for JK-BMS response header
        if len(response) < 2:
            return None

        if response[0:2] != b"\x4E\x57":  # "NW"
            logger.debug(f"JK-BMS: invalid response header: {response[:4].hex()}")
            return None

        logger.info(f"Identified JK-BMS on {connection.remote_addr}")

        # Extract serial from response if possible
        serial_number = f"jkbms_{connection.remote_ip}_{connection.remote_port}"

        return IdentifiedDevice(
            protocol_id=protocol.protocol_id,
            serial_number=serial_number,
            device_type=protocol.device_type.value,
            model="JK-BMS",
            manufacturer="JK",
            extra_data={"response_header": response[:10].hex()},
        )

    async def probe(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
    ) -> Optional[IdentifiedDevice]:
        """
        Probe a connection using a command-based protocol.

        Args:
            connection: TCP connection to probe.
            protocol: Protocol definition to try.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        if protocol.protocol_type != ProtocolType.COMMAND:
            return None

        logger.debug(f"Probing for {protocol.protocol_id} (command-based)")

        # Use protocol-specific probing
        if "pytes" in protocol.protocol_id.lower():
            return await self.probe_pytes(connection, protocol)
        elif "jkbms" in protocol.protocol_id.lower():
            return await self.probe_jkbms(connection, protocol)
        else:
            # Generic command probe
            return await self._generic_probe(connection, protocol)

    async def _generic_probe(
        self,
        connection: TCPConnection,
        protocol: ProtocolDefinition,
    ) -> Optional[IdentifiedDevice]:
        """
        Generic command-based probe.

        Args:
            connection: TCP connection.
            protocol: Protocol definition.

        Returns:
            IdentifiedDevice if successful, None otherwise.
        """
        ident_config = protocol.identification
        command_config = protocol.command

        if not ident_config.command:
            logger.debug(f"{protocol.protocol_id}: no identification command")
            return None

        line_ending = command_config.line_ending if command_config else "\r\n"

        # Determine if binary or text
        command = ident_config.command
        if command.startswith("\\x") or all(
            c in "0123456789abcdefABCDEF" for c in command.replace(" ", "")
        ):
            # Binary command
            if command.startswith("\\x"):
                cmd_bytes = bytes.fromhex(command.replace("\\x", ""))
            else:
                cmd_bytes = bytes.fromhex(command.replace(" ", ""))

            response = await self.send_binary_command(
                connection,
                cmd_bytes,
                response_timeout=ident_config.timeout,
            )

            if not response:
                return None

            # Check expected response
            if ident_config.expected_response:
                expected = ident_config.expected_response
                if expected.startswith("\\x"):
                    expected_bytes = bytes.fromhex(expected.replace("\\x", ""))
                else:
                    expected_bytes = expected.encode("utf-8")

                if not response.startswith(expected_bytes):
                    return None

        else:
            # Text command
            response = await self.send_text_command(
                connection,
                command,
                line_ending=line_ending,
                response_timeout=ident_config.timeout,
            )

            if not response:
                return None

            if ident_config.expected_response:
                if ident_config.expected_response.lower() not in response.lower():
                    return None

        logger.info(f"Identified {protocol.protocol_id}")

        # Generate serial number
        serial_number = f"{protocol.protocol_id}_{connection.remote_ip}_{connection.remote_port}"

        return IdentifiedDevice(
            protocol_id=protocol.protocol_id,
            serial_number=serial_number,
            device_type=protocol.device_type.value,
            model=protocol.name,
            manufacturer=protocol.manufacturer,
        )
