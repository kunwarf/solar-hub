"""
Unit test configuration.

Auto-marks all tests in this directory as unit tests.
"""
import pytest


def pytest_collection_modifyitems(items):
    """Auto-mark all tests in the unit directory."""
    for item in items:
        if "/unit/" in str(item.fspath) or "\\unit\\" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
