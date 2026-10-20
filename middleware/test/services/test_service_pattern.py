"""Tests for Service-layer pattern in middleware/src/services/ (Issue #881, Wave 0e W0-17).

Verifies:
1. Command/Handler pattern contracts and Protocol interfaces.
2. Immutability of Command and Result frozen dataclasses.
3. ConvertService single and batch conversion behavior.
4. Proper validation and error handling via domain exceptions.
5. Dependency injection and composability of handlers.
6. Clean architectural boundaries (no GUI/PySide imports).
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest
from middleware.src.services.base import (
    CommandValidationError,
    Handler,
    ServiceProtocol,
)
from middleware.src.services.convert import (
    BatchConvertCommand,
    BatchConvertHandler,
    ConvertService,
    ConvertServiceProtocol,
    ConvertSingleCommand,
    ConvertSingleHandler,
    ConvertSingleResult,
)
from PIL import Image


def _create_sample_image(
    path: Path, color: tuple[int, int, int] = (255, 0, 0), size: tuple[int, int] = (64, 64)
) -> Path:
    """Helper to create a valid test image."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=color)
    img.save(path)
    return path


class TestServicePatternContracts:
    def test_command_and_result_immutability(self):
        cmd = ConvertSingleCommand(input_path="a.png", output_path="b.jpg")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cmd.output_format = "webp"  # type: ignore

        res = ConvertSingleResult(input_path="a.png", output_path="b.jpg", success=True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            res.success = False  # type: ignore

    def test_service_protocol_conformance(self):
        service = ConvertService()
        assert isinstance(service, ConvertServiceProtocol)
        assert isinstance(service, ServiceProtocol)

    def test_handler_protocol_conformance(self):
        single_h = ConvertSingleHandler()
        batch_h = BatchConvertHandler()
        assert isinstance(single_h, Handler)
        assert isinstance(batch_h, Handler)


class TestConvertServiceOperations:
    def test_convert_single_success(self, tmp_path):
        in_file = _create_sample_image(tmp_path / "input.png", color=(0, 128, 255))
        out_file = tmp_path / "output.jpg"

        service = ConvertService()
        cmd = ConvertSingleCommand(
            input_path=str(in_file),
            output_path=str(out_file),
            output_format="jpg",
            quality=95,
        )

        result = service.convert_single(cmd)
        assert result.success is True
        assert result.error is None
        assert result.size_bytes > 0
        assert result.elapsed_seconds >= 0.0
        assert out_file.exists()

        # Verify output image format
        with Image.open(out_file) as img:
            assert img.format == "JPEG"

    def test_convert_single_missing_input_handled(self, tmp_path):
        service = ConvertService()
        cmd = ConvertSingleCommand(
            input_path=str(tmp_path / "non_existent.png"),
            output_path=str(tmp_path / "output.webp"),
        )
        result = service.convert_single(cmd)
        assert result.success is False
        assert "does not exist" in (result.error or "")

    def test_convert_single_overwrite_protection(self, tmp_path):
        in_file = _create_sample_image(tmp_path / "input.png")
        out_file = _create_sample_image(tmp_path / "output.png", color=(0, 255, 0))

        service = ConvertService()
        cmd = ConvertSingleCommand(
            input_path=str(in_file),
            output_path=str(out_file),
            overwrite=False,
        )
        result = service.convert_single(cmd)
        assert result.success is False
        assert "already exists and overwrite=False" in (result.error or "")

    def test_convert_batch_success(self, tmp_path):
        in_dir = tmp_path / "src_images"
        out_dir = tmp_path / "dest_images"
        in_dir.mkdir()

        # Create 2 valid images and 1 ignored file
        _create_sample_image(in_dir / "img1.png")
        _create_sample_image(in_dir / "img2.jpg")
        (in_dir / "ignore.txt").write_text("not an image")

        service = ConvertService()
        cmd = BatchConvertCommand(
            input_dir=str(in_dir),
            output_dir=str(out_dir),
            output_format="webp",
            input_formats=("png", "jpg"),
        )

        result = service.convert_batch(cmd)
        assert result.total_discovered == 2
        assert result.succeeded == 2
        assert result.failed == 0
        assert len(result.output_paths) == 2
        assert (out_dir / "img1.webp").exists()
        assert (out_dir / "img2.webp").exists()

    def test_convert_batch_missing_directory_raises(self, tmp_path):
        service = ConvertService()
        cmd = BatchConvertCommand(
            input_dir=str(tmp_path / "no_such_directory"),
            output_dir=str(tmp_path / "out"),
        )
        with pytest.raises(CommandValidationError) as exc_info:
            service.convert_batch(cmd)
        assert exc_info.value.details.get("field") == "input_dir"

    def test_custom_handler_injection(self):
        class SpyHandler:
            def __init__(self):
                self.called_with = None

            def handle(self, command: ConvertSingleCommand) -> ConvertSingleResult:
                self.called_with = command
                return ConvertSingleResult(
                    input_path=command.input_path,
                    output_path=command.output_path,
                    success=True,
                )

        spy = SpyHandler()
        service = ConvertService(single_handler=spy)
        cmd = ConvertSingleCommand(input_path="mock_in.png", output_path="mock_out.png")
        res = service.convert_single(cmd)

        assert res.success is True
        assert spy.called_with == cmd


class TestServiceBoundaries:
    def test_no_gui_or_pyside_imports_in_services(self):
        import middleware.src.services.convert  # noqa: F401

        # Ensure no GUI modules were imported into sys.modules by loading services
        assert "PySide6" not in sys.modules
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("gui."):
                pytest.fail(f"Service layer transitively imported GUI module: {mod_name}")


def test_converter_delegates_to_existing_core(tmp_path, monkeypatch):
    from middleware.src.core.image.image_converter import ImageFormatConverter

    source = _create_sample_image(tmp_path / "input.png")
    called = []

    def convert(path, output, **kwargs):
        called.append((path, kwargs))
        Path(output).write_bytes(b"encoded")
        return True

    monkeypatch.setattr(ImageFormatConverter, "convert_single_image", convert)
    result = ConvertService().convert_single(ConvertSingleCommand(str(source), str(tmp_path / "out.png")))
    assert result.success
    assert called == [(str(source), {"format": "png"})]


def test_failed_conversion_preserves_existing_output(tmp_path, monkeypatch):
    from middleware.src.core.image.image_converter import ImageFormatConverter

    source = _create_sample_image(tmp_path / "input.png")
    destination = tmp_path / "output.png"
    destination.write_bytes(b"original")

    def fail(path, output, **kwargs):
        Path(output).write_bytes(b"partial")
        return False

    monkeypatch.setattr(ImageFormatConverter, "convert_single_image", fail)
    result = ConvertService().convert_single(ConvertSingleCommand(str(source), str(destination)))
    assert not result.success
    assert destination.read_bytes() == b"original"


def test_batch_rejects_colliding_output_names(tmp_path):
    source = tmp_path / "in"
    _create_sample_image(source / "same.png")
    _create_sample_image(source / "same.jpg")
    with pytest.raises(CommandValidationError, match="same output"):
        ConvertService().convert_batch(BatchConvertCommand(str(source), str(tmp_path / "out")))


def test_unsupported_quality_is_not_silently_ignored(tmp_path):
    source = _create_sample_image(tmp_path / "input.png")
    with pytest.raises(CommandValidationError, match="quality"):
        ConvertService().convert_single(ConvertSingleCommand(str(source), str(tmp_path / "out.jpg"), quality=75))
