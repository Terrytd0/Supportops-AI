"""Shared pytest fixtures.

TODO: add fixtures for a test database session, test Redis client, and any
authenticated test client variants once auth is implemented.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
