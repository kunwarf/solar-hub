"""
Regression tests for the TCPConnection.close() CLOSE-WAIT fix.

Production evidence (faisal-home `ss` output):

    LAST-ACK   ... timer:(on,5.976sec,6)
    LAST-ACK   ... timer:(on,1min15sec,7)
    CLOSE-WAIT ... users:(("python",pid=2669959,fd=25))

CLOSE-WAIT means the peer (ESP32) sent FIN cleanly, our kernel received
it, but the application never called close() on the socket.  The FD leaks
AND the `_by_serial` slot is held so an ESP32 reconnect can't re-register
under the same serial until the OS eventually cleans up (which can be
minutes).  This alone widens the "device missing from Redis" window every
time a device disconnects.

Root cause: `close()` used to short-circuit when `_state == DISCONNECTED`,
and the read paths (`read`, `read_until`) SET that state to DISCONNECTED
on `IncompleteReadError` (peer FIN).  So by the time the cleanup path
called `connection.close()`, we returned early without ever calling
`writer.close()`.  Fix: always close the writer, guarded by an idempotent
`_writer_closed` flag.
"""
from unittest.mock import AsyncMock, MagicMock

import asyncio
import pytest

from system_b.device_server.connection.tcp_connection import (
    ConnectionState,
    TCPConnection,
)


def _make_conn():
    """Build a TCPConnection wrapping mocked reader/writer."""
    reader = MagicMock(spec=asyncio.StreamReader)
    writer = MagicMock(spec=asyncio.StreamWriter)
    writer.get_extra_info.return_value = None
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return TCPConnection(reader=reader, writer=writer), writer


class TestCloseAfterPeerFin:
    """
    The critical case: peer sends FIN, our read path sets state to
    DISCONNECTED via IncompleteReadError, THEN cleanup calls close().
    Prior to the fix the writer was never closed.
    """

    @pytest.mark.asyncio
    async def test_close_still_closes_writer_when_state_already_disconnected(self):
        conn, writer = _make_conn()

        # Simulate the peer-FIN path setting state before close() is called.
        conn._state = ConnectionState.DISCONNECTED

        await conn.close()

        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_is_idempotent(self):
        """Calling close() twice must not double-close the writer."""
        conn, writer = _make_conn()

        await conn.close()
        await conn.close()

        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_normal_close_still_works(self):
        """Regression check: the normal 'peer-still-alive' close path is unchanged."""
        conn, writer = _make_conn()
        assert conn._state == ConnectionState.CONNECTED

        await conn.close()

        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()
        assert conn._state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_writer_exception_does_not_raise(self):
        """
        If writer.close() itself raises (e.g. socket already ripped down at
        kernel level), close() must swallow the exception so cleanup can
        continue in the caller.
        """
        conn, writer = _make_conn()
        writer.wait_closed.side_effect = OSError("kernel already closed us")

        # Must not raise.
        await conn.close()

        writer.close.assert_called_once()
