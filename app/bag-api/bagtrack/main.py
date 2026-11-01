"""bag-api: the HTTP API of BagTrack.

Start it with:

    uvicorn bagtrack.main:app --host 0.0.0.0 --port 8000

Settings come from environment variables. See Settings.from_env() below.
"""

import logging
import os
import random
import socket
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .checkpoints import CHECKPOINTS, Checkpoint, IllegalMove, check_move
from .models import Bag, NewBag, NewScan, Scan, Stats
from .seed import add_sample_bags
from .store import StorageUnavailable, make_store

# uvicorn sets up its own loggers. This sets up the "bagtrack" logger.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
log = logging.getLogger("bagtrack")


@dataclass(frozen=True)
class Settings:
    database_url: str | None = None  # None keeps the data in memory
    hub: str = "ORD"
    version: str = "dev"
    seed: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get("DATABASE_URL") or None,
            hub=os.environ.get("HUB", "ORD").upper(),
            version=os.environ.get("APP_VERSION", "dev"),
            seed=os.environ.get("SEED", "true").strip().lower() in ("1", "true", "yes", "on"),
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = make_store(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log.info(
            "bag-api version %s starting: hub %s, storage %s",
            settings.version, settings.hub, store.describe(),
        )
        if settings.seed:
            # The database may still be starting. bag-api starts anyway and
            # reports "not ready" on /readyz until the database answers.
            try:
                if sum(store.count_by_status().values()) == 0:
                    log.info("Store is empty. Added %d sample bags.", add_sample_bags(store))
            except StorageUnavailable as err:
                log.warning("Database not reachable at startup. Sample bags not added: %s", err)
        yield

    app = FastAPI(title="BagTrack bag-api", version=settings.version, lifespan=lifespan)

    @app.exception_handler(StorageUnavailable)
    async def database_unavailable(request: Request, err: StorageUnavailable) -> JSONResponse:
        log.warning("%s %s failed. Database unavailable: %s", request.method, request.url.path, err)
        return JSONResponse(status_code=503, content={"detail": f"Database unavailable: {err}"})

    @app.get("/")
    def index():
        return {"service": "bag-api", "version": settings.version, "docs": "/docs", "bags": "/api/bags"}

    @app.get("/healthz")
    def healthz():
        """Liveness: the process runs. This does not check the database."""
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        """Readiness: the process can reach its storage."""
        try:
            store.ping()
        except StorageUnavailable as err:
            return JSONResponse(
                status_code=503,
                content={"status": "not ready", "storage": store.kind, "error": str(err)},
            )
        return {"status": "ready", "storage": store.kind}

    @app.get("/api/info")
    def info():
        """Which copy of bag-api answered. The board shows this in its footer."""
        return {
            "service": "bag-api",
            "version": settings.version,
            "hostname": socket.gethostname(),
            "hub": settings.hub,
            "storage": store.kind,
        }

    @app.get("/api/bags", response_model=list[Bag])
    def list_bags(
        flight: str | None = None,
        status: Checkpoint | None = None,
        limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    ):
        """List bags, most recently updated first."""
        return store.list_bags(flight.upper() if flight else None, status, limit)

    @app.post("/api/bags", response_model=Bag, status_code=201)
    def check_in(new: NewBag):
        """Check in a bag. It starts at the first checkpoint, checked_in."""
        now = datetime.now(timezone.utc)
        # A tag sent by the client must be new. A generated tag is tried again
        # in the rare case that it is already taken.
        for _ in range(1 if new.tag else 5):
            tag = new.tag or f"BT{random.randint(0, 999_999):06d}"
            bag = Bag(
                tag=tag,
                flight=new.flight,
                passenger=new.passenger,
                destination=new.destination,
                status=CHECKPOINTS[0],
                updated_at=now,
            )
            first_scan = Scan(tag=tag, checkpoint=CHECKPOINTS[0], scanner="check-in", scanned_at=now)
            if store.add_bag(bag, [first_scan]):
                return bag
        raise HTTPException(status_code=409, detail=f"Bag {tag} already exists")

    @app.get("/api/bags/{tag}", response_model=Bag)
    def get_bag(tag: str):
        bag = store.get_bag(tag.upper())
        if bag is None:
            raise HTTPException(status_code=404, detail=f"Bag {tag.upper()} not found")
        return bag

    @app.post("/api/bags/{tag}/scans", response_model=Bag)
    def scan_bag(tag: str, new: NewScan):
        """Record a scan. A bag can only move to its next checkpoint."""
        bag = get_bag(tag)
        try:
            check_move(bag.status, new.checkpoint)
        except IllegalMove as err:
            raise HTTPException(status_code=409, detail=f"Bag {bag.tag} {err}") from err
        scan = Scan(
            tag=bag.tag,
            checkpoint=new.checkpoint,
            scanner=new.scanner,
            scanned_at=datetime.now(timezone.utc),
        )
        moved = store.move_bag(bag.tag, bag.status, scan)
        if moved is None:
            raise HTTPException(
                status_code=409,
                detail=f"Bag {bag.tag} was moved by another scan at the same time. Read it again and retry.",
            )
        return moved

    @app.get("/api/bags/{tag}/scans", response_model=list[Scan])
    def list_scans(tag: str):
        """The scan history of one bag, oldest first."""
        bag = get_bag(tag)
        return store.list_scans(bag.tag)

    @app.get("/api/stats", response_model=Stats)
    def stats():
        """Number of bags at each checkpoint."""
        counts = store.count_by_status()
        by_status = {checkpoint: counts.get(checkpoint, 0) for checkpoint in CHECKPOINTS}
        return Stats(total=sum(by_status.values()), by_status=by_status)

    return app


app = create_app()
