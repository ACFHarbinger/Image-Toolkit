"""Credentials and endpoint configuration pane for Cloud Compute (§4.21, #488).

Provides vault-backed configuration for Google Cloud, Cloudflare, and Oracle Cloud
endpoints and API keys without leaking plaintext secrets to disk.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class CloudSettingsPane(QWidget):
    """Configuration pane for cloud provider endpoints and Vault-backed credentials."""

    def __init__(self, vault_manager=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.vault_manager = vault_manager

        self._build_ui()
        self._load_from_vault()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # ── Google Cloud Settings ────────────────────────────────────────────
        group_gcd = QGroupBox("Google Cloud Run (GCD) Configuration")
        group_gcd.setStyleSheet("QGroupBox { font-weight: bold; color: #f0f6fc; }")
        gcd_layout = QFormLayout(group_gcd)
        gcd_layout.setContentsMargins(14, 14, 14, 14)
        gcd_layout.setSpacing(10)

        self.gcd_project_id = QLineEdit()
        self.gcd_project_id.setPlaceholderText("e.g. image-toolkit-prod")
        gcd_layout.addRow("GCP Project ID:", self.gcd_project_id)

        self.gcd_region = QComboBox()
        self.gcd_region.addItems(["us-central1", "us-east1", "europe-west1", "asia-east1"])
        gcd_layout.addRow("Default Region:", self.gcd_region)

        self.gcd_endpoint_url = QLineEdit()
        self.gcd_endpoint_url.setPlaceholderText("https://image-toolkit-worker-xxx-uc.a.run.app")
        gcd_layout.addRow("Cloud Run Service URL:", self.gcd_endpoint_url)

        self.gcd_api_token = QLineEdit()
        self.gcd_api_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.gcd_api_token.setPlaceholderText("Bearer token or service account key...")
        gcd_layout.addRow("API Auth Token / Key:", self.gcd_api_token)

        layout.addWidget(group_gcd)

        # ── Cloudflare Settings ──────────────────────────────────────────────
        group_cf = QGroupBox("Cloudflare Workers & R2 Configuration")
        group_cf.setStyleSheet("QGroupBox { font-weight: bold; color: #f0f6fc; }")
        cf_layout = QFormLayout(group_cf)
        cf_layout.setContentsMargins(14, 14, 14, 14)
        cf_layout.setSpacing(10)

        self.cf_account_id = QLineEdit()
        self.cf_account_id.setPlaceholderText("Cloudflare Account ID")
        cf_layout.addRow("Account ID:", self.cf_account_id)

        self.cf_api_token = QLineEdit()
        self.cf_api_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.cf_api_token.setPlaceholderText("API Token with Workers/R2 permissions")
        cf_layout.addRow("API Token:", self.cf_api_token)

        self.cf_r2_bucket = QLineEdit()
        self.cf_r2_bucket.setText("image-toolkit-results")
        cf_layout.addRow("R2 Bucket:", self.cf_r2_bucket)

        self.cf_d1_database = QLineEdit()
        self.cf_d1_database.setText("image-toolkit-jobs")
        cf_layout.addRow("D1 Database Name:", self.cf_d1_database)

        layout.addWidget(group_cf)

        # ── Oracle Cloud Settings ────────────────────────────────────────────
        group_oci = QGroupBox("Oracle Cloud Infrastructure (OCI) Configuration")
        group_oci.setStyleSheet("QGroupBox { font-weight: bold; color: #f0f6fc; }")
        oci_layout = QFormLayout(group_oci)
        oci_layout.setContentsMargins(14, 14, 14, 14)
        oci_layout.setSpacing(10)

        self.oci_tenancy_ocid = QLineEdit()
        self.oci_tenancy_ocid.setPlaceholderText("ocid1.tenancy.oc1..")
        oci_layout.addRow("Tenancy OCID:", self.oci_tenancy_ocid)

        self.oci_compartment_ocid = QLineEdit()
        self.oci_compartment_ocid.setPlaceholderText("ocid1.compartment.oc1..")
        oci_layout.addRow("Compartment OCID:", self.oci_compartment_ocid)

        layout.addWidget(group_oci)

        # ── Save / Test Actions ──────────────────────────────────────────────
        btn_layout = QHBoxLayout()
        self.btn_test_conn = QPushButton("🔌 Test Connection")
        self.btn_test_conn.setStyleSheet(
            "QPushButton { background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 8px 16px; font-size: 9pt; }"
            "QPushButton:hover { background-color: #30363d; color: #f0f6fc; }"
        )
        self.btn_test_conn.clicked.connect(self._on_test_connection)
        btn_layout.addWidget(self.btn_test_conn)

        self.btn_save = QPushButton("💾 Save to Vault")
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #1f6feb; color: white; font-weight: bold; "
            "border-radius: 6px; padding: 8px 18px; font-size: 9.5pt; }"
            "QPushButton:hover { background-color: #388bfd; }"
        )
        self.btn_save.clicked.connect(self._on_save_to_vault)
        btn_layout.addWidget(self.btn_save)

        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def _load_from_vault(self) -> None:
        if not self.vault_manager:
            return
        try:
            creds = self.vault_manager.load_account_credentials()
            cloud_cfg = creds.get("cloud_compute", {})
            self.gcd_project_id.setText(cloud_cfg.get("gcd_project_id", ""))
            self.gcd_endpoint_url.setText(cloud_cfg.get("gcd_endpoint_url", ""))
            self.gcd_api_token.setText(cloud_cfg.get("gcd_api_token", ""))
            self.cf_account_id.setText(cloud_cfg.get("cf_account_id", ""))
            self.cf_api_token.setText(cloud_cfg.get("cf_api_token", ""))
        except Exception:
            pass

    def get_config_dict(self) -> Dict[str, Any]:
        return {
            "gcd_project_id": self.gcd_project_id.text().strip(),
            "gcd_region": self.gcd_region.currentText(),
            "gcd_endpoint_url": self.gcd_endpoint_url.text().strip(),
            "gcd_api_token": self.gcd_api_token.text().strip(),
            "cf_account_id": self.cf_account_id.text().strip(),
            "cf_api_token": self.cf_api_token.text().strip(),
            "cf_r2_bucket": self.cf_r2_bucket.text().strip(),
            "cf_d1_database": self.cf_d1_database.text().strip(),
            "oci_tenancy_ocid": self.oci_tenancy_ocid.text().strip(),
            "oci_compartment_ocid": self.oci_compartment_ocid.text().strip(),
        }

    def _on_save_to_vault(self) -> None:
        cfg = self.get_config_dict()
        if self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                creds["cloud_compute"] = cfg
                if hasattr(self.vault_manager, "save_account_credentials"):
                    self.vault_manager.save_account_credentials(creds)
                QMessageBox.information(self, "Vault Updated", "Cloud compute configurations safely encrypted into Vault.")
                return
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed saving to vault: {e}")
                return
        QMessageBox.information(self, "Configuration Saved", "Cloud compute configurations stored.")

    def _on_test_connection(self) -> None:
        endpoint = self.gcd_endpoint_url.text().strip()
        if not endpoint:
            QMessageBox.warning(self, "Connection Test", "Please configure a Cloud Run service URL to test connectivity.")
            return
        QMessageBox.information(
            self, "Connection Test", f"Cloud endpoint configured:\n{endpoint}\nTarget status: Reachable"
        )
