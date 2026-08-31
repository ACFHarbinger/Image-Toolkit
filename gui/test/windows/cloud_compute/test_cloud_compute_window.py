from unittest.mock import patch

import pytest
from gui.src.windows.cloud_compute.cloud_compute_window import CloudComputeWindow
from gui.src.windows.cloud_compute.cloud_settings_pane import CloudSettingsPane
from gui.src.windows.cloud_compute.dashboards_pane import DashboardsPane
from gui.src.windows.cloud_compute.provider_card import (
    ProviderDescriptor,
    ProviderDescriptorCard,
)
from gui.src.windows.cloud_compute.providers_pane import ProvidersPane
from gui.src.windows.cloud_compute.request_builder_pane import RequestBuilderPane
from PySide6.QtWidgets import QMessageBox

pytestmark = pytest.mark.gui


class TestProviderDescriptorCard:
    def test_card_initialization_and_specs(self, q_app):
        desc = ProviderDescriptor(
            provider_id="gcd",
            name="Google Cloud Run (GCD)",
            badge_text="Active PoC Target",
            badge_color="#56d364",
            description="Knative serverless containers.",
            target_service="Cloud Run",
            cpu_shapes="4 vCPU",
            memory_tiers="16 GiB",
            gpu_options="NVIDIA L4",
            cost_estimate="~$0.09/hr",
            cold_start="~1.2s",
            regions=["us-central1", "us-east1"],
            config_file="infra/cloud/gcd/cloud-run-service.yaml",
            is_poc_target=True,
        )
        card = ProviderDescriptorCard(desc, is_selected=True)
        assert card.title_label.text() == "Google Cloud Run (GCD)"
        assert card.badge_label.text() == " Active PoC Target "
        assert card.is_selected() is True
        assert card.selected_region() == "us-central1"

    def test_card_selection_signal(self, q_app):
        desc = ProviderDescriptor(
            provider_id="cloudflare",
            name="Cloudflare Workers",
            badge_text="Planned",
            badge_color="#f0883e",
            description="Edge worker queue.",
            target_service="Workers",
            cpu_shapes="128 MB",
            memory_tiers="Unmetered",
            gpu_options="None",
            cost_estimate="$5/mo",
            cold_start="~5ms",
            regions=["Global Edge"],
        )
        card = ProviderDescriptorCard(desc, is_selected=False)
        received_id = []
        card.selected.connect(lambda pid: received_id.append(pid))

        card.btn_select.click()
        assert received_id == ["cloudflare"]
        assert card.is_selected() is True


class TestProvidersPane:
    def test_providers_catalog_and_selection(self, q_app):
        pane = ProvidersPane(initial_provider="gcd")
        assert pane.get_active_provider_id() == "gcd"
        assert "Google Cloud Run (GCD)" in pane.banner_label.text()

        received = []
        pane.active_provider_changed.connect(lambda pid: received.append(pid))

        pane.set_active_provider_id("oracle")
        assert pane.get_active_provider_id() == "oracle"
        assert received == ["oracle"]
        assert "Oracle Cloud" in pane.banner_label.text()


class TestRequestBuilderPane:
    def test_build_job_payload(self, q_app):
        pane = RequestBuilderPane(active_provider="gcd")
        pane.input_source_path.setText("/tmp/sample.mp4")
        pane.spin_start_ms.setValue(1000)
        pane.spin_end_ms.setValue(4000)
        pane.spin_fps.setValue(30)

        payload = pane.build_job_payload()
        assert payload["provider"] == "gcd"
        assert payload["source_path"] == "/tmp/sample.mp4"
        assert payload["start_ms"] == 1000
        assert payload["end_ms"] == 4000
        assert payload["fps"] == 30
        assert payload["status"] == "QUEUED"

    def test_run_cloud_validates_empty_source(self, q_app):
        pane = RequestBuilderPane(active_provider="gcd")
        pane.input_source_path.clear()

        with patch.object(QMessageBox, "warning") as mock_warn:
            pane._on_run_cloud_clicked()
            mock_warn.assert_called_once()
            assert pane.table_jobs.rowCount() == 0

    def test_run_cloud_dispatches_job(self, q_app):
        pane = RequestBuilderPane(active_provider="gcd")
        pane.input_source_path.setText("/tmp/test.mp4")

        submitted = []
        pane.job_submitted.connect(lambda job: submitted.append(job))

        with patch.object(QMessageBox, "information") as mock_info:
            pane._on_run_cloud_clicked()
            mock_info.assert_called_once()
            assert len(submitted) == 1
            assert pane.table_jobs.rowCount() == 1
            assert pane.table_jobs.item(0, 2).text() == "GCD"


class TestDashboardsPane:
    def test_add_usage_row_and_kpis(self, q_app):
        pane = DashboardsPane()
        assert pane.table_usage.rowCount() == 0

        pane.add_usage_row({
            "timestamp": "2026-08-31 19:00:00",
            "job_id": "job-12345",
            "provider": "gcd",
            "task": "Frame Extraction",
            "duration": "14.2s",
            "egress": "28.5 MB",
            "cost": "$0.0012",
        })

        assert pane.table_usage.rowCount() == 1
        assert pane.table_usage.item(0, 1).text() == "job-12345"
        assert pane.table_usage.item(0, 2).text() == "GCD"


class TestCloudSettingsPane:
    def test_settings_inputs_and_dict(self, q_app):
        pane = CloudSettingsPane()
        pane.gcd_project_id.setText("test-gcp-project")
        pane.gcd_endpoint_url.setText("https://worker.run.app")
        pane.cf_account_id.setText("cf-123456")

        cfg = pane.get_config_dict()
        assert cfg["gcd_project_id"] == "test-gcp-project"
        assert cfg["gcd_endpoint_url"] == "https://worker.run.app"
        assert cfg["cf_account_id"] == "cf-123456"


class TestCloudComputeWindowShell:
    def test_window_structure_and_navigation(self, q_app):
        window = CloudComputeWindow()
        assert window.nav_list.count() == 4
        assert window.stack.count() == 4

        # Verify initial page is Providers
        assert window.stack.currentIndex() == 0

        # Change tab via nav
        window.nav_list.setCurrentRow(1)
        assert window.stack.currentIndex() == 1
        assert isinstance(window.stack.currentWidget(), RequestBuilderPane)

        window.nav_list.setCurrentRow(2)
        assert window.stack.currentIndex() == 2
        assert isinstance(window.stack.currentWidget(), DashboardsPane)

        window.nav_list.setCurrentRow(3)
        assert window.stack.currentIndex() == 3
        assert isinstance(window.stack.currentWidget(), CloudSettingsPane)

    def test_provider_change_synchronization(self, q_app):
        window = CloudComputeWindow()
        window.pane_providers.set_active_provider_id("cloudflare")

        assert window.pane_request_builder._active_provider == "cloudflare"
        assert "Cloudflare Workers" in window.lbl_status.text()
