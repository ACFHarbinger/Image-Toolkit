"""End-to-end ReconEngine + DatasetIndexer + provenance export tests."""

import os

import cv2
import numpy as np
import pytest

pytest.importorskip("base")

from backend.src.web.recon import (  # noqa: E402
    DatasetIndexer,
    ReconConfig,
    ReconEngine,
    export_provenance,
)
from backend.src.web.recon.provenance import ProvenanceEntry, ProvenanceReport  # noqa: E402
from backend.src.web.recon.segmenter import alpha_cutout, cutout_to_png_bytes  # noqa: E402


def _person_image(kind, seed):
    rng = np.random.default_rng(seed)
    img = np.zeros((128, 128, 3), np.uint8)
    if kind == "John_Doe":
        img[:64, :] = (200, 30, 30)
        cv2.circle(img, (64, 96), 28, (255, 255, 255), -1)
    elif kind == "Jane_Smith":
        img[:, :64] = (30, 200, 30)
        cv2.rectangle(img, (72, 20), (110, 100), (255, 255, 0), -1)
    else:
        img[64:, :] = (30, 30, 200)
        cv2.line(img, (0, 0), (127, 60), (255, 255, 255), 6)
    return cv2.add(img, rng.integers(0, 8, (128, 128, 3), dtype=np.uint8))


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / "dataset"
    for name in ["John_Doe", "Jane_Smith", "Bob_Lee"]:
        d = root / name
        d.mkdir(parents=True)
        for i in range(3):
            cv2.imwrite(str(d / f"{i}.png"), _person_image(name, hash((name, i)) % 997))
    return root


def _config(root, tmp_path):
    return ReconConfig(
        dataset_root=str(root), embed_mode="clip", cache_path=":memory:",
        local_match_threshold=0.5, privacy_mode=True,
    )


class TestIndexing:
    def test_labels_from_directory(self, dataset, tmp_path):
        idxr = DatasetIndexer(_config(dataset, tmp_path))
        idxr.build()
        assert idxr.stats["labels"] == 3
        assert idxr.stats["indexed"] == 9

    def test_root_level_images_ignored(self, dataset, tmp_path):
        # An image directly in the root has no identity folder → skipped.
        cv2.imwrite(str(dataset / "loose.png"), _person_image("John_Doe", 1))
        idxr = DatasetIndexer(_config(dataset, tmp_path))
        idxr.build()
        assert idxr.stats["indexed"] == 9   # loose.png excluded


class TestResolution:
    def test_local_identity_match(self, dataset, tmp_path):
        cfg = _config(dataset, tmp_path)
        idxr = DatasetIndexer(cfg)
        idxr.build()
        eng = ReconEngine(cfg, indexer=idxr)

        q = cv2.cvtColor(_person_image("Jane_Smith", 555), cv2.COLOR_BGR2RGB)
        png = cutout_to_png_bytes(alpha_cutout(q, np.full((128, 128), 255, np.uint8)))
        res = eng.resolve(q, png)
        assert res.origin == "local"
        assert res.name == "Jane Smith"
        assert res.report.predicted_name == "Jane Smith"

    def test_privacy_mode_blocks_web(self, tmp_path):
        # Empty index → no local match; local-only scope → must not go to web.
        cfg = ReconConfig(dataset_root=str(tmp_path / "empty"), embed_mode="clip",
                          cache_path=":memory:", privacy_mode=True)
        (tmp_path / "empty").mkdir()
        idxr = DatasetIndexer(cfg)
        idxr.build()
        eng = ReconEngine(cfg, indexer=idxr)
        q = cv2.cvtColor(_person_image("John_Doe", 7), cv2.COLOR_BGR2RGB)
        png = cutout_to_png_bytes(alpha_cutout(q, np.full((128, 128), 255, np.uint8)))
        res = eng.resolve(q, png)
        assert res.origin == "none"
        assert "web disabled" in res.method.lower()

    def test_web_only_scope_skips_local(self, dataset, tmp_path):
        # Web-only scope must not report a local match even when the index would
        # match; with the stub dispatcher (no hits) it falls through to "none".
        from backend.src.web.recon.config import SCOPE_WEB

        cfg = _config(dataset, tmp_path)
        cfg.search_scope = SCOPE_WEB
        cfg.privacy_mode = False
        idxr = DatasetIndexer(cfg)
        idxr.build()
        eng = ReconEngine(cfg, indexer=idxr)
        q = cv2.cvtColor(_person_image("John_Doe", 7), cv2.COLOR_BGR2RGB)
        png = cutout_to_png_bytes(alpha_cutout(q, np.full((128, 128), 255, np.uint8)))
        res = eng.resolve(q, png)
        assert res.origin != "local"
        assert res.local_matches == []

    def test_legacy_privacy_false_enables_web_scope(self):
        # A persisted config without search_scope should derive it from the
        # legacy privacy_mode flag (False → both, so web is not lost).
        from backend.src.web.recon.config import SCOPE_BOTH

        cfg = ReconConfig.from_dict({"privacy_mode": False})
        assert cfg.search_scope == SCOPE_BOTH

    def test_batch_suggestions(self, dataset, tmp_path):
        cfg = _config(dataset, tmp_path)
        idxr = DatasetIndexer(cfg)
        idxr.build()
        eng = ReconEngine(cfg, indexer=idxr)
        paths = [str(dataset / "Bob_Lee" / "0.png")]
        suggestions = eng.suggest_batch(paths)
        assert suggestions[0]["suggested_label"] == "Bob_Lee"


class TestExport:
    def test_json_and_csv(self, tmp_path):
        rep = ProvenanceReport(predicted_name="John Doe", confidence=0.91,
                               method="Web Consensus", query_hash="abc123")
        rep.add(ProvenanceEntry(kind="web", label="John Doe",
                                source="https://reddit.com/x", domain="reddit.com",
                                score=0.91, method="Yandex -> Web"))
        pj = export_provenance(rep, str(tmp_path / "r.json"))
        pc = export_provenance(rep, str(tmp_path / "r.csv"))
        assert os.path.getsize(pj) > 0
        assert os.path.getsize(pc) > 0
        import json
        with open(pj) as f:
            data = json.load(f)
        assert data["predicted_name"] == "John Doe"
        assert data["entries"][0]["domain"] == "reddit.com"
