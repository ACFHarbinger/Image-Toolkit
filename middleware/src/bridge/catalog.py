"""Contract catalog for the bridge package (W0-11, #875).

Loads ``contracts/`` (schemas + ``methods.toml``) once per process and
exposes the routing surface the bridge frames against. Schema refs follow
the contract convention ``"<stem>.<Title>"``: stem is the schema file stem
under ``schemas/envelope/`` or ``schemas/capability/``, Title a root or
``$defs`` title.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .schema import SchemaError, SchemaRegistry

_ENV_CONTRACTS_DIR = "IMAGE_TOOLKIT_CONTRACTS_DIR"


class ContractsNotFound(Exception):
    """The contracts directory could not be located."""


def contracts_dir() -> Path:
    """Locate ``contracts/``: env override first, then walking up from here."""
    env = os.environ.get(_ENV_CONTRACTS_DIR)
    if env:
        path = Path(env)
        if not (path / "methods.toml").is_file():
            raise ContractsNotFound(f"{_ENV_CONTRACTS_DIR}={env} has no methods.toml")
        return path
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "contracts"
        if (candidate / "methods.toml").is_file():
            return candidate
    raise ContractsNotFound(
        "contracts/ not found; set IMAGE_TOOLKIT_CONTRACTS_DIR when the bridge package runs outside the repository"
    )


@lru_cache(maxsize=1)
def _load() -> "Catalog":
    return Catalog(contracts_dir())


def catalog() -> "Catalog":
    """Process-wide contract catalog (loaded once, immutable)."""
    return _load()


@dataclass(frozen=True)
class MethodRoute:
    name: str
    capability: str
    params_schema: str  # "<stem>.<Title>"
    result_schema: str
    errors: tuple[str, ...]
    cancelable: bool
    emits: tuple[str, ...]
    stability: str


@dataclass(frozen=True)
class ChannelRoute:
    name: str
    payload_schema: str
    snapshot_schema: str
    durable_default: bool


class Catalog:
    """The method/channel routing surface plus schema validators."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.registry = SchemaRegistry(root / "schemas")
        with (root / "methods.toml").open("rb") as handle:
            table = tomllib.load(handle)
        envelope = table.get("envelope", {})
        self.jsonrpc_version: str = envelope.get("jsonrpc", "2.0")
        self.methods: dict[str, MethodRoute] = {}
        for row in table.get("method", []):
            route = MethodRoute(
                name=row["name"],
                capability=row["capability"],
                params_schema=row["params"],
                result_schema=row["result"],
                errors=tuple(row.get("errors", [])),
                cancelable=bool(row.get("cancelable", False)),
                emits=tuple(row.get("emits", [])),
                stability=row.get("stability", "experimental"),
            )
            if route.name in self.methods:
                raise ValueError(f"duplicate method {route.name} in methods.toml")
            self.methods[route.name] = route
        self.channels: dict[str, ChannelRoute] = {
            row["name"]: ChannelRoute(
                name=row["name"],
                payload_schema=row["payload"],
                snapshot_schema=row["snapshot"],
                durable_default=bool(row.get("durable_default", False)),
            )
            for row in table.get("channel", [])
        }

    def _schema_file(self, stem: str) -> str:
        for sub in ("envelope", "capability"):
            rel = f"{sub}/{stem}.json"
            if (self.root / "schemas" / rel).is_file():
                return rel
        raise ValueError(f"no schema file for stem {stem!r}")

    def _split_ref(self, schema_ref: str) -> tuple[str, str]:
        stem, _, title = schema_ref.partition(".")
        if not title:
            raise ValueError(f"schema ref {schema_ref!r} must be '<stem>.<Title>'")
        return self._schema_file(stem), title

    def _validate(self, schema_ref: str, instance: Any) -> list[SchemaError]:
        file_rel, title = self._split_ref(schema_ref)
        doc = self.registry.document(file_rel)
        root_title = doc.get("title")
        if title == root_title:
            ref = "#"
        else:
            if title not in doc.get("$defs", {}):
                raise ValueError(f"schema {schema_ref!r}: no $defs entry titled {title!r}")
            ref = f"#/$defs/{title}"
        return self.registry.validate(instance, ref, file_rel)

    def validate_request_envelope(self, frame: Any) -> list[SchemaError]:
        return self._validate("request.BridgeRequest", frame)

    def validate_response_envelope(self, frame: Any) -> list[SchemaError]:
        return self._validate("response.BridgeResponse", frame)

    def validate_error_envelope(self, frame: Any) -> list[SchemaError]:
        return self._validate("error.BridgeError", frame)

    def validate_event_envelope(self, frame: Any) -> list[SchemaError]:
        return self._validate("event.BridgeEvent", frame)

    def validate_params(self, method: str, params: Any) -> list[SchemaError]:
        route = self.methods.get(method)
        if route is None:
            raise ValueError(f"unknown method {method!r}; not in methods.toml")
        return self._validate(route.params_schema, params)

    def validate_result(self, method: str, result: Any) -> list[SchemaError]:
        route = self.methods.get(method)
        if route is None:
            raise ValueError(f"unknown method {method!r}; not in methods.toml")
        return self._validate(route.result_schema, result)

    def validate_event_payload(self, channel: str, payload: Any) -> list[SchemaError]:
        route = self.channels.get(channel)
        if route is None:
            raise ValueError(f"unknown channel {channel!r}; not in methods.toml")
        return self._validate(route.payload_schema, payload)

    def capabilities(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for route in self.methods.values():
            seen.setdefault(route.capability, None)
        return tuple(seen)
