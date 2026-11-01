"""Where bag-api keeps bags and scans.

Two classes have the same methods:

- MemoryStore keeps the data in Python dictionaries. The data is lost when the
  process stops, and every copy of bag-api has its own data.
- PostgresStore keeps the data in PostgreSQL, so every copy of bag-api sees
  the same data.

make_store() picks MemoryStore when DATABASE_URL is empty, PostgresStore otherwise.
"""

import threading
from collections import Counter
from contextlib import contextmanager

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from .models import Bag, Scan

CONNECT_TIMEOUT_SECONDS = 2


class StorageUnavailable(Exception):
    """The database cannot be reached. bag-api answers HTTP 503 when this happens."""


def make_store(database_url: str | None):
    if database_url:
        return PostgresStore(database_url)
    return MemoryStore()


class MemoryStore:
    kind = "memory"

    def __init__(self):
        self._bags: dict[str, Bag] = {}
        self._scans: dict[str, list[Scan]] = {}
        # FastAPI handles requests in several threads at once.
        self._lock = threading.Lock()

    def describe(self) -> str:
        return "memory"

    def ping(self) -> None:
        """Memory is always available."""

    def list_bags(self, flight=None, status=None, limit=None) -> list[Bag]:
        """Return bags, most recently updated first. None means "no filter"."""
        with self._lock:
            bags = [
                bag
                for bag in self._bags.values()
                if (flight is None or bag.flight == flight) and (status is None or bag.status == status)
            ]
        bags.sort(key=lambda bag: (bag.updated_at, bag.tag), reverse=True)
        return bags[:limit]

    def get_bag(self, tag: str) -> Bag | None:
        with self._lock:
            return self._bags.get(tag)

    def add_bag(self, bag: Bag, scans: list[Scan]) -> bool:
        """Store a new bag with its first scans. Return False if the tag is taken."""
        with self._lock:
            if bag.tag in self._bags:
                return False
            self._bags[bag.tag] = bag
            self._scans[bag.tag] = list(scans)
            return True

    def move_bag(self, tag: str, from_status: str, scan: Scan) -> Bag | None:
        """Move the bag to scan.checkpoint if it is still at from_status.

        Return the updated bag, or None if another scan moved it first.
        """
        with self._lock:
            bag = self._bags.get(tag)
            if bag is None or bag.status != from_status:
                return None
            moved = bag.model_copy(update={"status": scan.checkpoint, "updated_at": scan.scanned_at})
            self._bags[tag] = moved
            self._scans[tag].append(scan)
            return moved

    def list_scans(self, tag: str) -> list[Scan]:
        with self._lock:
            return list(self._scans.get(tag, []))

    def count_by_status(self) -> dict[str, int]:
        with self._lock:
            return dict(Counter(bag.status for bag in self._bags.values()))


SCHEMA = """
CREATE TABLE IF NOT EXISTS bags (
    tag         text PRIMARY KEY,
    flight      text NOT NULL,
    passenger   text NOT NULL,
    destination text NOT NULL,
    status      text NOT NULL,
    updated_at  timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag         text NOT NULL REFERENCES bags (tag),
    checkpoint  text NOT NULL,
    scanner     text NOT NULL,
    scanned_at  timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS scans_tag ON scans (tag);
"""

INSERT_SCAN = """
INSERT INTO scans (tag, checkpoint, scanner, scanned_at)
VALUES (%(tag)s, %(checkpoint)s, %(scanner)s, %(scanned_at)s)
"""


class PostgresStore:
    kind = "postgres"

    def __init__(self, url: str):
        self.url = url
        self._schema_ready = False

    def describe(self) -> str:
        """Name the database for the startup log line, without the password."""
        params = conninfo_to_dict(self.url)
        return f"postgres (host {params.get('host', 'localhost')}, database {params.get('dbname', '-')})"

    @contextmanager
    def _transaction(self):
        """Open a connection, run one transaction, close the connection.

        Connection problems become StorageUnavailable. Tables are created on the
        first connection that works, so bag-api can start before the database.
        """
        try:
            with psycopg.connect(self.url, connect_timeout=CONNECT_TIMEOUT_SECONDS, row_factory=dict_row) as conn:
                if not self._schema_ready:
                    # Several bag-api copies may start at the same moment. The advisory
                    # lock makes them create the tables one after the other.
                    conn.execute("SELECT pg_advisory_xact_lock(4242)")
                    conn.execute(SCHEMA)
                    conn.commit()
                    self._schema_ready = True
                yield conn
        except psycopg.OperationalError as err:
            raise StorageUnavailable(" ".join(str(err).split())) from err

    def ping(self) -> None:
        with self._transaction() as conn:
            conn.execute("SELECT 1")

    def list_bags(self, flight=None, status=None, limit=None) -> list[Bag]:
        """Return bags, most recently updated first. None means "no filter"."""
        query = """
            SELECT * FROM bags
            WHERE (%(flight)s::text IS NULL OR flight = %(flight)s)
              AND (%(status)s::text IS NULL OR status = %(status)s)
            ORDER BY updated_at DESC, tag DESC
            LIMIT %(limit)s
        """
        with self._transaction() as conn:
            rows = conn.execute(query, {"flight": flight, "status": status, "limit": limit}).fetchall()
        return [Bag(**row) for row in rows]

    def get_bag(self, tag: str) -> Bag | None:
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM bags WHERE tag = %s", [tag]).fetchone()
        return Bag(**row) if row else None

    def add_bag(self, bag: Bag, scans: list[Scan]) -> bool:
        """Store a new bag with its first scans. Return False if the tag is taken."""
        with self._transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO bags (tag, flight, passenger, destination, status, updated_at)
                VALUES (%(tag)s, %(flight)s, %(passenger)s, %(destination)s, %(status)s, %(updated_at)s)
                ON CONFLICT (tag) DO NOTHING
                """,
                bag.model_dump(),
            )
            if cursor.rowcount == 0:
                return False
            for scan in scans:
                conn.execute(INSERT_SCAN, scan.model_dump())
        return True

    def move_bag(self, tag: str, from_status: str, scan: Scan) -> Bag | None:
        """Move the bag to scan.checkpoint if it is still at from_status.

        Return the updated bag, or None if another scan moved it first.
        """
        with self._transaction() as conn:
            row = conn.execute(
                """
                UPDATE bags SET status = %(checkpoint)s, updated_at = %(scanned_at)s
                WHERE tag = %(tag)s AND status = %(from_status)s
                RETURNING *
                """,
                {**scan.model_dump(), "from_status": from_status},
            ).fetchone()
            if row is None:
                return None
            conn.execute(INSERT_SCAN, scan.model_dump())
        return Bag(**row)

    def list_scans(self, tag: str) -> list[Scan]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT tag, checkpoint, scanner, scanned_at FROM scans WHERE tag = %s ORDER BY id",
                [tag],
            ).fetchall()
        return [Scan(**row) for row in rows]

    def count_by_status(self) -> dict[str, int]:
        with self._transaction() as conn:
            rows = conn.execute("SELECT status, count(*) AS bags FROM bags GROUP BY status").fetchall()
        return {row["status"]: row["bags"] for row in rows}
