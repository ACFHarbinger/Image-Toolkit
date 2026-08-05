"""Tests for backend/src/models/core/comfy_manager.py's workflow launch
path (Content Gen §1.4, issue #35): loading curated ControlNet/IP-Adapter
workflow JSON templates, applying generic node-input overrides, uploading
an extra conditioning/reference image, and queuing the resulting prompt
graph to a running ComfyUI server.

The pre-existing ComfyUIManager only started/stopped the server subprocess
and exposed its URL -- there was no HTTP submission mechanism to test
before this. These tests cover the new pure-function pieces (load/apply
overrides) directly, and mock urllib for the network calls (upload_image /
queue_workflow) so no real ComfyUI server is required.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.src.models.core.comfy_manager import WORKFLOWS_DIR, ComfyUIManager


@pytest.fixture
def manager():
    return ComfyUIManager()


class TestLoadWorkflow:
    def test_load_controlnet_template_by_bare_name(self):
        workflow = ComfyUIManager.load_workflow("controlnet_generate.json")
        assert workflow["1"]["class_type"] == "CheckpointLoaderSimple"
        assert workflow["8"]["class_type"] == "ControlNetLoader"
        assert workflow["10"]["class_type"] == "ControlNetApplyAdvanced"

    def test_load_ipadapter_template_by_bare_name(self):
        workflow = ComfyUIManager.load_workflow("ipadapter_generate.json")
        assert workflow["3"]["class_type"] == "IPAdapterModelLoader"
        assert workflow["5"]["class_type"] == "IPAdapterAdvanced"

    def test_load_workflow_by_absolute_path(self):
        path = WORKFLOWS_DIR / "controlnet_generate.json"
        workflow = ComfyUIManager.load_workflow(str(path))
        assert "1" in workflow

    def test_all_curated_templates_are_valid_node_graphs(self):
        """Every node in every curated template must have class_type +
        inputs (the shape ComfyUI's /prompt endpoint requires)."""
        for path in WORKFLOWS_DIR.glob("*.json"):
            workflow = json.loads(path.read_text(encoding="utf-8"))
            assert workflow, f"{path} is empty"
            for node_id, node in workflow.items():
                assert "class_type" in node, f"{path}:{node_id} missing class_type"
                assert "inputs" in node, f"{path}:{node_id} missing inputs"


class TestApplyOverrides:
    def test_overrides_merge_into_matching_node_inputs(self):
        workflow = ComfyUIManager.load_workflow("controlnet_generate.json")
        result = ComfyUIManager.apply_overrides(
            workflow,
            {
                "1": {"ckpt_name": "custom.safetensors"},
                "9": {"image": "uploaded_control.png"},
            },
        )
        assert result["1"]["inputs"]["ckpt_name"] == "custom.safetensors"
        assert result["9"]["inputs"]["image"] == "uploaded_control.png"

    def test_overrides_do_not_mutate_the_original_workflow(self):
        workflow = ComfyUIManager.load_workflow("controlnet_generate.json")
        original_ckpt = workflow["1"]["inputs"]["ckpt_name"]
        ComfyUIManager.apply_overrides(workflow, {"1": {"ckpt_name": "changed.safetensors"}})
        assert workflow["1"]["inputs"]["ckpt_name"] == original_ckpt

    def test_unknown_node_id_in_overrides_is_ignored(self):
        workflow = ComfyUIManager.load_workflow("controlnet_generate.json")
        # Must not raise even though node "999" doesn't exist.
        result = ComfyUIManager.apply_overrides(workflow, {"999": {"foo": "bar"}})
        assert "999" not in result

    def test_empty_overrides_returns_equivalent_copy(self):
        workflow = ComfyUIManager.load_workflow("ipadapter_generate.json")
        result = ComfyUIManager.apply_overrides(workflow, {})
        assert result == workflow
        assert result is not workflow


class TestUploadImage:
    def test_upload_image_posts_multipart_and_returns_server_filename(self, manager, tmp_path):
        img = tmp_path / "control.png"
        img.write_bytes(b"\x89PNG\r\n fake-bytes")

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({"name": "control_00001_.png"}).encode()
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        with patch(
            "backend.src.models.core.comfy_manager.urllib.request.urlopen",
            return_value=fake_response,
        ) as mock_urlopen:
            name = manager.upload_image(str(img))

        assert name == "control_00001_.png"
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == f"{manager.url}/upload/image"
        assert req.get_method() == "POST"

    def test_upload_image_falls_back_to_source_filename_when_name_missing(
        self, manager, tmp_path
    ):
        img = tmp_path / "reference.jpg"
        img.write_bytes(b"fake-jpeg")

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({}).encode()
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        with patch(
            "backend.src.models.core.comfy_manager.urllib.request.urlopen",
            return_value=fake_response,
        ):
            name = manager.upload_image(str(img))

        assert name == "reference.jpg"


class TestQueueWorkflow:
    def test_queue_workflow_posts_prompt_and_returns_prompt_id(self, manager):
        workflow = ComfyUIManager.load_workflow("controlnet_generate.json")

        fake_response = MagicMock()
        fake_response.read.return_value = json.dumps({"prompt_id": "abc-123"}).encode()
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = False

        with patch(
            "backend.src.models.core.comfy_manager.urllib.request.urlopen",
            return_value=fake_response,
        ) as mock_urlopen:
            prompt_id = manager.queue_workflow(workflow)

        assert prompt_id == "abc-123"
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == f"{manager.url}/prompt"
        sent = json.loads(req.data.decode("utf-8"))
        assert sent["prompt"] == workflow

    def test_queue_workflow_raises_runtime_error_on_http_error(self, manager):
        import urllib.error

        workflow = ComfyUIManager.load_workflow("controlnet_generate.json")
        http_error = urllib.error.HTTPError(
            url="http://x/prompt", code=400, msg="Bad Request",
            hdrs=None, fp=MagicMock(read=lambda: b'{"error": "invalid prompt"}'),
        )

        with patch(
            "backend.src.models.core.comfy_manager.urllib.request.urlopen",
            side_effect=http_error,
        ), pytest.raises(RuntimeError, match="ComfyUI rejected the workflow"):
            manager.queue_workflow(workflow)
