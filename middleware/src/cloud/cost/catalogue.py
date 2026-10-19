"""Versioned price catalogue (#832).

Rows come from three layers, highest priority first: user overrides, live
price APIs (provider adapters fill this where one exists), and the curated
file. No prices are shipped as fact: the curated seed starts empty and every
row carries ``last_verified`` so stale data shows up as a warning.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

SEED_PATH = Path(__file__).with_name("prices.yaml")
LAYER_USER = "user"
LAYER_LIVE = "live"
LAYER_CURATED = "curated"
_LAYER_ORDER = (LAYER_USER, LAYER_LIVE, LAYER_CURATED)
ANY = "*"


@dataclass(frozen=True)
class ComputePrice:
    provider: str
    region: str           # or "*"
    mode: str             # ExecutionMode value, or "*"
    sku: str              # instance type / GPU class / "cpu"
    usd_per_hour: float
    billing_increment_s: int = 1
    minimum_s: int = 0
    startup_s: float = 0.0       # boot/pull time that bills before work starts
    ipv4_usd_per_hour: float = 0.0
    spot: bool = False
    last_verified: str = ""      # ISO date
    layer: str = LAYER_CURATED

    @property
    def key(self) -> Tuple[str, str, str, str, bool]:
        return (self.provider, self.region, self.mode, self.sku, self.spot)


@dataclass(frozen=True)
class EgressPrice:
    provider: str
    destination: str  # "internet" or another provider id
    usd_per_gb: float
    last_verified: str = ""
    layer: str = LAYER_CURATED


@dataclass(frozen=True)
class StoragePrice:
    provider: str
    usd_per_gb_month: float
    last_verified: str = ""
    layer: str = LAYER_CURATED


def age_days(last_verified: str, today: _dt.date) -> Optional[int]:
    try:
        return (today - _dt.date.fromisoformat(last_verified)).days
    except (TypeError, ValueError):
        return None


class PriceCatalogue:
    def __init__(self, compute: Iterable[ComputePrice] = (), egress: Iterable[EgressPrice] = (),
                 storage: Iterable[StoragePrice] = (), version: str = "0"):
        self.version = version
        self._compute = list(compute)
        self._egress = list(egress)
        self._storage = list(storage)

    @classmethod
    def load(cls, path: Path = SEED_PATH) -> "PriceCatalogue":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
        data = data or {}
        return cls(
            [ComputePrice(**r) for r in data.get("compute", []) or []],
            [EgressPrice(**r) for r in data.get("egress", []) or []],
            [StoragePrice(**r) for r in data.get("storage", []) or []],
            str(data.get("version", "0")),
        )

    def with_rows(self, compute: Sequence[ComputePrice] = (), egress: Sequence[EgressPrice] = (),
                  storage: Sequence[StoragePrice] = ()) -> "PriceCatalogue":
        """A new catalogue with extra rows (user overrides or live prices) layered in."""
        return PriceCatalogue(self._compute + list(compute), self._egress + list(egress),
                              self._storage + list(storage), self.version)

    @staticmethod
    def _best(rows: List[Any]) -> Optional[Any]:
        if not rows:
            return None
        return min(rows, key=lambda r: _LAYER_ORDER.index(r.layer) if r.layer in _LAYER_ORDER else 9)

    def compute(self, provider: str, region: str, mode: str, sku: str, spot: bool = False) -> Optional[ComputePrice]:
        def match(r: ComputePrice, reg: str, md: str) -> bool:
            return (r.provider == provider and r.sku == sku and r.spot == spot
                    and r.region == reg and r.mode == md)

        for reg, md in ((region, mode), (region, ANY), (ANY, mode), (ANY, ANY)):
            hit = self._best([r for r in self._compute if match(r, reg, md)])
            if hit is not None:
                return hit
        return None

    def egress(self, provider: str, destination: str = "internet") -> Optional[EgressPrice]:
        return self._best([r for r in self._egress if r.provider == provider and r.destination == destination])

    def storage(self, provider: str) -> Optional[StoragePrice]:
        return self._best([r for r in self._storage if r.provider == provider])

    def skus(self, provider: str) -> List[str]:
        return sorted({r.sku for r in self._compute if r.provider == provider})


def snapshot(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    """Serialisable copy of the rows an estimate used, stored with the job."""
    return [{"type": type(r).__name__, **asdict(r)} for r in rows if r is not None]
