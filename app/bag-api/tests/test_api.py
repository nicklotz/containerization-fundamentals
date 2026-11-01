"""API tests against the in-memory store."""

import re

from fastapi.testclient import TestClient

from bagtrack.main import Settings, create_app


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_readyz_with_memory_store(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "storage": "memory"}


def test_info(client):
    info = client.get("/api/info").json()
    assert info["service"] == "bag-api"
    assert info["version"] == "test"
    assert info["hub"] == "ORD"
    assert info["storage"] == "memory"
    assert info["hostname"]


def test_index_points_to_docs(client):
    body = client.get("/").json()
    assert body["docs"] == "/docs"
    assert body["bags"] == "/api/bags"


def test_check_in_generates_a_tag(new_bag):
    assert re.fullmatch(r"BT\d{6}", new_bag["tag"])
    assert new_bag["status"] == "checked_in"
    assert new_bag["flight"] == "FL101"


def test_check_in_cleans_up_codes(client):
    response = client.post(
        "/api/bags", json={"flight": "fl202", "passenger": " Okafor ", "destination": "den", "tag": "bt200001"}
    )
    assert response.status_code == 201
    bag = response.json()
    assert (bag["tag"], bag["flight"], bag["passenger"], bag["destination"]) == ("BT200001", "FL202", "Okafor", "DEN")


def test_duplicate_tag_is_refused(client):
    body = {"flight": "FL101", "passenger": "Garcia", "destination": "SFO", "tag": "BT200002"}
    assert client.post("/api/bags", json=body).status_code == 201
    response = client.post("/api/bags", json=body)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_invalid_bag_is_refused(client):
    response = client.post("/api/bags", json={"flight": "FL101", "passenger": "Garcia", "destination": "Chicago"})
    assert response.status_code == 422


def test_get_bag(client, new_bag):
    assert client.get(f"/api/bags/{new_bag['tag']}").json() == new_bag


def test_unknown_bag_is_404(client):
    assert client.get("/api/bags/BT999999").status_code == 404
    response = client.post("/api/bags/BT999999/scans", json={"checkpoint": "security"})
    assert response.status_code == 404


def test_list_is_newest_first_and_filters(client):
    for flight, tag in [("FL101", "BT300001"), ("FL202", "BT300002"), ("FL101", "BT300003")]:
        client.post("/api/bags", json={"flight": flight, "passenger": "Rossi", "destination": "SFO", "tag": tag})
    client.post("/api/bags/BT300001/scans", json={"checkpoint": "security"})

    tags = [bag["tag"] for bag in client.get("/api/bags").json()]
    assert tags == ["BT300001", "BT300003", "BT300002"]  # BT300001 was scanned last

    fl101 = client.get("/api/bags", params={"flight": "fl101"}).json()
    assert {bag["tag"] for bag in fl101} == {"BT300001", "BT300003"}

    at_security = client.get("/api/bags", params={"status": "security"}).json()
    assert [bag["tag"] for bag in at_security] == ["BT300001"]

    assert len(client.get("/api/bags", params={"limit": 2}).json()) == 2


def test_scan_moves_bag_to_next_checkpoint(client, new_bag):
    tag = new_bag["tag"]
    response = client.post(f"/api/bags/{tag}/scans", json={"checkpoint": "security", "scanner": "sc-test"})
    assert response.status_code == 200
    assert response.json()["status"] == "security"

    history = client.get(f"/api/bags/{tag}/scans").json()
    assert [(scan["checkpoint"], scan["scanner"]) for scan in history] == [
        ("checked_in", "check-in"),
        ("security", "sc-test"),
    ]


def test_skipping_a_checkpoint_is_409(client, new_bag):
    response = client.post(f"/api/bags/{new_bag['tag']}/scans", json={"checkpoint": "loaded"})
    assert response.status_code == 409
    assert response.json()["detail"] == (
        f"Bag {new_bag['tag']} cannot move from 'checked_in' to 'loaded'. The next checkpoint is 'security'"
    )


def test_unknown_checkpoint_is_422(client, new_bag):
    response = client.post(f"/api/bags/{new_bag['tag']}/scans", json={"checkpoint": "lost"})
    assert response.status_code == 422


def test_full_journey_then_no_more_scans(client, new_bag):
    tag = new_bag["tag"]
    for checkpoint in ["security", "sorted", "loaded", "unloaded", "claimed"]:
        assert client.post(f"/api/bags/{tag}/scans", json={"checkpoint": checkpoint}).status_code == 200
    response = client.post(f"/api/bags/{tag}/scans", json={"checkpoint": "claimed"})
    assert response.status_code == 409
    assert "last checkpoint" in response.json()["detail"]


def test_stats_lists_every_checkpoint(client, new_bag):
    client.post(f"/api/bags/{new_bag['tag']}/scans", json={"checkpoint": "security"})
    client.post("/api/bags", json={"flight": "FL202", "passenger": "Haddad", "destination": "DEN"})
    assert client.get("/api/stats").json() == {
        "total": 2,
        "by_status": {"checked_in": 1, "security": 1, "sorted": 0, "loaded": 0, "unloaded": 0, "claimed": 0},
    }


def test_seed_adds_sample_bags_once():
    app = create_app(Settings(database_url=None, seed=True))
    with TestClient(app) as client:
        bags = client.get("/api/bags").json()
        assert len(bags) == 12
        assert len({bag["flight"] for bag in bags}) == 4
        assert len({bag["status"] for bag in bags}) >= 5
        # A seeded bag has a scan for every checkpoint it passed.
        loaded = client.get("/api/bags/BT100003/scans").json()
        assert [scan["checkpoint"] for scan in loaded] == ["checked_in", "security", "sorted", "loaded"]


def test_app_starts_while_database_is_down():
    # Nothing listens on port 1, so every connection attempt fails at once.
    settings = Settings(database_url="postgresql://bagtrack:secret@127.0.0.1:1/bagtrack", seed=True)
    with TestClient(create_app(settings)) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/info").json()["storage"] == "postgres"

        ready = client.get("/readyz")
        assert ready.status_code == 503
        assert ready.json()["status"] == "not ready"

        response = client.get("/api/bags")
        assert response.status_code == 503
        assert response.json()["detail"].startswith("Database unavailable")
