"""#481: Tier-2 heavy CV/torch/ffmpeg workers run under the cyclic-GC guard.

The #478/#480 crash class (process-global cyclic GC tripped on a worker
thread finalizes a collectable QWidget off the GUI thread → SIGSEGV)
applies to every heavy-allocating worker, not just the JSON/listing set
already guarded. Every Tier-2 worker's ``run()`` must carry
``@gc_disabled_run`` (outermost, above any ``@Slot()``).

Two layers, mirroring the #478/#480 test pattern:

- a parametrized static check over the full Tier-2 registry (a bare
  ``run()`` re-appearing on any of these classes is the regression), and
- dynamic signal-probe tests: run a worker directly on the test thread
  down a quick deterministic path and record ``gc.isenabled()`` inside a
  slot fired *during* ``run()`` — the emission happens inside the guard.
"""

from __future__ import annotations

import gc
import importlib

import pytest
from gui.src.helpers.gc_safe import gc_disabled_run

# All applications of the decorator share one closure code object, so this
# is a cheap identity check that a run() is *the* guard's wrapper.
_GUARD_CODE = gc_disabled_run(lambda: None).__code__

TIER2_WORKERS = [
    # core
    ("gui.src.helpers.core.conversion_worker", "ConversionWorker"),
    ("gui.src.helpers.core.codec_conversion_worker", "CodecConversionWorker"),
    ("gui.src.helpers.core.video_export_worker", "ScrollVideoExportWorker"),
    ("gui.src.helpers.core.deletion_worker", "DeletionWorker"),
    ("gui.src.helpers.core.merge_worker", "MergeWorker"),
    ("gui.src.helpers.core.sampler_worker", "SamplerWorker"),
    ("gui.src.helpers.core.similarity_scan_worker", "SimilarityScanWorker"),
    ("gui.src.helpers.core.duplicate_scan_worker", "DuplicateScanWorker"),
    ("gui.src.helpers.core.queue_execution_worker", "QueueExecutionWorker"),
    ("gui.src.helpers.core.wallpaper_worker", "WallpaperWorker"),
    # core/tasks
    ("gui.src.helpers.core.tasks.orb_task", "OrbTask"),
    ("gui.src.helpers.core.tasks.sift_task", "SiftTask"),
    ("gui.src.helpers.core.tasks.ssim_task", "SsimTask"),
    ("gui.src.helpers.core.tasks.phask_task", "PhashTask"),
    ("gui.src.helpers.core.tasks.sn_task", "SiameseTask"),
    # video
    ("gui.src.helpers.video.storyboard", "StoryboardBuilder"),
    ("gui.src.helpers.video.video_scan_worker", "VideoScannerWorker"),
    ("gui.src.helpers.video.codec_scan_worker", "CodecScanWorker"),
    ("gui.src.helpers.video.video_loader_worker", "VideoLoaderWorker"),
    ("gui.src.helpers.video.batch_video_loader_worker", "BatchVideoLoaderWorker"),
    ("gui.src.helpers.video.frame_extractor_worker", "FrameExtractionWorker"),
    ("gui.src.helpers.video.gif_extractor_worker", "GifCreationWorker"),
    ("gui.src.helpers.video.video_extractor_worker", "VideoExtractionWorker"),
    # image
    ("gui.src.helpers.image.image_loader_worker", "ImageLoaderWorker"),
    # database
    ("gui.src.helpers.database.embedding_worker", "ImageEmbeddingWorker"),
    ("gui.src.helpers.database.listings_embedding_worker", "ListingsEmbeddingWorker"),
    # web
    ("gui.src.helpers.web.recon_worker", "IndexBuildWorker"),
    ("gui.src.helpers.web.recon_worker", "ResolveWorker"),
    ("gui.src.helpers.web.recon_worker", "BatchSuggestWorker"),
    ("gui.src.helpers.web.reverse_search_worker", "ReverseSearchWorker"),
    # models
    ("gui.src.helpers.models.training_worker", "TrainingWorker"),
    ("gui.src.helpers.models.lora_training_worker", "LoRATrainingWorker"),
    ("gui.src.helpers.models.tag_review_worker", "TagReviewWorker"),
    # components
    ("gui.src.components.dialogs.frame_selection_dialog", "_FrameWorker"),
    # ASP submodule (asp_gui alias — see git/scripts/_submodule_bootstrap.py)
    ("asp_gui.helpers.stitch_worker", "StitchWorker"),
    ("asp_gui.helpers.graph_stitch_worker", "GraphStitchWorker"),
    ("asp_gui.helpers.batch_stitch_worker", "BatchStitchWorker"),
    ("asp_gui.helpers.mask_preview_worker", "MaskPreviewWorker"),
]


@pytest.mark.parametrize(("module_name", "class_name"), TIER2_WORKERS)
def test_run_is_gc_guarded(module_name: str, class_name: str):
    module = importlib.import_module(module_name)
    klass = getattr(module, class_name)
    run = klass.__dict__.get("run")
    assert run is not None, f"{class_name} must define its own run()"
    assert run.__code__ is _GUARD_CODE, (
        f"{class_name}.run must be wrapped by @gc_disabled_run (#478/#481 "
        "crash class: cyclic GC on a worker thread finalizes QWidgets "
        "off the GUI thread)"
    )


