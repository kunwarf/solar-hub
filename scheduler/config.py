"""
Scheduler service configuration.

Imports System A's settings directly since the service runs in the same virtualenv
and PYTHONPATH is set to include system_a/ by the systemd unit file.
"""
from app.config import get_settings

settings = get_settings()

__all__ = ["settings"]
