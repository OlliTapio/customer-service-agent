"""
Pytest configuration for integration tests.
"""

import pytest

def pytest_configure(config):
    """Add integration marker to pytest."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test that requires external services"
    )

@pytest.fixture(autouse=True)
def mark_integration_tests(request):
    """Automatically mark all tests in this directory as integration tests."""
    if request.node.get_closest_marker('integration') is None:
        request.node.add_marker(pytest.mark.integration) 