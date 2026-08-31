"""Providers pane for Cloud Compute Offload window (§4.21, #488).

Renders provider descriptor cards for Google Cloud Run, Cloudflare Workers,
Oracle Cloud Infrastructure, and AWS, with selection tracking and status telemetry.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .provider_card import ProviderDescriptor, ProviderDescriptorCard


class ProvidersPane(QWidget):
    """Container displaying the catalog of supported cloud compute providers."""

    active_provider_changed = Signal(str)  # Emits provider_id on change

    DEFAULT_PROVIDERS = [
        ProviderDescriptor(
            provider_id="gcd",
            name="Google Cloud Run (GCD)",
            badge_text="Active PoC Target",
            badge_color="#56d364",
            description=(
                "Serverless container compute powered by Knative. Runs isolated extraction "
                "workers with automatic scaling from 0 to 8 instances. Ideal for high-throughput "
                "frame slicing and GIF transcoding without consuming local CPU or RAM."
            ),
            target_service="Cloud Run (Knative)",
            cpu_shapes="4 vCPU (Flex Gen2)",
            memory_tiers="16 GiB RAM",
            gpu_options="NVIDIA L4 24GB (Optional)",
            cost_estimate="~$0.09 / hr (Per-second billing)",
            cold_start="~1.2s (Gen2 container)",
            regions=[
                "us-central1 (Iowa)",
                "us-east1 (S. Carolina)",
                "europe-west1 (Belgium)",
                "asia-east1 (Taiwan)",
            ],
            config_file="infra/cloud/gcd/cloud-run-service.yaml",
            is_poc_target=True,
        ),
        ProviderDescriptor(
            provider_id="cloudflare",
            name="Cloudflare Workers & Queues",
            badge_text="Planned / Edge Queue",
            badge_color="#f0883e",
            description=(
                "Ultra-low-latency edge queue consumer backed by Cloudflare R2 bucket storage "
                "and D1 analytics database. Coordinates asynchronous batch jobs across 300+ global PoPs "
                "with instant edge dispatch."
            ),
            target_service="Workers + R2 + D1",
            cpu_shapes="128 MB V8 Isolate",
            memory_tiers="Unmetered Edge I/O",
            gpu_options="Cloudflare AI / Partner API",
            cost_estimate="$5/mo base + $0.50/M ops",
            cold_start="~5ms (V8 Isolate)",
            regions=["Global Edge (300+ PoPs)"],
            config_file="infra/cloud/cloudflare/wrangler.toml",
            is_poc_target=False,
        ),
        ProviderDescriptor(
            provider_id="oracle",
            name="Oracle Cloud Infrastructure (OCI)",
            badge_text="Planned / GPU Shapes",
            badge_color="#d2a8ff",
            description=(
                "High-performance OCI Container Instances running on AMD E4 or Ampere A1 Flex cores, "
                "with dedicated NVIDIA A10 Tensor Core GPUs available for deep-learning image generation "
                "and heavy parallel workloads."
            ),
            target_service="OCI Container Instance",
            cpu_shapes="4 OCPU (8 vCPU)",
            memory_tiers="16–64 GiB RAM",
            gpu_options="NVIDIA A10 24GB Tensor Core",
            cost_estimate="Always Free Tier / ~$0.05/hr",
            cold_start="~3–5s (OCI Container)",
            regions=[
                "us-ashburn-1 (N. Virginia)",
                "us-phoenix-1 (Arizona)",
                "eu-frankfurt-1 (Germany)",
            ],
            config_file="infra/cloud/oracle/oci-container-instance.tf",
            is_poc_target=False,
        ),
        ProviderDescriptor(
            provider_id="aws",
            name="Amazon Web Services (AWS)",
            badge_text="Roadmap / Fargate",
            badge_color="#8b949e",
            description=(
                "Serverless container execution on AWS Fargate with S3 results storage "
                "and SQS asynchronous job queuing."
            ),
            target_service="Fargate / ECS + S3",
            cpu_shapes="4 vCPU",
            memory_tiers="16 GiB RAM",
            gpu_options="AWS G5 / G6e Instances",
            cost_estimate="~$0.16 / hr",
            cold_start="~10–15s (Fargate task)",
            regions=[
                "us-east-1 (N. Virginia)",
                "us-west-2 (Oregon)",
                "eu-west-1 (Ireland)",
            ],
            config_file="infra/cloud/aws/cfn-template.yaml",
            is_poc_target=False,
        ),
    ]

    def __init__(self, initial_provider: str = "gcd", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._active_provider_id = initial_provider
        self._cards: Dict[str, ProviderDescriptorCard] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # ── Banner: Active Provider Summary ──────────────────────────────────
        self.banner_frame = QFrame()
        self.banner_frame.setStyleSheet(
            "background-color: #161b22; border: 1px solid #30363d; border-radius: 6px;"
        )
        banner_layout = QHBoxLayout(self.banner_frame)
        banner_layout.setContentsMargins(14, 10, 14, 10)

        self.banner_label = QLabel()
        self.banner_label.setStyleSheet("color: #f0f6fc; font-size: 10pt; font-weight: bold;")
        banner_layout.addWidget(self.banner_label)
        banner_layout.addStretch(1)

        main_layout.addWidget(self.banner_frame)

        # ── Title & Intro ────────────────────────────────────────────────────
        intro_label = QLabel(
            "Select an infrastructure provider to offload resource-heavy workloads "
            "(video frame extraction, GIF rendering, and deep-learning generation). "
            "Jobs are packaged into containerized workloads and executed remotely."
        )
        intro_label.setWordWrap(True)
        intro_label.setStyleSheet("color: #8b949e; font-size: 9.5pt; line-height: 1.4;")
        main_layout.addWidget(intro_label)

        # ── Scrollable Provider Cards List ───────────────────────────────────
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        cards_container = QWidget()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        for desc in self.DEFAULT_PROVIDERS:
            is_selected = (desc.provider_id == self._active_provider_id)
            card = ProviderDescriptorCard(desc, is_selected=is_selected)
            card.selected.connect(self._on_card_selected)
            self._cards[desc.provider_id] = card
            cards_layout.addWidget(card)

        cards_layout.addStretch(1)
        scroll_area.setWidget(cards_container)
        main_layout.addWidget(scroll_area)

        self._update_banner()

    def _on_card_selected(self, provider_id: str) -> None:
        self._active_provider_id = provider_id
        for pid, card in self._cards.items():
            card.set_selected(pid == provider_id)
        self._update_banner()
        self.active_provider_changed.emit(provider_id)

    def _update_banner(self) -> None:
        selected_card = self._cards.get(self._active_provider_id)
        if selected_card:
            p_name = selected_card.descriptor.name
            region = selected_card.selected_region()
            self.banner_label.setText(
                f"⚡ Active Offload Target: <span style='color:#58a6ff;'>{p_name}</span> "
                f"&nbsp;•&nbsp; Region: <span style='color:#79c0ff;'>{region}</span>"
            )
        else:
            self.banner_label.setText("⚡ Active Offload Target: None")

    def get_active_provider_id(self) -> str:
        return self._active_provider_id

    def set_active_provider_id(self, provider_id: str) -> None:
        if provider_id in self._cards:
            self._on_card_selected(provider_id)

    def get_selected_region(self, provider_id: Optional[str] = None) -> str:
        pid = provider_id or self._active_provider_id
        card = self._cards.get(pid)
        return card.selected_region() if card else "us-central1"
