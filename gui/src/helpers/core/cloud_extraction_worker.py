"""Run one extractor-tab extraction on Google Cloud Run (#487).

Wraps :class:`CloudExtractionDispatcher` in a ``QRunnable`` so the upload →
cloud run → download round-trip happens off the GUI thread. Provider config
(service URL, auth token, project, source bucket) is read from the vault
``cloud_compute`` credentials the Cloud Settings pane writes.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from gui.src.helpers.base import BaseQRunnableWorker


class CloudConfigError(RuntimeError):
    """Raised when the vault has no usable Cloud Run configuration."""


def _cloud_cfg(vault_manager) -> Dict[str, Any]:
    if vault_manager is None:
        raise CloudConfigError("no vault session — unlock an account first")
    try:
        creds = vault_manager.load_account_credentials()
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as-is
        raise CloudConfigError(f"could not read vault credentials: {exc}") from exc
    cfg = dict(creds.get("cloud_compute", {}) or {})
    if not cfg.get("gcd_endpoint_url"):
        raise CloudConfigError(
            "no Cloud Run service URL configured — set it in "
            "Cloud Compute ▸ Settings first"
        )
    return cfg


def build_dispatcher(vault_manager, output_dir: str):
    """Assemble a `CloudExtractionDispatcher` for GCD from vault config."""
    from backend.src.web.cloud.compute import (
        CloudExtractionDispatcher,
        GCDCloudRunAdapter,
    )

    cfg = _cloud_cfg(vault_manager)
    token = (cfg.get("gcd_api_token") or "").strip()
    adapter = GCDCloudRunAdapter(
        cfg["gcd_endpoint_url"].strip(),
        id_token_provider=(lambda t=token: t) if token else None,
    )
    project = (cfg.get("gcd_project_id") or "").strip()
    source_bucket = (
        (cfg.get("gcd_source_bucket") or "").strip()
        or (f"{project}-itk-cloud-src" if project else "")
    )
    if not source_bucket:
        raise CloudConfigError(
            "no source bucket — set a GCP Project ID (or gcd_source_bucket) "
            "in Cloud Compute ▸ Settings"
        )
    return CloudExtractionDispatcher(
        adapter, source_bucket=source_bucket, output_dir=output_dir
    )


class CloudExtractionWorker(BaseQRunnableWorker):
    """``signals.finished`` → ``dict`` result, ``signals.error`` → ``str``."""

    def __init__(
        self,
        extraction_config: Dict[str, Any],
        *,
        vault_manager,
        output_dir: str,
        job_id: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._config = dict(extraction_config)
        self._vault = vault_manager
        self._output_dir = output_dir
        self._job_id = job_id

    def _execute(self) -> None:
        dispatcher = build_dispatcher(self._vault, self._output_dir)
        result = dispatcher.dispatch(self._config, job_id=self._job_id)
        if not result.ok:
            self.signals.error.emit(result.error or "cloud extraction failed")
            return
        usage = (
            {
                "job_id": result.usage_row.job_id,
                "provider": result.usage_row.provider,
                "task": result.usage_row.task,
                "status": result.usage_row.status,
                "duration_seconds": result.usage_row.duration_seconds,
                "cost_usd": result.usage_row.cost_usd,
            }
            if result.usage_row is not None
            else {}
        )
        self.signals.finished.emit(
            {
                "paths": list(result.local_paths),
                "job_id": result.job_id,
                "source_uri": result.source_uri,
                "usage": usage,
            }
        )


__all__ = ["CloudExtractionWorker", "build_dispatcher", "CloudConfigError"]
