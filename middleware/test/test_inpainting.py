"""Unit tests for the InpaintingAdapter contract."""

import pytest
from models import InpaintingAdapter, InpaintingModel, ModelUnavailable


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


def _available_adapter() -> InpaintingAdapter:
    return InpaintingAdapter(
        backend="diffusers",
        weights_uri="https://example.com/models/inpainting.safetensors",
    )


def test_inpainting_adapter_accepts_stroke_guided_mask():
    # Raw stroke/point data as an alternative to a precomputed mask_ref -- the
    # UI paints directly on the canvas and the actual rasterization happens
    # downstream, not in this dependency-light contract layer.
    strokes = [{"x": 12, "y": 8, "radius": 6.0}, {"x": 14, "y": 9, "radius": 6.0}]
    proposal = _available_adapter().propose(
        "canvas_frame_01.png", strokes=strokes, mode="inpaint"
    )
    assert proposal.payload["strokes"] == strokes
    assert proposal.payload["mask_ref"] is None


def test_inpainting_adapter_inpaint_requires_mask_or_strokes():
    with pytest.raises(ValueError, match="mask_ref.*strokes|strokes.*mask_ref"):
        _available_adapter().propose("canvas_frame_01.png", mode="inpaint")


def test_inpainting_adapter_outpaint_requires_bbox():
    with pytest.raises(ValueError, match="bbox"):
        _available_adapter().propose("canvas_frame_01.png", mode="outpaint")


@pytest.mark.parametrize("bbox", [(100, 100, 100, 200), (100, 100, 200, 100), (200, 0, 100, 50)])
def test_inpainting_adapter_rejects_degenerate_outpaint_bbox(bbox):
    with pytest.raises(ValueError, match="bbox"):
        _available_adapter().propose("canvas_frame_01.png", bbox=bbox, mode="outpaint")
