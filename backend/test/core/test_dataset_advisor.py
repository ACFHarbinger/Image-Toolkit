"""Dataset advisor (#744): deterministic scan, tag entanglement, and
diversity clustering over synthetic PIL images / numpy embeddings.

No models, GPU, or database — everything runs on tmp_path fixtures.
"""
from pathlib import Path

import numpy as np

import backend.src.core.dataset_advisor as dataset_advisor
from backend.src.core.dataset_advisor import (
    ACTION_EXCLUDE,
    ACTION_HYDRA,
    ACTION_SELECT,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    analyze_diversity,
    scan_dataset,
)


def _img(path: Path, size=(64, 64), color=(120, 40, 200)) -> Path:
    from PIL import Image

    Image.new("RGB", size, color).save(path)
    return path


def _caption(path: Path, text: str) -> Path:
    sidecar = path.with_suffix(".txt")
    sidecar.write_text(text, encoding="utf-8")
    return sidecar


def _finding(report, category):
    return next((f for f in report.findings if f.category == category), None)


# ---------------------------------------------------------------------------
# Deterministic scan
# ---------------------------------------------------------------------------


def test_clean_dataset_reports_nothing(tmp_path):
    paths = [
        _img(tmp_path / f"char_{i:03}.png", color=(120, 40, i * 30 + 1))
        for i in range(6)
    ]
    for p in paths:
        _caption(p, "1girl, mychar")
    report = scan_dataset([str(p) for p in paths], trigger="mychar")
    assert report.findings == ()
    assert report.summary.image_count == 6
    assert report.summary.caption_coverage == 1.0
    assert report.summary.scene_count == 1  # char_000..005 group as one scene


def test_unreadable_file_is_flagged_with_show_action(tmp_path):
    good = _img(tmp_path / "good.png")
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not an image at all")
    report = scan_dataset([str(good), str(bad)])
    finding = _finding(report, "unreadable")
    assert finding is not None
    assert finding.severity == SEVERITY_WARNING
    assert finding.action == ACTION_SELECT
    assert str(bad) in finding.paths
    assert report.summary.image_count == 1


def test_missing_and_empty_captions_count_as_missing(tmp_path):
    a = _img(tmp_path / "a.png")
    b = _img(tmp_path / "b.png")
    _caption(a, "")  # empty sidecar counts as missing
    report = scan_dataset([str(a), str(b)])
    finding = _finding(report, "captions")
    assert finding is not None and finding.action == ACTION_HYDRA
    assert finding.action_payload == "pipeline.run_captioning=true"
    assert set(finding.paths) == {str(a), str(b)}
    assert report.summary.caption_coverage == 0.0


def test_extreme_aspect_ratio_is_flagged(tmp_path):
    wide = _img(tmp_path / "wide.png", size=(200, 60))
    normal = _img(tmp_path / "normal.png", size=(64, 64))
    report = scan_dataset([str(wide), str(normal)])
    finding = _finding(report, "aspects")
    assert finding is not None and str(wide) in finding.paths
    assert finding.action == ACTION_SELECT


def test_exact_duplicates_across_scenes_are_excludable(tmp_path):
    a = _img(tmp_path / "a.png", color=(10, 10, 10))
    b = _img(tmp_path / "b.png", color=(10, 10, 10))
    c = _img(tmp_path / "c.png", color=(250, 250, 250))
    report = scan_dataset([str(a), str(b), str(c)])
    finding = _finding(report, "duplicates")
    assert finding is not None
    assert finding.action == ACTION_EXCLUDE
    assert set(finding.paths) == {str(a), str(b)}
    assert finding.action_label == "Exclude 1 duplicate(s)"


def test_identical_frames_within_one_scene_are_a_burst_not_duplicates(tmp_path):
    f1 = _img(tmp_path / "clip_001.png", color=(5, 5, 5))
    f2 = _img(tmp_path / "clip_002.png", color=(5, 5, 5))
    other = _img(tmp_path / "other.png", color=(200, 200, 200))
    report = scan_dataset([str(f1), str(f2), str(other)])
    assert _finding(report, "duplicates") is None
    burst = _finding(report, "frames")
    assert burst is not None and burst.severity == SEVERITY_INFO
    assert set(burst.paths) == {str(f1), str(f2)}
    # the burst scene plus the standalone file
    assert report.summary.scene_count == 2


def test_progress_and_cancel_are_honored(tmp_path):
    paths = [_img(tmp_path / f"i{i}.png") for i in range(20)]
    seen = []
    report = scan_dataset([str(p) for p in paths], progress=lambda done, total: seen.append((done, total)))
    assert seen and seen[-1] == (20, 20)

    calls = {"n": 0}

    def cancel_after_two():
        calls["n"] += 1
        return calls["n"] > 2

    report = scan_dataset([str(p) for p in paths], cancel=cancel_after_two)
    assert report.summary.image_count < 20


