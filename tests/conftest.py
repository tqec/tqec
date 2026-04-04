import pytest

SLOW_TEST_TIMEOUT = 300


def pytest_collection_modifyitems(items):
    """Increase timeouts for tests marked as slow."""
    for item in items:
        if item.get_closest_marker("slow"):
            item.add_marker(pytest.mark.timeout(SLOW_TEST_TIMEOUT))
