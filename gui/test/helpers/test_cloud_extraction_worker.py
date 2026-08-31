"""CloudExtractionWorker config plumbing (#487) — no Qt event loop needed."""

from __future__ import annotations

import pytest
from gui.src.helpers.core.cloud_extraction_worker import (
    CloudConfigError,
    build_dispatcher,
)


class _Vault:
    def __init__(self, cloud_cfg):
        self._cfg = cloud_cfg

    def load_account_credentials(self):
        return {"cloud_compute": self._cfg}


def test_build_dispatcher_requires_service_url(tmp_path):
    with pytest.raises(CloudConfigError, match="service URL"):
        build_dispatcher(_Vault({}), str(tmp_path))


def test_build_dispatcher_requires_a_source_bucket(tmp_path):
    with pytest.raises(CloudConfigError, match="source bucket"):
        build_dispatcher(
            _Vault({"gcd_endpoint_url": "https://svc.run.app"}), str(tmp_path)
        )


def test_build_dispatcher_derives_bucket_from_project(tmp_path):
    disp = build_dispatcher(
        _Vault(
            {
                "gcd_endpoint_url": "https://svc.run.app",
                "gcd_project_id": "itk-prod",
                "gcd_api_token": "tok-1",
            }
        ),
        str(tmp_path),
    )
    assert disp._bucket == "itk-prod-itk-cloud-src"
    assert disp._adapter.name == "gcd"


def test_build_dispatcher_explicit_bucket_wins(tmp_path):
    disp = build_dispatcher(
        _Vault(
            {
                "gcd_endpoint_url": "https://svc.run.app",
                "gcd_project_id": "itk-prod",
                "gcd_source_bucket": "my-explicit-bucket",
            }
        ),
        str(tmp_path),
    )
    assert disp._bucket == "my-explicit-bucket"


def test_no_vault_is_a_config_error(tmp_path):
    with pytest.raises(CloudConfigError):
        build_dispatcher(None, str(tmp_path))
