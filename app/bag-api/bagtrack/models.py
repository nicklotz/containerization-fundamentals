"""The shapes of the data that bag-api reads and returns.

FastAPI uses these Pydantic classes to check incoming JSON and to describe
the API on the /docs page.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .checkpoints import Checkpoint


class NewBag(BaseModel):
    """Body of POST /api/bags."""

    model_config = ConfigDict(str_strip_whitespace=True)

    flight: str = Field(pattern=r"^[A-Z]{2}\d{1,4}$", examples=["FL101"])
    passenger: str = Field(min_length=1, max_length=40, examples=["Garcia"])
    destination: str = Field(pattern=r"^[A-Z]{3}$", examples=["SFO"])
    # Leave the tag out and bag-api generates one.
    tag: str | None = Field(default=None, pattern=r"^BT\d{6}$", examples=["BT123456"])

    @field_validator("flight", "destination", "tag", mode="before")
    @classmethod
    def uppercase(cls, value):
        # Accept "fl101" or "sfo" and store "FL101" or "SFO".
        return value.upper() if isinstance(value, str) else value


class Bag(BaseModel):
    """A bag and the last checkpoint it passed."""

    tag: str
    flight: str
    passenger: str
    destination: str
    status: Checkpoint
    updated_at: datetime


class NewScan(BaseModel):
    """Body of POST /api/bags/{tag}/scans."""

    checkpoint: Checkpoint
    scanner: str = Field(default="manual", min_length=1, max_length=64, examples=["sc-7f3a"])


class Scan(BaseModel):
    """One scan of a bag at a checkpoint."""

    tag: str
    checkpoint: Checkpoint
    scanner: str
    scanned_at: datetime


class Stats(BaseModel):
    """Answer of GET /api/stats."""

    total: int
    by_status: dict[str, int]
