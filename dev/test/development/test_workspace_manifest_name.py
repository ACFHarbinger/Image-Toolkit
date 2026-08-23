"""Regression coverage for workspace manifest-name discovery."""

from __future__ import annotations

import json

from tool.host.plugins import MANIFEST_SCHEMA, load_manifest
from tool.host.workspace import discover_plugin_sources


def test_discovery_uses_manifest_name_when_filename_differs(tmp_path):
    manifest = tmp_path / "renamed.plugin.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": MANIFEST_SCHEMA,
                "name": "declared-name",
                "version": "0.1.0",
                "entry": {"python_module": "pkg.plugin:plugin", "command": None},
            }
        ),
        encoding="utf-8",
    )

    sources = discover_plugin_sources(global_dir=tmp_path)

    assert [load_manifest(source).name for source in sources] == ["declared-name"]
