"""#750: Review can run OCR and VLM on their own. No network and no model."""
import pytest
from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton

from gui.src.tabs.models.review_vision_tools import ReviewVisionPanel

pytestmark = pytest.mark.gui


class _Ocr:
    name = "fake"

    def read(self, image_path, *, region=None):
        from backend.src.core.guidance_vision import OcrBox, OcrResult

        return OcrResult("fake", "Hello", (OcrBox("Hello", 0, 0, 1, 1, 90.0),), 8, 8)


class _Advisor:
    def __init__(self, placement, endpoint, model, api_key):
        self.placement = placement
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key

    def preview(self, image_path, *, note=""):
        from backend.src.core.guidance_vision import DeparturePreview

        leaves = self.placement == "cloud"
        return DeparturePreview(leaves, "api.openai.com" if leaves else "127.0.0.1", ("model", "image", "note"), 12, len(note))

    def observe(self, image_path, *, note="", approved=False):
        from backend.src.core.guidance_vision import VlmObservation

        if self.placement == "cloud" and not approved:
            return VlmObservation("chat", (), "Cloud analysis needs an explicit send approval.")
        if self.api_key:
            assert self.api_key == "abc"
        return VlmObservation("chat", ("flat shading",), None)


def _panel(tmp_path):
    image = tmp_path / "out.png"
    image.write_bytes(b"\x89PNG\r\n")
    panel = ReviewVisionPanel(ocr=_Ocr(), advisor_factory=_Advisor, vault=_Vault())
    panel.set_image(str(image))
    return panel


class _Vault:
    def load_account_credentials(self):
        return {"guidance": {"vlm_api_key": "abc"}}


def test_ocr_button_is_independent_of_the_vlm(tmp_path, q_app):
    panel = _panel(tmp_path)
    panel.read_text()
    panel._thread.join(2)
    q_app.processEvents()
    assert "Hello" in panel._ocr_text.toPlainText()
    assert "(1 boxes)" in panel._ocr_text.toPlainText()
    assert panel._vlm_text.toPlainText() == ""
    panel.deleteLater()


def test_cloud_run_stays_disabled_until_the_preview_is_approved(tmp_path, q_app):
    panel = _panel(tmp_path)
    panel._placement.setCurrentIndex(1)
    panel.preview_departure()
    assert "Would leave this machine" in panel._preview.text()
    assert panel.findChild(QPushButton, "dl_review_vlm_btn").isEnabled() is False
    panel.describe_image()
    assert "approval" in panel._status.text()
    panel.findChild(QCheckBox, "dl_review_vlm_approve").setChecked(True)
    assert panel.findChild(QPushButton, "dl_review_vlm_btn").isEnabled() is True
    panel.describe_image()
    panel._thread.join(2)
    q_app.processEvents()
    assert "flat shading" in panel._vlm_text.toPlainText()
    panel.deleteLater()


def test_empty_review_does_not_start_a_read(q_app):
    panel = ReviewVisionPanel(ocr=_Ocr(), advisor_factory=_Advisor)
    panel.read_text()
    panel.describe_image()
    assert "pin an image" in panel._status.text()
    assert panel._thread is None
    panel.deleteLater()


def test_review_page_hosts_the_ocr_action(q_app):
    from unittest.mock import MagicMock

    from gui.src.tabs.models.dl_workspace_host import _ReviewToolsPage

    page = _ReviewToolsPage(host=MagicMock(), preference_store=None)
    assert page.findChild(QPushButton, "dl_review_ocr_btn") is not None
    assert page.findChild(QLabel, "dl_review_vlm_preview") is not None
    page.deleteLater()
