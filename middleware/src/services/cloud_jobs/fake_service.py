"""Fake cloud service factory for Gate B-compliant execution and tests (#850 / #1109)."""

from __future__ import annotations

import datetime as _dt
import tempfile
import time
from pathlib import Path
from typing import Any

from middleware.src.cloud.cost import ComputePrice, PriceCatalogue
from middleware.src.cloud.engine import EngineSettings, JobEngine
from middleware.src.cloud.fakes import FakeProvider
from middleware.src.cloud.service import CloudJobService
from middleware.src.cloud.settings import CloudSettings
from middleware.src.cloud.store import CloudJobStore

_CATALOGUE = PriceCatalogue([
    ComputePrice("fake", "*", "instance", "cpu", 1.0, last_verified="2026-10-20"),
    ComputePrice("runpod", "*", "managed_batch", "cpu", 1.0, last_verified="2026-10-20"),
    ComputePrice("runpod", "*", "instance", "cpu", 1.0, last_verified="2026-10-20"),
    ComputePrice("aws", "*", "instance", "cpu", 1.0, last_verified="2026-10-20"),
])


def create_fake_cloud_service(
    store_path: Path | None = None,
    clock: Any = time.time,
) -> CloudJobService:
    """Create a CloudJobService backed by in-memory/temp store and FakeProvider."""
    if store_path is None:
        temp_dir = tempfile.mkdtemp(prefix="itk_fake_cloud_")
        store_path = Path(temp_dir) / "cloud_jobs.db"

    store = CloudJobStore.open("fake-secret-key-32-chars-long!", "salt-0123456789ab", store_path, clock=clock)
    store.clock = clock

    fake_provider = FakeProvider(name="fake")
    runpod_fake = FakeProvider(name="runpod")
    aws_fake = FakeProvider(name="aws")

    adapters = {
        "fake": fake_provider,
        "runpod": runpod_fake,
        "aws": aws_fake,
    }

    engine = JobEngine(
        store=store,
        adapters=adapters,
        settings=EngineSettings(owner="sidecar"),
        clock=clock,
    )

    settings = CloudSettings(
        default_max_spend_usd=10.0,
        monthly_cap_usd=50.0,
    )

    return CloudJobService(
        engine=engine,
        settings=settings,
        catalogue=_CATALOGUE,
        clock=clock,
        today=lambda: _dt.date.today(),
    )


__all__ = ["create_fake_cloud_service"]
