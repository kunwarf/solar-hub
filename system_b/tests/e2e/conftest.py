"""
Pytest configuration for end-to-end tests.

Automatically marks all tests in this directory as e2e tests.
"""
import pytest


def pytest_collection_modifyitems(config, items):
    """Automatically mark all tests in this directory as e2e tests."""
    for item in items:
        # Check if test is in the e2e directory
        test_path = str(item.path)
        if 'tests/e2e' in test_path or test_path.endswith('tests\\e2e'):
            # Only mark items that don't already have a marker
            if not any(mark.name in ('unit', 'integration', 'e2e') for mark in item.iter_markers()):
                item.add_marker(pytest.mark.e2e)
