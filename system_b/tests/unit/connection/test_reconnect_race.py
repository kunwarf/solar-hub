"""
Regression tests for the connection_manager reconnect-race fix.

Production evidence (faisal-home): 5 of 7 ESP32 dataloggers reconnect
every ~2 minutes.  With the old cleanup path, if the new socket arrived
before the old socket's cleanup finished, both would run — the new one
re-armed the device_state, then the old one's cleanup called
`remove_device` and tore it down.  The next poll loop cycle ran on a
missing device_state and exited immediately, producing a several-second
Redis blackout on every reconnect.

The fix: `_cleanup_connection` guards `remove_device` behind an "am I
still the owning connection for this serial?" check.  If a newer
connection has taken over `_by_serial[serial]`, our cleanup is a no-op
on the device_state.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from system_b.device_server.connection.connection_manager import (
    ConnectionManager,
)


def _make_connection(serial: str = "SH01TEST00000001"):
    """Build a minimal fake TCPConnection just for the fields the cleanup uses."""
    conn = MagicMock()
    conn.connection_id = uuid4()
    conn.serial_number = serial
    conn.device_id = uuid4()
    conn.is_connected = False
    conn.close = AsyncMock()
    return conn


def _make_manager():
    """Build a ConnectionManager wired to fake prober + device_manager."""
    prober = MagicMock()
    device_manager = MagicMock()
    device_manager.remove_device = AsyncMock()
    return ConnectionManager(prober=prober, device_manager=device_manager)


class TestReconnectRace:
    @pytest.mark.asyncio
    async def test_cleanup_of_superseded_connection_does_not_remove_device(self):
        """
        Old socket dies AFTER a new socket has re-registered under the same
        serial.  The old socket's cleanup must NOT call remove_device.
        """
        manager = _make_manager()

        old_conn = _make_connection()
        new_conn = _make_connection()
        assert old_conn.serial_number == new_conn.serial_number

        # Both connections were seen by the manager at some point.
        manager._connections[old_conn.connection_id] = old_conn
        manager._connections[new_conn.connection_id] = new_conn

        # The new connection is the current owner of this serial.
        manager._by_serial[old_conn.serial_number] = new_conn.connection_id
        manager._by_device_id[old_conn.device_id] = old_conn.connection_id
        manager._by_device_id[new_conn.device_id] = new_conn.connection_id

        # Now the old socket finishes closing and its cleanup runs.
        await manager._cleanup_connection(old_conn)

        # Device_state must NOT have been torn down — the new connection
        # owns it.
        manager.device_manager.remove_device.assert_not_awaited()

        # The new connection's ownership entries must still be intact.
        assert manager._by_serial.get(new_conn.serial_number) == new_conn.connection_id
        assert new_conn.device_id in manager._by_device_id
        assert old_conn.device_id not in manager._by_device_id

    @pytest.mark.asyncio
    async def test_cleanup_of_still_owning_connection_does_remove_device(self):
        """
        Regular case: connection dies without a replacement in-flight.
        remove_device still fires — no functional regression.
        """
        manager = _make_manager()
        conn = _make_connection()

        manager._connections[conn.connection_id] = conn
        manager._by_serial[conn.serial_number] = conn.connection_id
        manager._by_device_id[conn.device_id] = conn.connection_id

        await manager._cleanup_connection(conn)

        manager.device_manager.remove_device.assert_awaited_once_with(conn.device_id)
        assert conn.serial_number not in manager._by_serial
        assert conn.device_id not in manager._by_device_id

    @pytest.mark.asyncio
    async def test_cleanup_of_unidentified_connection_is_noop(self):
        """
        A connection that never got past identification has no serial and
        no device_id — cleanup should not touch the device_manager.
        """
        manager = _make_manager()
        conn = MagicMock()
        conn.connection_id = uuid4()
        conn.serial_number = None
        conn.device_id = None
        conn.is_connected = False
        conn.close = AsyncMock()

        manager._connections[conn.connection_id] = conn

        await manager._cleanup_connection(conn)

        manager.device_manager.remove_device.assert_not_awaited()


class TestTcpKeepalive:
    """
    _apply_tcp_keepalive should set SO_KEEPALIVE on every socket it can
    reach, and set the Linux tunables when available.  Missing constants
    (e.g. on Windows) must be silently skipped, not raise.
    """

    def test_sets_so_keepalive_and_tunables_when_available(self):
        import socket

        from system_b.device_server.connection.tcp_server import (
            _apply_tcp_keepalive,
        )

        writer = MagicMock()
        fake_sock = MagicMock()
        writer.get_extra_info.return_value = fake_sock

        _apply_tcp_keepalive(writer)

        # SO_KEEPALIVE flag
        fake_sock.setsockopt.assert_any_call(
            socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1
        )
        # Linux tunables — only asserted when present on this platform.
        for name, value in (
            ("TCP_KEEPIDLE", 30),
            ("TCP_KEEPINTVL", 15),
            ("TCP_KEEPCNT", 3),
        ):
            opt = getattr(socket, name, None)
            if opt is not None:
                fake_sock.setsockopt.assert_any_call(
                    socket.IPPROTO_TCP, opt, value
                )

    def test_missing_socket_is_silently_ignored(self):
        from system_b.device_server.connection.tcp_server import (
            _apply_tcp_keepalive,
        )
        writer = MagicMock()
        writer.get_extra_info.return_value = None
        _apply_tcp_keepalive(writer)   # must not raise

    def test_setsockopt_failure_does_not_raise(self):
        from system_b.device_server.connection.tcp_server import (
            _apply_tcp_keepalive,
        )
        writer = MagicMock()
        fake_sock = MagicMock()
        fake_sock.setsockopt.side_effect = OSError("nope")
        writer.get_extra_info.return_value = fake_sock
        _apply_tcp_keepalive(writer)   # must not raise
