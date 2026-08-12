"""Unit tests for DeblurAdapter and WatermarkRemovalAdapter model contracts."""

import pytest
from hie_middleware.models import (
    DeblurAdapter,
    DeblurModel,
    ModelUnavailable,
    WatermarkModel,
    WatermarkRemovalAdapter,
)


def test_deblur_adapter_method_validation():
    with pytest.raises(ValueError, match="deblur method must be 'blind' or 'non_blind'"):
        DeblurAdapter(method="invalid")


def test_deblur_adapter_available_propose():
    adapter = DeblurModel(
        backend="torch",
        weights_uri="https://example.com/deblur.pth",
        method="blind",
    )
    assert adapter.is_available()

    proposal = adapter.propose(
        "blurry_canvas.png",
        kernel_size=17,
        strength=1.2,
        psf_estimate="motion_blur_45deg",
    )

    assert proposal.operation == "deblur"
    assert proposal.confidence == 0.9
    assert proposal.payload["kernel_size"] == 17
    assert proposal.payload["strength"] == 1.2
    assert proposal.payload["psf_estimate"] == "motion_blur_45deg"


def test_deblur_adapter_parameter_validation():
    adapter = DeblurModel(
        backend="torch",
        weights_uri="https://example.com/deblur.pth",
    )
    with pytest.raises(ValueError, match="kernel_size must be an odd integer >= 3"):
        adapter.propose("canvas.png", kernel_size=4)

    with pytest.raises(ValueError, match="strength must be between 0.0 and 2.0"):
        adapter.propose("canvas.png", strength=3.0)


def test_watermark_removal_adapter_consent_and_mask_validation():
    adapter = WatermarkModel(
        backend="torch",
        weights_uri="https://example.com/watermark.pth",
    )
    assert adapter.is_available()

    with pytest.raises(ValueError, match="watermark inpainting requires a user-supplied mask_ref"):
        adapter.propose("watermarked.png", mask_ref="", permission_confirmed=True)

    with pytest.raises(PermissionError, match="confirm ownership or permission before removal"):
        adapter.propose("watermarked.png", mask_ref="logo_mask.png", permission_confirmed=False)

    proposal = adapter.propose(
        "watermarked.png",
        mask_ref="logo_mask.png",
        permission_confirmed=True,
        edge_blur=4,
    )

    assert proposal.operation == "masked_inpainting"
    assert proposal.payload["mask_ref"] == "logo_mask.png"
    assert proposal.payload["edge_blur"] == 4