def test_hash_cache_avoids_rehashing(tmp_path, monkeypatch):
    p = _img(tmp_path / "a.png")
    cache = {}
    scan_dataset([str(p)], hash_cache=cache)
    assert str(p) in cache

    probes = {"n": 0}
    original = dataset_advisor._probe

    def counting_probe(path):
        probes["n"] += 1
        return original(path)

    monkeypatch.setattr(dataset_advisor, "_probe", counting_probe)
    scan_dataset([str(p)], hash_cache=cache)
    assert probes["n"] == 0  # mtime+size match → cache hit

    _img(tmp_path / "a.png", color=(1, 2, 3))  # same size? force new file
    if (tmp_path / "a.png").stat().st_size == cache[str(p)][1]:
        _img(tmp_path / "a.png", size=(65, 65))
    scan_dataset([str(p)], hash_cache=cache)
    assert probes["n"] == 1  # changed file → re-probed


# ---------------------------------------------------------------------------
# Tag co-occurrence (Gemini's entanglement formula)
# ---------------------------------------------------------------------------


def _tagged_dataset(tmp_path, captions):
    paths = []
    for i, text in enumerate(captions):
        p = _img(tmp_path / f"d{i}.png")
        _caption(p, text)
        paths.append(p)
    return paths


def test_entanglement_flags_tag_always_with_trigger(tmp_path):
    paths = _tagged_dataset(
        tmp_path,
        ["mychar, school_uniform, 1girl"] * 10 + ["mychar, 1girl"] * 5,
    )
    report = scan_dataset([str(p) for p in paths], trigger="mychar")
    findings = [f for f in report.findings if f.category == "cooccurrence"]
    finding = next(f for f in findings if "'school_uniform'" in f.title)
    assert finding.severity == SEVERITY_WARNING
    assert "100%" in finding.title  # 10/10 school_uniform images carry the trigger
    assert finding.action is None  # no honest one-click fix → no button
    # "1girl" is on every image — ubiquitous-tag guard keeps it quiet
    assert all("'1girl'" not in f.title for f in findings)


def test_entanglement_ignores_rare_tags_and_mixed_usage(tmp_path):
    # school_uniform also appears in 10 non-trigger images: P(trigger|uniform)=10/20
    paths = _tagged_dataset(
        tmp_path,
        ["mychar, school_uniform"] * 10 + ["school_uniform, outdoors"] * 10,
    )
    report = scan_dataset([str(p) for p in paths], trigger="mychar")
    assert _finding(report, "cooccurrence") is None


def test_trigger_support_too_low_is_informational(tmp_path):
    paths = _tagged_dataset(tmp_path, ["mychar, hat"] * 3 + ["1girl"] * 4)
    report = scan_dataset([str(p) for p in paths], trigger="mychar")
    finding = _finding(report, "cooccurrence")
    assert finding is not None and finding.severity == SEVERITY_INFO
    assert "below" in finding.title


def test_trigger_missing_or_unset_is_informational(tmp_path):
    paths = _tagged_dataset(tmp_path, ["1girl, hat"] * 6)
    report = scan_dataset([str(p) for p in paths], trigger="mychar")
    assert "not found" in _finding(report, "cooccurrence").title
    report = scan_dataset([str(p) for p in paths], trigger="")
    assert "not set" in _finding(report, "cooccurrence").title


# ---------------------------------------------------------------------------
# CLIP diversity clustering (synthetic embeddings)
# ---------------------------------------------------------------------------


def _unit(seed_dir: int, dim: int = 16) -> np.ndarray:
    rng = np.random.default_rng(seed_dir)
    v = rng.normal(size=dim).astype(np.float32)
    return v / np.linalg.norm(v)


def test_diversity_requires_minimum_images():
    findings = analyze_diversity({f"p{i}": _unit(i) for i in range(4)})
    assert len(findings) == 1
    assert findings[0].severity == SEVERITY_INFO
    assert "at least" in findings[0].title


def test_near_duplicate_cluster_is_excludable():
    base = _unit(99)
    embeddings = {f"img{i}": _unit(i) for i in range(12)}
    embeddings["dup_a"] = base
    embeddings["dup_b"] = base.copy()
    embeddings["dup_c"] = base * 0.999 + _unit(1) * 0.001  # cos ≈ 1
    findings = analyze_diversity(embeddings)
    cluster = next(f for f in findings if "Near-duplicate cluster" in f.title)
    assert cluster.action == ACTION_EXCLUDE
    assert set(cluster.paths) == {"dup_a", "dup_b", "dup_c"}


def test_dominant_mode_and_thin_clusters_are_flagged():
    dominant = _unit(7)
    embeddings = {f"dom{i}": dominant for i in range(40)}
    for i in range(4):
        embeddings[f"rare{i}"] = _unit(100 + i)
    findings = analyze_diversity(embeddings)
    dom = next(f for f in findings if "visual mode" in f.title)
    assert dom.severity == SEVERITY_WARNING and dom.action == ACTION_SELECT
    assert len(dom.paths) == 40
    thin = next(f for f in findings if "thin cluster" in f.title)
    assert thin.severity == SEVERITY_INFO
    assert set(thin.paths) == {"rare0", "rare1", "rare2", "rare3"}


def test_diversity_summary_label_present():
    embeddings = {f"img{i}": _unit(i) for i in range(30)}
    findings = analyze_diversity(embeddings)
    summary = next(f for f in findings if f.title.startswith("Diversity:"))
    assert summary.action is None
