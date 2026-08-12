"""Unit tests for the InpaintingAdapter contract."""

import pytest
from hie_middleware.models import InpaintingAdapter, InpaintingModel, ModelUnavailable


def test_inpainting_adapter_default_unavailable():
    adapter = InpaintingAdapter()
    assert not adapter.is_available()
    assert adapter.spec.name == "neural-inpainting"
    assert adapter.spec.task == "inpainting_outpainting"

    with pytest.raises(ModelUnavailable):
        adapter.propose("test_input.png")


def test_inpainting_adapter_available_propose_inpaint():
    adapter = InpaintingAdapter(
        backend="diffusers",
        weights_uri="https://example.com/models/inpainting.safetensors",
        model_variant="sd-inpainting-v2",
    )
    assert adapter.is_available()

    proposal = adapter.propose(
        input_ref="canvas_frame_01.png",
        mask_ref="stroke_mask_01.png",
        prompt="remove background object",
        bbox=(10, 10, 200, 200),
        mode="inpaint",
    )

    assert proposal.operation == "neural_inpaint"
    assert proposal.payload["input_ref"] == "canvas_frame_01.png"
    assert proposal.payload["mask_ref"] == "stroke_mask_01.png"
    assert proposal.payload["prompt"] == "remove background object"
    assert proposal.payload["bbox"] == (10, 10, 200, 200)
    assert proposal.payload["mode"] == "inpaint"


def test_inpainting_adapter_propose_outpaint():
    adapter = InpaintingAdapter(
        backend="diffusers",
        weights_uri="https://example.com/models/outpainting.safetensors",
    )
    proposal = adapter.propose(
        input_ref="canvas_frame_01.png",
        bbox=(-50, -50, 800, 600),
        mode="outpaint",
    )
    assert proposal.operation == "neural_outpaint"
    assert proposal.payload["mode"] == "outpaint"


def test_inpainting_adapter_invalid_mode():
    adapter = InpaintingAdapter(
        backend="diffusers",
        weights_uri="https://example.com/models/inpainting.safetensors",
    )
    with pytest.raises(ValueError, match="Invalid mode"):
        adapter.propose("input.png", mode="invalid_mode")


def test_inpainting_model_alias():
    model = InpaintingModel(
        backend="diffusers",
        weights_uri="https://example.com/models/inpainting.safetensors",
    )
    assert isinstance(model, InpaintingAdapter)
