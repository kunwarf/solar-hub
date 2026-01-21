"""
Pytest configuration for integration tests.

Automatically marks all tests in this directory as integration tests.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """Automatically mark all tests in this directory as integration tests."""
    for item in items:
        # Check if test is in the integration directory
        test_path = str(item.path)
        if 'tests/integration' in test_path or test_path.endswith('tests\\integration'):
            # Only mark items that don't already have a marker
            if not any(mark.name in ('unit', 'integration', 'e2e') for mark in item.iter_markers()):
                item.add_marker(pytest.mark.integration)
