"""Tests against a real PostgreSQL database.

They are skipped unless TEST_DATABASE_URL is set, for example:

    TEST_DATABASE_URL=postgresql://bagtrack:bagtrack@localhost:5432/bagtrack python -m pytest -q

The tests create the tables if needed. They add the 12 sample bags (the same
ones bag-api adds at startup) and delete every other row they create.
"""

import os
import random
from datetime import datetime, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from bagtrack.main import Settings, create_app
from bagtrack.models import Bag, Scan
from bagtrack.seed import SAMPLE_BAGS, add_sample_bags
from bagtrack.store import PostgresStore

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not set")


@pytest.fixture
def tags():
    """Random BT9xxxxx tags for one test. Their rows are deleted afterwards."""
    used = [f"BT9{random.randint(0, 99_999):05d}" for _ in range(2)]
    yield used
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("DELETE FROM scans WHERE tag = ANY(%s)", [used])
        conn.execute("DELETE FROM bags WHERE tag = ANY(%s)", [used])


def test_api_round_trip_on_postgres(tags):
    with TestClient(create_app(Settings(database_url=DATABASE_URL, seed=False))) as client:
        assert client.get("/readyz").json() == {"status": "ready", "storage": "postgres"}

        body = {"flight": "FL101", "passenger": "Garcia", "destination": "SFO", "tag": tags[0]}
        assert client.post("/api/bags", json=body).status_code == 201
        assert client.post("/api/bags", json=body).status_code == 409

        scanned = client.post(f"/api/bags/{tags[0]}/scans", json={"checkpoint": "security", "scanner": "sc-pg"})
        assert scanned.json()["status"] == "security"
        assert client.post(f"/api/bags/{tags[0]}/scans", json={"checkpoint": "claimed"}).status_code == 409

        history = client.get(f"/api/bags/{tags[0]}/scans").json()
        assert [(scan["checkpoint"], scan["scanner"]) for scan in history] == [
            ("checked_in", "check-in"),
            ("security", "sc-pg"),
        ]
        at_security = client.get("/api/bags", params={"status": "security", "limit": 1000}).json()
        assert tags[0] in [bag["tag"] for bag in at_security]
        assert client.get("/api/stats").json()["by_status"]["security"] >= 1


def test_move_only_succeeds_from_the_expected_checkpoint(tags):
    store = PostgresStore(DATABASE_URL)
    now = datetime.now(timezone.utc)
    bag = Bag(tag=tags[1], flight="FL202", passenger="Okafor", destination="DEN", status="checked_in", updated_at=now)
    assert store.add_bag(bag, [])

    scan = Scan(tag=tags[1], checkpoint="security", scanner="sc-pg", scanned_at=now)
    assert store.move_bag(tags[1], "checked_in", scan).status == "security"
    # A second scanner that still thinks the bag is at checked_in loses.
    assert store.move_bag(tags[1], "checked_in", scan) is None


def test_seed_is_idempotent():
    store = PostgresStore(DATABASE_URL)
    add_sample_bags(store)  # adds the bags, or finds them already there
    assert add_sample_bags(store) == 0
    assert {tag for tag, *_ in SAMPLE_BAGS} <= {bag.tag for bag in store.list_bags()}