class _GcProbe:
    """Records gc.isenabled() the moment a Qt signal fires during run()."""

    def __init__(self) -> None:
        self.seen: dict[str, bool] = {}

    def slot(self, *args: object) -> None:
        self.seen["enabled_during"] = gc.isenabled()


def _run_and_probe(worker, signal) -> _GcProbe:
    probe = _GcProbe()
    signal.connect(probe.slot)
    assert gc.isenabled(), "test precondition: GC starts enabled"
    worker.run()  # directly, on the test thread — same as the #478 test
    assert gc.isenabled(), "GC must be restored after run()"
    return probe


def test_conversion_worker_quick_error_path_runs_gced(tmp_path):
    from gui.src.helpers.core.conversion_worker import ConversionWorker

    w = ConversionWorker({})  # no files → error_signal "No files to convert."
    probe = _run_and_probe(w, w.error_signal)
    assert probe.seen.get("enabled_during") is False


def test_merge_worker_error_path_runs_gced():
    from gui.src.helpers.core.merge_worker import MergeWorker

    w = MergeWorker({})  # missing output_path → caught → error.emit
    probe = _run_and_probe(w, w.error)
    assert probe.seen.get("enabled_during") is False


def test_deletion_worker_missing_target_runs_gced(tmp_path):
    from gui.src.helpers.core.deletion_worker import DeletionWorker

    w = DeletionWorker(
        {
            "target_path": str(tmp_path / "does-not-exist"),
            "mode": "files",
            "require_confirm": False,
            "target_extensions": None,
        }
    )
    probe = _run_and_probe(w, w.error)
    assert probe.seen.get("enabled_during") is False


def test_sampler_worker_empty_config_runs_gced():
    from gui.src.helpers.core.sampler_worker import SamplerWorker

    w = SamplerWorker({})
    probe = _run_and_probe(w, w.error)
    assert probe.seen.get("enabled_during") is False


def test_storyboard_builder_zero_duration_runs_gced(tmp_path):
    from gui.src.helpers.video.storyboard import StoryboardBuilder

    video = tmp_path / "v.mp4"
    video.write_bytes(b"0")  # _cache_dir_for() os.stat()s it; never decoded
    w = StoryboardBuilder(str(video), duration_ms=0)
    probe = _run_and_probe(w, w.failed)  # "Unknown video duration."
    assert probe.seen.get("enabled_during") is False


def test_video_scanner_worker_no_dirs_runs_gced(tmp_path):
    from gui.src.helpers.video.video_scan_worker import VideoScannerWorker

    w = VideoScannerWorker([str(tmp_path / "missing")])  # filtered → empty
    probe = _run_and_probe(w, w.scan_error)
    assert probe.seen.get("enabled_during") is False


def test_codec_scan_worker_empty_batch_runs_gced():
    from gui.src.helpers.video.codec_scan_worker import CodecScanWorker

    w = CodecScanWorker([])
    probe = _run_and_probe(w, w.signals.finished)
    assert probe.seen.get("enabled_during") is False


def test_queue_execution_worker_empty_queue_runs_gced():
    from gui.src.helpers.core.queue_execution_worker import QueueExecutionWorker

    w = QueueExecutionWorker([])
    probe = _run_and_probe(w, w.signals.started)
    assert probe.seen.get("enabled_during") is False


def test_duplicate_scan_worker_all_files_empty_dir_runs_gced(tmp_path):
    from gui.src.helpers.core.duplicate_scan_worker import DuplicateScanWorker

    w = DuplicateScanWorker(str(tmp_path), [".png"], "all_files", recursive=False)
    probe = _run_and_probe(w, w.finished)
    assert probe.seen.get("enabled_during") is False


def test_phash_task_runs_gced(tmp_path):
    from gui.src.helpers.core.tasks.phask_task import PhashTask
    from PIL import Image

    img = tmp_path / "img.png"
    Image.new("RGB", (8, 8), "red").save(img)
    t = PhashTask(str(img))
    probe = _run_and_probe(t, t.signals.result)
    assert probe.seen.get("enabled_during") is False


def test_frame_worker_runs_gced(monkeypatch, tmp_path):
    frame_selection_dialog = importlib.import_module(
        "gui.src.components.dialogs.frame_selection_dialog"
    )

    seen = {}

    def _fake_extract(video_path, frame_idx, total_frames, fps):
        seen["enabled_during"] = gc.isenabled()
        return None  # → failed.emit

    monkeypatch.setattr(
        frame_selection_dialog, "extract_video_frame_via_ffmpeg", _fake_extract
    )
    w = frame_selection_dialog._FrameWorker(str(tmp_path / "v.mp4"), 0, 10, 24.0)
    probe = _run_and_probe(w, w.signals.failed)
    assert probe.seen.get("enabled_during") is False
    assert seen.get("enabled_during") is False


def test_graph_stitch_worker_empty_plan_runs_gced():
    from asp_gui.helpers.graph_stitch_worker import GraphStitchWorker

    w = GraphStitchWorker([], {})
    probe = _run_and_probe(w, w.sig_finished)
    assert probe.seen.get("enabled_during") is False


def test_batch_stitch_worker_empty_dir_runs_gced(tmp_path):
    from asp_gui.helpers.batch_stitch_worker import BatchStitchWorker

    w = BatchStitchWorker(str(tmp_path))  # no subdirs → sig_batch_finished
    probe = _run_and_probe(w, w.sig_batch_finished)
    assert probe.seen.get("enabled_during") is False
