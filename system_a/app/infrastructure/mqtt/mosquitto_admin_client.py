"""
Mosquitto Dynamic Security Plugin admin client.

Uses paho-mqtt to publish management commands to the
$CONTROL/dynamic-security/v1 topic on the HA broker.

All public methods are async (they offload the blocking paho call to
a thread executor so they compose cleanly with FastAPI/asyncio).
"""
import asyncio
import json
import logging
from typing import Optional

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MosquittoAdminClient:
    """
    Thin wrapper around Mosquitto's Dynamic Security Plugin.

    The plugin listens on ``$CONTROL/dynamic-security/v1`` for JSON
    command payloads and responds on ``$CONTROL/dynamic-security/v1/response``.
    We fire-and-forget here because:
    - the broker processes commands synchronously on receive, and
    - we do NOT need the response payload for our use cases.

    If the broker is unreachable the call raises ``ConnectionError`` so
    the service layer can roll back the DB transaction.
    """

    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        admin_username: str,
        admin_password: str,
        *,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._host = broker_host
        self._port = broker_port
        self._username = admin_username
        self._password = admin_password
        self._timeout = timeout_seconds

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def create_user(self, username: str, password: str) -> None:
        """Create a new MQTT user with the default ha_subscriber role."""
        commands = [
            {
                "command": "createClient",
                "username": username,
                "password": password,
            },
            {
                "command": "addClientRole",
                "username": username,
                "rolename": "ha_subscriber",
                "priority": -1,
            },
        ]
        await self._publish_commands(commands)

    async def delete_user(self, username: str) -> None:
        """Delete a MQTT user."""
        await self._publish_commands([{"command": "deleteClient", "username": username}])

    async def update_password(self, username: str, new_password: str) -> None:
        """Change a MQTT user's password."""
        await self._publish_commands(
            [{"command": "modifyClient", "username": username, "password": new_password}]
        )

    async def add_acl_for_user(self, username: str) -> None:
        """
        Grant a user publish/subscribe rights to their personal topic prefix.

        Topic pattern: ``solarhub/ha/<username>/#``
        This is called automatically by ``create_user`` via the ha_subscriber
        role, but kept separate in case we need fine-grained overrides later.
        """
        # The ha_subscriber role is scoped per-user via topic patterns.
        # Individual ACLs are not needed when the role uses {username} substitution.
        # Mosquitto Dynamic Security supports %u substitution in ACL patterns.
        pass  # handled by role definition in dynsec bootstrap

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish_commands_sync(self, commands: list) -> None:
        """Blocking paho publish — runs in a thread executor."""
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.username_pw_set(self._username, self._password)

        connected = False
        error: Optional[Exception] = None

        def on_connect(c, userdata, flags, reason_code, properties):
            nonlocal connected
            if reason_code == 0:
                connected = True
            else:
                nonlocal error
                error = ConnectionError(
                    f"MQTT connect failed with reason code {reason_code}"
                )

        client.on_connect = on_connect

        client.connect(self._host, self._port, keepalive=30)
        client.loop_start()

        deadline = asyncio.get_event_loop  # not used in thread, use time module below
        import time
        start = time.monotonic()
        while not connected and error is None:
            if time.monotonic() - start > self._timeout:
                client.loop_stop()
                client.disconnect()
                raise ConnectionError(
                    f"Timed out connecting to MQTT broker {self._host}:{self._port}"
                )
            time.sleep(0.05)

        if error:
            client.loop_stop()
            raise error

        payload = json.dumps({"commands": commands})
        info = client.publish("$CONTROL/dynamic-security/v1", payload, qos=1)
        info.wait_for_publish(timeout=self._timeout)

        client.loop_stop()
        client.disconnect()

        if not info.is_published():
            raise ConnectionError("MQTT publish to $CONTROL topic did not complete")

        logger.debug(
            "DynSec commands sent to %s:%d: %s", self._host, self._port, commands
        )

    async def _publish_commands(self, commands: list) -> None:
        """Async wrapper — offloads blocking paho work to a thread."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._publish_commands_sync, commands)
