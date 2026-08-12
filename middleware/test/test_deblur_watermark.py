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
    assert proposal.confidence == 0.92  # unchanged default when mask_coverage isn't given


def test_watermark_removal_confidence_scales_with_mask_coverage():
    adapter = WatermarkModel(backend="torch", weights_uri="https://example.com/watermark.pth")

    small = adapter.propose(
        "watermarked.png", mask_ref="logo_mask.png", permission_confirmed=True, mask_coverage=0.02
    )
    large = adapter.propose(
        "watermarked.png", mask_ref="logo_mask.png", permission_confirmed=True, mask_coverage=0.45
    )
    # A small, localized mask (a real logo/watermark) should score higher
    # confidence than a large one (more likely an imprecise selection).
    assert small.confidence > large.confidence
    assert small.payload["mask_coverage"] == 0.02
    assert large.payload["mask_coverage"] == 0.45
    assert 0.5 <= large.confidence <= 0.95
    assert 0.5 <= small.confidence <= 0.95


def test_watermark_removal_rejects_out_of_range_mask_coverage():
    adapter = WatermarkModel(backend="torch", weights_uri="https://example.com/watermark.pth")
    with pytest.raises(ValueError, match="mask_coverage must be between 0 and 1"):
        adapter.propose(
            "watermarked.png", mask_ref="logo_mask.png", permission_confirmed=True, mask_coverage=1.5
        )
    with pytest.raises(ValueError, match="mask_coverage must be between 0 and 1"):
        adapter.propose(
            "watermarked.png", mask_ref="logo_mask.png", permission_confirmed=True, mask_coverage=0.0
        )


def test_watermark_removal_logs_permission_audit_entry(caplog):
    adapter = WatermarkModel(backend="torch", weights_uri="https://example.com/watermark.pth")
    with caplog.at_level("INFO", logger="hie_middleware.watermark_removal.audit"):
        adapter.propose(
            "watermarked.png", mask_ref="logo_mask.png", permission_confirmed=True, mask_coverage=0.1
        )
    assert any("permission confirmed" in record.message for record in caplog.records)
    audit_record = next(r for r in caplog.records if "permission confirmed" in r.message)
    assert audit_record.input_ref == "watermarked.png"
    assert audit_record.mask_ref == "logo_mask.png"


def test_watermark_removal_does_not_log_when_validation_fails():
    adapter = WatermarkModel(backend="torch", weights_uri="https://example.com/watermark.pth")
    import logging

    logger = logging.getLogger("hie_middleware.watermark_removal.audit")
    records = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record)
    logger.addHandler(handler)
    try:
        with pytest.raises(PermissionError):
            adapter.propose("watermarked.png", mask_ref="logo_mask.png", permission_confirmed=False)
    finally:
        logger.removeHandler(handler)
    assert not records
