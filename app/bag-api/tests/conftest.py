import pytest
from fastapi.testclient import TestClient

from bagtrack.main import Settings, create_app


@pytest.fixture
def client():
    """A test client for bag-api with an empty in-memory store."""
    app = create_app(Settings(database_url=None, hub="ORD", version="test", seed=False))
    with TestClient(app) as test_client:  # "with" runs the startup code
        yield test_client


@pytest.fixture
def new_bag(client):
    """Check in one bag and return it."""
    response = client.post("/api/bags", json={"flight": "FL101", "passenger": "Garcia", "destination": "SFO"})
    assert response.status_code == 201
    return response.json()
