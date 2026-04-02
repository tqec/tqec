import pytest

SLOW_TEST_TIMEOUT = 300


def pytest_collection_modifyitems(items):
    """Increase timeouts for tests marked as slow."""
    for item in items:
        marker = item.get_closest_marker("slow")
        if marker:
            item.add_marker(pytest.mark.timeout(SLOW_TEST_TIMEOUT))
