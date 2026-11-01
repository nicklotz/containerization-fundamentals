"""Tests for gate-display. Run them on your machine. They do not belong in the image."""

import pytest

from app import app


@pytest.fixture
def client():
    return app.test_client()


def test_health_answers_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "ok\n"


def test_api_lists_gates(client):
    data = client.get("/api/gates").get_json()
    assert data["hub"] == "ORD"
    assert len(data["gates"]) == 6
    assert set(data["gates"][0]) == {"flight", "destination", "gate", "departs", "status"}


def test_page_has_one_row_per_gate(client):
    html = client.get("/").get_data(as_text=True)
    assert "Departure gates at ORD" in html
    assert html.count("<tr>") == 1 + 6  # header row plus one row per gate
