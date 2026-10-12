"""Send-to-Upscale handoff wiring ESRGANWrapper into Generate/Review (#749)."""
import threading

import pytest
from backend.src.comfy_matrix import gpu_lease
from PySide6.QtWidgets import QPushButton

from gui.src.tabs.models import upscale_handoff as uh

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _free_lease():
    gpu_lease.release("upscale")
    gpu_lease.release("after-upscale")
    yield
    gpu_lease.release("upscale")
    gpu_lease.release("after-upscale")


def _png_bytes(width=8, height=6):
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage

    img = QImage(width, height, QImage.Format.Format_RGB888)
    img.fill(QColor(16, 32, 64))
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    assert img.save(buf, "PNG")
    return bytes(buf.data())


# ── Pure helpers ──────────────────────────────────────────────────────────


def test_upscaled_output_path_is_sibling_and_never_source():
    out = uh.upscaled_output_path("/tmp/Generated/output.png")
    assert out == "/tmp/Generated/output_upscaled_4x.png"
    assert out != "/tmp/Generated/output.png"


def test_upscaled_output_path_defaults_extension():
    assert uh.upscaled_output_path("/tmp/img") == "/tmp/img_upscaled_4x.png"


def test_decode_image_bytes_roundtrip(q_app):
    data = _png_bytes()
    img = uh.decode_image_bytes(data)
    assert img is not None
    assert img.shape == (6, 8, 3)


def test_decode_image_bytes_rejects_garbage():
    assert uh.decode_image_bytes(b"") is None
    assert uh.decode_image_bytes(b"not-an-image") is None
    assert uh.decode_image_bytes(None) is None


def test_latest_output_paths_single(q_app, tmp_path):
    target = tmp_path / "output.png"
    target.write_bytes(_png_bytes())
    assert uh.latest_output_paths(str(target), 1) == [str(target)]


def test_latest_output_paths_batch_naming(q_app, tmp_path):
    base = tmp_path / "output.png"
    (tmp_path / "output_1.png").write_bytes(_png_bytes())
    (tmp_path / "output_3.png").write_bytes(_png_bytes())
    assert uh.latest_output_paths(str(base), 3) == [str(tmp_path / "output_1.png"), str(tmp_path / "output_3.png")]


def test_latest_output_paths_missing_is_empty(tmp_path):
    assert uh.latest_output_paths(str(tmp_path / "nope.png"), 1) == []


# ── Admission-guarded job ─────────────────────────────────────────────────


def test_run_upscale_file_refuses_without_touching_model(monkeypatch):
    import backend.src.models.wrappers.esrgan_wrapper as esrgan_mod

    touched = []

    class _Boom:
        def __init__(self, *args, **kwargs):
            touched.append(True)

    monkeypatch.setattr(esrgan_mod, "ESRGANWrapper", _Boom)
    assert gpu_lease.try_acquire("matrix")
    try:
        with pytest.raises(RuntimeError, match="matrix"):
            uh.run_upscale_file("/tmp/in.png", "/tmp/out.png")
    finally:
        gpu_lease.release("matrix")
    assert touched == []
    assert gpu_lease.owner is None


def test_run_upscale_file_holds_lease_during_work(monkeypatch, tmp_path):
    import backend.src.models.wrappers.esrgan_wrapper as esrgan_mod

    seen = {}
    src = tmp_path / "in.png"
    src.write_bytes(_png_bytes())
    out = str(tmp_path / "in_upscaled_4x.png")

    class _Fake:
        def upscale_path(self, input_path, output_path):
            seen["owner"] = gpu_lease.owner
            seen["in"] = input_path
            with open(output_path, "wb") as handle:
                handle.write(b"done")

    monkeypatch.setattr(esrgan_mod, "ESRGANWrapper", _Fake)
    assert uh.run_upscale_file(str(src), out) == out
    assert seen == {"owner": "upscale", "in": str(src)}
    assert gpu_lease.owner is None


def test_runner_emits_finished_list(monkeypatch):
    got = {}
    runner = uh.UpscaleRunner()
    runner.finished.connect(lambda paths: got.setdefault("ok", paths))
    runner.error.connect(lambda msg: got.setdefault("err", msg))
    monkeypatch.setattr(
        uh, "run_upscale_file", lambda src, dst: dst + "!"
    )
    runner._run(["/tmp/a.png"])
    assert got == {"ok": ["/tmp/a_upscaled_4x.png!"]}
    runner.deleteLater()


def test_runner_emits_error_and_releases(monkeypatch):
    got = {}
    runner = uh.UpscaleRunner()
    runner.finished.connect(lambda paths: got.setdefault("ok", paths))
    runner.error.connect(lambda msg: got.setdefault("err", msg))

    def _fail(src, dst):
        raise RuntimeError("GPU admission is held by lora-train.")

    monkeypatch.setattr(uh, "run_upscale_file", _fail)
    runner._run(["/tmp/a.png"])
    assert got == {"err": "GPU admission is held by lora-train."}
    runner.deleteLater()


def test_runner_start_refuses_while_busy():
    runner = uh.UpscaleRunner()
    gate = threading.Event()
    runner._run = lambda paths: gate.wait(timeout=10)
    first = runner.start(["/tmp/a.png"])
    assert first is not None
    got = {}
    runner.error.connect(lambda msg: got.setdefault("err", msg))
    assert runner.start(["/tmp/b.png"]) is None
    assert got == {"err": "An upscale job is already running."}
    gate.set()
    first.join(timeout=10)
    runner.deleteLater()


# ── Surface wiring ────────────────────────────────────────────────────────


def test_lora_generate_tab_has_upscale_action(q_app):
    from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab

    tab = LoRAGenerateTab()
    button = tab.findChild(QPushButton, "lora_upscale_btn")
    assert button is not None
    assert button.text() == "Upscale Output"
    tab.deleteLater()


