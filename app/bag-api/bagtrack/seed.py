"""Sample bags for a new BagTrack system.

bag-api adds them at startup when its store is empty and SEED is true.
You can also run this module to fill the database that DATABASE_URL points at:

    python -m bagtrack.seed

Bags whose tag already exists are skipped, so running it twice is safe.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from .checkpoints import CHECKPOINTS
from .models import Bag, Scan
from .store import PostgresStore, StorageUnavailable

# tag, flight, passenger, destination, checkpoint the bag has reached
SAMPLE_BAGS = [
    ("BT100001", "FL101", "Garcia", "SFO", "claimed"),
    ("BT100002", "FL101", "Okafor", "SFO", "unloaded"),
    ("BT100003", "FL101", "Nguyen", "SFO", "loaded"),
    ("BT100004", "FL202", "Schmidt", "DEN", "loaded"),
    ("BT100005", "FL202", "Rossi", "DEN", "sorted"),
    ("BT100006", "FL202", "Kowalski", "DEN", "sorted"),
    ("BT100007", "FL303", "Haddad", "BOS", "security"),
    ("BT100008", "FL303", "Tanaka", "BOS", "sorted"),
    ("BT100009", "FL303", "Silva", "BOS", "checked_in"),
    ("BT100010", "FL404", "Novak", "MIA", "security"),
    ("BT100011", "FL404", "Dubois", "MIA", "checked_in"),
    ("BT100012", "FL404", "Larsen", "MIA", "claimed"),
]


def sample_bags(now: datetime) -> list[tuple[Bag, list[Scan]]]:
    """Build each sample bag with the scans that brought it to its checkpoint.

    Scans are five minutes apart. The last scan of the first bag is one minute
    before `now`, and every following bag is one minute older.
    """
    result = []
    for number, (tag, flight, passenger, destination, status) in enumerate(SAMPLE_BAGS, start=1):
        passed = CHECKPOINTS[: CHECKPOINTS.index(status) + 1]
        last_scan = now - timedelta(minutes=number)
        scans = [
            Scan(
                tag=tag,
                checkpoint=checkpoint,
                scanner="seed",
                scanned_at=last_scan - timedelta(minutes=5 * (len(passed) - 1 - step)),
            )
            for step, checkpoint in enumerate(passed)
        ]
        bag = Bag(
            tag=tag,
            flight=flight,
            passenger=passenger,
            destination=destination,
            status=status,
            updated_at=last_scan,
        )
        result.append((bag, scans))
    return result


def add_sample_bags(store) -> int:
    """Add the sample bags that the store does not have yet. Return how many were added."""
    added = 0
    for bag, scans in sample_bags(datetime.now(timezone.utc)):
        if store.add_bag(bag, scans):
            added += 1
    return added


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set. Set it to the PostgreSQL database to fill.", file=sys.stderr)
        return 1
    try:
        added = add_sample_bags(PostgresStore(url))
    except StorageUnavailable as err:
        print(f"Cannot reach the database: {err}", file=sys.stderr)
        return 1
    print(f"Added {added} of {len(SAMPLE_BAGS)} sample bags.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