def test_lora_upscale_reports_missing_output(q_app, monkeypatch, tmp_path):
    from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab

    tab = LoRAGenerateTab()
    missing = str(tmp_path / "nothing.png")
    tab.widgets["output_filename"].setText(missing)
    messages = []
    monkeypatch.setattr(
        "gui.src.tabs.models.gen.lora_generate_tab.QMessageBox.information",
        lambda *args, **kwargs: messages.append(args),
    )
    started = tab.start_upscale()
    assert started is False
    assert messages
    tab.deleteLater()


def test_generate_surface_upscale_needs_selection(q_app):
    from unittest.mock import MagicMock

    from backend.src.constants.comfy import ServerState

    from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController
    from gui.src.tabs.models.gen.generate_surface import GenerateSurface

    manager = MagicMock(state=ServerState.STOPPED, owns_server=False, port=8188)
    manager.runs.return_value = ()
    manager.get_object_info.return_value = None
    controller = ComfyWorkspaceController(manager=manager)
    surface = GenerateSurface(controller=controller)
    assert surface.findChild(QPushButton, "generate_upscale_selected") is not None
    surface._on_upscale_selected()
    assert "Select a run" in surface._upscale_message.text()
    surface.close()
    controller.shutdown()


def test_generate_surface_upscale_finished_lands_in_filmstrip(q_app, tmp_path):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from backend.src.constants.comfy import ServerState

    from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController
    from gui.src.tabs.models.gen.generate_surface import GenerateSurface

    manager = MagicMock(state=ServerState.STOPPED, owns_server=False, port=8188)
    manager.runs.return_value = ()
    manager.get_object_info.return_value = None
    controller = ComfyWorkspaceController(manager=manager)
    surface = GenerateSurface(controller=controller)
    record = SimpleNamespace(
        prompt_id="abc123",
        status="done",
        surface_mode="guided",
        outputs=(),
        workflow=None,
    )
    surface._filmstrip.upsert(record)
    out = tmp_path / "abc123_upscaled_4x.png"
    out.write_bytes(_png_bytes())
    surface._upscale_source_id = "abc123"
    surface._on_upscale_finished([str(out)])
    derived = surface._filmstrip.selected_record()
    assert derived is not None
    assert getattr(derived, "prompt_id", "") == "abc123_upscaled"
    assert getattr(derived, "local_output_path", "") == str(out)
    surface.close()
    controller.shutdown()


def test_review_upscale_button_present_and_empty_safe(q_app):
    from unittest.mock import MagicMock

    from gui.src.tabs.models.dl_workspace_host import _ReviewToolsPage

    page = _ReviewToolsPage(host=MagicMock(), preference_store=None)
    button = page.findChild(QPushButton, "dl_review_upscale_btn")
    assert button is not None
    page._on_upscale()
    assert "No output" in page._upscale_status.text()
    page.deleteLater()


def test_review_upscale_finished_appends_result(q_app, tmp_path):
    from unittest.mock import MagicMock

    from gui.src.tabs.models.dl_workspace_host import _ReviewToolsPage

    page = _ReviewToolsPage(host=MagicMock(), preference_store=None)
    src = tmp_path / "gen.png"
    src.write_bytes(_png_bytes())
    out = tmp_path / "gen_upscaled_4x.png"
    out.write_bytes(_png_bytes())
    page.set_compare_paths([str(src)])
    page._on_upscale_finished([str(out)])
    assert page._compare_paths == [str(src), str(out)]
    page.deleteLater()


@pytest.mark.parametrize("width", [1, 2, 3, 5, 7])
def test_decoder_handles_qimage_row_padding(q_app, width):
    image = uh.decode_image_bytes(_png_bytes(width=width, height=3))
    assert image.shape == (3, width, 3)
    assert tuple(image[0, 0]) == (64, 32, 16)


def test_upscale_does_not_overwrite_existing_output(tmp_path):
    source = tmp_path / "image.png"
    source.write_bytes(_png_bytes())
    output = tmp_path / "image_upscaled_4x.png"
    output.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        uh.run_upscale_file(str(source), str(output))
    assert output.read_bytes() == b"keep"
    assert uh.upscaled_output_path(str(source)).endswith("_upscaled_4x_2.png")


def test_remote_upscale_fetches_off_thread_and_uses_png_snapshot(q_app, tmp_path, monkeypatch):
    from PySide6.QtTest import QTest

    calls = []
    runner = uh.UpscaleRunner()
    done = []
    runner.finished.connect(done.extend)

    def fetch(*args):
        calls.append(threading.current_thread() is not threading.main_thread())
        return _png_bytes(width=5)

    def upscale(src, dst):
        with open(src, "rb") as stream:
            assert uh.decode_image_bytes(stream.read()).shape == (6, 5, 3)
        return dst

    monkeypatch.setattr(uh, "run_upscale_file", upscale)
    worker = runner.start_remote(fetch, "a.png", "", "temp", str(tmp_path))
    worker.join(2)
    QTest.qWait(50)
    assert calls == [True] and done
    runner.deleteLater()


def test_lora_upscale_result_appears_beside_its_source(q_app, tmp_path):
    from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab

    tab = LoRAGenerateTab()
    source = tmp_path / "source.png"
    output = tmp_path / "source_upscaled_4x.png"
    source.write_bytes(_png_bytes())
    output.write_bytes(_png_bytes())
    tab._show_output_paths([str(source)], "generated")
    tab.handle_upscale_finished([str(output)])
    strip = tab._output_filmstrip
    assert strip.selected_record().local_output_path == str(output)
    assert set(strip._records) == {str(source), str(output)}
    tab.deleteLater()
