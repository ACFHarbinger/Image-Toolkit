"""Dataset advisor (#744): deterministic dataset hygiene checks and CLIP
diversity analysis backing the Train tab's advisor panel.

`scan_dataset` is pure fs I/O + PIL header probing (no torch), so it runs
off the GUI thread and stays importable in GUI tests; CLIP embeddings are
computed by the caller via the similarity stack and handed to
`analyze_diversity` as numpy vectors, keeping this module GPU-free.

All findings are advisory: a sparse cluster or a high co-occurrence is a
review cue, not proof of a defect. Action kinds map to one-click panel
handlers; a finding with ``action=None`` is informational only (#744: a
finding that can't be applied in one click gets no button at all).
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Sequence

import numpy as np
from PIL import Image

SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

ACTION_SELECT = "select"
ACTION_EXCLUDE = "exclude"
ACTION_HYDRA = "hydra"
ACTION_REVIEW_TAGS = "review_tags"

ASPECT_MAX_RATIO = 3.0
COOCCURRENCE_THRESHOLD = 0.85
COOCCURRENCE_MIN_SUPPORT = 5
ENTANGLEMENT_CARD_LIMIT = 8
DIVERSITY_MIN_IMAGES = 8
NEAR_DUP_COSINE = 0.98
NEAR_DUP_EXACT_LIMIT = 1500
_DETAIL_PATH_LIMIT = 6
_DUPLICATE_CARD_LIMIT = 5
_THIN_CLUSTER_CARD_LIMIT = 5

# path -> (mtime_ns, size, sha256, width, height); lets the panel re-scan
# cheaply when only the trigger token changed.
HashCache = MutableMapping[str, tuple[int, int, str, int, int]]

_FRAME_RE = re.compile(r"^(.*?)(?:[_\- ])?(\d+)$")

# Composition tags describe image framing, not trainable concepts —
# entanglement advice about them is never actionable, so they are skipped
# for co-occurrence (they still count toward trigger support).
_COMPOSITION_TAGS = frozenset({
    "1girl", "2girls", "3girls", "4girls", "5girls",
    "1boy", "2boys", "3boys", "4boys", "5boys",
    "1other", "2others", "solo", "duo", "trio",
    "multiple girls", "multiple boys", "mixed-sex group",
})


@dataclass(frozen=True)
class AdvisorFinding:
    category: str  # duplicates|frames|captions|unreadable|aspects|cooccurrence|diversity
    severity: str  # SEVERITY_WARNING | SEVERITY_INFO
    title: str
    paths: tuple[str, ...] = ()
    action: str | None = None
    action_label: str = ""
    action_payload: str = ""  # Hydra fragment for ACTION_HYDRA
    detail: str = ""


@dataclass(frozen=True)
class ScanSummary:
    image_count: int
    captioned: int
    caption_coverage: float  # 0..1 over readable images
    scene_count: int  # distinct frame-group keys (video bursts count once)


@dataclass(frozen=True)
class ScanReport:
    findings: tuple[AdvisorFinding, ...]
    summary: ScanSummary


def _frame_group(filename: str) -> str:
    """Scene key for video-derived frames: trailing digits (with optional
    separator) stripped, so ``ep01_0001``/``ep01_0002`` group as one scene
    and adjacent frames don't inflate apparent coverage."""
    stem = Path(filename).stem
    match = _FRAME_RE.match(stem)
    if match and match.group(1):
        return match.group(1).rstrip("_- ")
    return stem


def _probe(path: Path) -> tuple[str | None, tuple[int, int] | None]:
    """Exact sha256 + header-only dimensions; (None, None) when unreadable."""
    try:
        data = path.read_bytes()
    except OSError:
        return None, None
    try:
        with Image.open(path) as image:
            dims = image.size
    except Exception:
        return hashlib.sha256(data).hexdigest(), None
    return hashlib.sha256(data).hexdigest(), dims


def _detail(paths: Sequence[str]) -> str:
    names = [Path(p).name for p in paths]
    suffix = f" (+{len(names) - _DETAIL_PATH_LIMIT} more)" if len(names) > _DETAIL_PATH_LIMIT else ""
    return ", ".join(names[:_DETAIL_PATH_LIMIT]) + suffix


def _cooccurrence_findings(
    captions: Mapping[str, list[str]], trigger: str
) -> list[AdvisorFinding]:
    tagged = {p: {t.strip().lower() for t in tags if t.strip()} for p, tags in captions.items()}
    tagged = {p: tags for p, tags in tagged.items() if tags}
    if len(tagged) < COOCCURRENCE_MIN_SUPPORT:
        return []
    if not trigger.strip():
        return [AdvisorFinding(
            "cooccurrence", SEVERITY_INFO,
            "Trigger token not set — tag entanglement not checked",
        )]
    trg = trigger.strip().lower()
    support = {p for p, tags in tagged.items() if trg in tags}
    if not support:
        return [AdvisorFinding(
            "cooccurrence", SEVERITY_INFO,
            f"Trigger '{trigger.strip()}' not found in any caption — nothing to check against",
        )]
    if len(support) < COOCCURRENCE_MIN_SUPPORT:
        return [AdvisorFinding(
            "cooccurrence", SEVERITY_INFO,
            f"Trigger '{trigger.strip()}' appears in {len(support)} caption(s) — "
            f"below the {COOCCURRENCE_MIN_SUPPORT} needed for entanglement stats",
        )]
    totals = Counter(tag for tags in tagged.values() for tag in tags)
    joint = Counter(
        tag for p, tags in tagged.items() if p in support for tag in tags if tag != trg
    )
    findings = []
    for tag, joint_count in joint.most_common():
        # Composition tags ("1girl" on every image) are framing, not
        # trainable concepts — entanglement advice about them is noise.
        if tag in _COMPOSITION_TAGS:
            continue
        # Gemini's formula: Ent(T, trigger) = P(T ∩ trigger) / P(T) — the
        # share of images carrying T that also carry the trigger word.
        entanglement = joint_count / totals[tag]
        if joint_count < COOCCURRENCE_MIN_SUPPORT or entanglement <= COOCCURRENCE_THRESHOLD:
            continue
        findings.append(AdvisorFinding(
            "cooccurrence", SEVERITY_WARNING,
            f"'{tag}' appears with trigger '{trigger.strip()}' in "
            f"{entanglement:.0%} of {totals[tag]} image(s)",
            detail="Consider decoupling or adding regularization images",
        ))
        if len(findings) >= ENTANGLEMENT_CARD_LIMIT:
            break
    return findings


def scan_dataset(
    images: Sequence[str],
    *,
    trigger: str = "",
    hash_cache: HashCache | None = None,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> ScanReport:
    """Run the deterministic checks over an already-resolved image list.

    Checks: unreadable files, extreme aspect ratios (beyond 3:1 either
    way), caption sidecar coverage, exact-hash duplicates (frame-group
    aware), and tag entanglement against *trigger*. Pure fs/PIL — safe off
    the GUI thread; *cancel* returning True stops the scan early and
    returns the findings gathered so far.
    """
    paths = sorted({str(p) for p in images})
    total = len(paths)
    readable: list[tuple[str, Path, tuple[int, int], str]] = []
    unreadable: list[str] = []
    for index, raw in enumerate(paths):
        if cancel is not None and cancel():
            break
        path = Path(raw)
        try:
            st = path.stat()
        except OSError:
            unreadable.append(raw)
            continue
        sha: str | None = None
        dims: tuple[int, int] | None = None
        cached = hash_cache.get(raw) if hash_cache is not None else None
        if cached is not None and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
            sha, dims = cached[2], (cached[3], cached[4])
        else:
            sha, dims = _probe(path)
            if sha is not None and dims is not None and hash_cache is not None:
                hash_cache[raw] = (st.st_mtime_ns, st.st_size, sha, dims[0], dims[1])
        if dims is None:
            unreadable.append(raw)
        else:
            readable.append((raw, path, dims, sha or ""))
        if progress is not None and index % 8 == 0:
            progress(index + 1, total)
    if progress is not None:
        progress(total, total)

    findings: list[AdvisorFinding] = []

    for group in _duplicate_groups(readable):
        findings.append(group)

    if unreadable:
        findings.append(AdvisorFinding(
            "unreadable", SEVERITY_WARNING,
            f"{len(unreadable)} unreadable image file(s)",
            paths=tuple(unreadable), action=ACTION_SELECT, action_label="Show",
            detail=_detail(unreadable),
        ))

    extremes = [
        raw for raw, _path, (w, h), _sha in readable
        if max(w / h, h / w) > ASPECT_MAX_RATIO
    ]
    if extremes:
        findings.append(AdvisorFinding(
            "aspects", SEVERITY_WARNING,
            f"{len(extremes)} extreme aspect ratio(s) (beyond {ASPECT_MAX_RATIO:g}:1)",
            paths=tuple(extremes), action=ACTION_SELECT, action_label="Show",
            detail=_detail(extremes),
        ))

    captions = _read_captions(path for _raw, path, _dims, _sha in readable)
    captioned = sum(1 for text in captions.values() if text)
    missing = tuple(raw for raw, path, _dims, _sha in readable if not captions.get(path))
    if missing:
        findings.append(AdvisorFinding(
            "captions", SEVERITY_WARNING,
            f"{len(missing)} image(s) without captions",
            paths=missing, action=ACTION_HYDRA,
            action_label="Queue Hydra override: pipeline.run_captioning=true",
            action_payload="pipeline.run_captioning=true",
            detail=_detail(missing),
        ))
    findings.extend(_cooccurrence_findings(
        {str(path): (captions.get(path) or "").split(",") for _r, path, _d, _s in readable},
        trigger,
    ))

    scenes = len({_frame_group(Path(raw).name) for raw, _p, _d, _s in readable})
    summary = ScanSummary(
        image_count=len(readable),
        captioned=captioned,
        caption_coverage=captioned / len(readable) if readable else 0.0,
        scene_count=scenes,
    )
    return ScanReport(findings=tuple(findings), summary=summary)


def _duplicate_groups(
    readable: list[tuple[str, Path, tuple[int, int], str]],
) -> list[AdvisorFinding]:
    by_hash: dict[str, list[str]] = {}
    for raw, _path, _dims, sha in readable:
        by_hash.setdefault(sha, []).append(raw)
    duplicates = []
    bursts = []
    for sha, group in sorted(by_hash.items(), key=lambda item: item[1][0]):
        if len(group) < 2:
            continue
        keys = {_frame_group(Path(p).name) for p in group}
        if len(keys) == 1:
            key = next(iter(keys))
            bursts.append(AdvisorFinding(
                "frames", SEVERITY_INFO,
                f"Scene '{key}' contributes {len(group)} identical frames",
                paths=tuple(group),
                detail="Video bursts are counted as one scene for coverage",
            ))
        else:
            duplicates.append(AdvisorFinding(
                "duplicates", SEVERITY_WARNING,
                f"{len(group)} identical files (sha256 {sha[:8]}…)",
                paths=tuple(group), action=ACTION_EXCLUDE,
                action_label=f"Exclude {len(group) - 1} duplicate(s)",
                detail=_detail(group),
            ))
    return duplicates[:_DUPLICATE_CARD_LIMIT] + bursts


def _read_captions(paths: Iterable[Path]) -> dict[Path, str]:
    captions: dict[Path, str] = {}
    for path in paths:
        sidecar = path.with_suffix(".txt")
        try:
            text = sidecar.read_text(encoding="utf-8").strip() if sidecar.is_file() else ""
        except OSError:
            text = ""
        captions[path] = text
    return captions


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.parent[rj] = ri


def _kmeans(matrix: np.ndarray, k: int, *, iterations: int = 25, seed: int = 0) -> np.ndarray:
    """Deterministic spherical k-means (rows are L2-normalized).

    Hand-rolled instead of sklearn.cluster.KMeans: sklearn's first fit
    walks every loaded shared library via threadpoolctl, which stalls for
    seconds inside GUI worker threads. Dataset sizes here are hundreds of
    images, where this loop is trivially fast.
    """
    n = matrix.shape[0]
    rng = np.random.default_rng(seed)
    centroids = [matrix[int(rng.integers(n))]]
    while len(centroids) < k:
        closest = np.stack([matrix @ c for c in centroids]).max(axis=0)
        weights = np.maximum(1.0 - closest, 0.0) ** 2
        total = float(weights.sum())
        if total <= 0.0:
            centroids.append(matrix[int(rng.integers(n))])
        else:
            centroids.append(matrix[int(rng.choice(n, p=weights / total))])
    centers = np.stack(centroids)

    labels = np.full(n, -1)
    for _ in range(iterations):
        new_labels = (matrix @ centers.T).argmax(axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for j in range(k):
            members = matrix[labels == j]
            if not len(members):
                continue
            centroid = members.mean(axis=0)
            norm = float(np.linalg.norm(centroid))
            if norm > 1e-12:
                centers[j] = centroid / norm
    return labels


def analyze_diversity(
    embeddings: Mapping[str, Any],
    *,
    cancel: Callable[[], bool] | None = None,
) -> list[AdvisorFinding]:
    """Cluster L2-normalized CLIP embeddings and flag near-duplicate
    clusters, a dominant visual mode, and thin clusters (possible
    underrepresented pose/angle/background — a review cue, not proof)."""
    items = [
        (str(p), np.asarray(v, dtype=np.float32).reshape(-1))
        for p, v in embeddings.items()
        if v is not None and np.asarray(v).size
    ]
    if len(items) < DIVERSITY_MIN_IMAGES:
        return [AdvisorFinding(
            "diversity", SEVERITY_INFO,
            f"Only {len(items)} embedded image(s) — clustering needs at least "
            f"{DIVERSITY_MIN_IMAGES}",
        )]
    stacked = np.stack([v for _p, v in items])
    matrix = stacked / np.maximum(np.linalg.norm(stacked, axis=1, keepdims=True), 1e-12)
    paths = [p for p, _v in items]
    n = len(paths)
    findings: list[AdvisorFinding] = []

    if cancel is not None and cancel():
        return findings
    if n <= NEAR_DUP_EXACT_LIMIT:
        similar = matrix @ matrix.T
        uf = _UnionFind(n)
        for i in range(n):
            for j in range(i + 1, n):
                if similar[i, j] >= NEAR_DUP_COSINE:
                    uf.union(i, j)
        members: dict[int, list[int]] = {}
        for i in range(n):
            members.setdefault(uf.find(i), []).append(i)
        near_dups = sorted(
            (group for group in members.values() if len(group) >= 2),
            key=len, reverse=True,
        )
        for group in near_dups[:_DUPLICATE_CARD_LIMIT]:
            group_paths = tuple(paths[i] for i in group)
            findings.append(AdvisorFinding(
                "diversity", SEVERITY_WARNING,
                f"Near-duplicate cluster: {len(group)} visually identical images",
                paths=group_paths, action=ACTION_EXCLUDE,
                action_label=f"Exclude {len(group) - 1}",
                detail=_detail(group_paths),
            ))

    k = int(round(n ** 0.5))
    k = max(2, min(k, max(2, n // 10)))
    labels = _kmeans(matrix, k)
    sizes = np.bincount(labels, minlength=k)
    shares = sizes / n
    top_share = float(shares.max())
    if top_share > 0.6:
        top_paths = tuple(
            p for p, label in zip(paths, labels, strict=True)
            if label == int(shares.argmax())
        )
        findings.append(AdvisorFinding(
            "diversity", SEVERITY_WARNING,
            f"One visual mode covers {top_share:.0%} of the dataset — overfit risk",
            paths=top_paths, action=ACTION_SELECT, action_label="Show",
        ))

    thin_limit = max(2, int(0.02 * n))
    thin = [label for label, size in enumerate(sizes) if size <= thin_limit]
    if thin:
        thin_paths = tuple(
            p for p, label in zip(paths, labels, strict=True) if label in set(thin)
        )
        findings.append(AdvisorFinding(
            "diversity", SEVERITY_INFO,
            f"{len(thin)} thin cluster(s) ({', '.join(str(sizes[l]) for l in thin[:8])} images)"
            " — possibly underrepresented pose/angle/background",
            paths=thin_paths, action=ACTION_SELECT, action_label="Show examples",
            detail="A sparse cluster is a review cue, not proof of a missing pose",
        ))

    effective = 1.0 / float((shares ** 2).sum())
    ratio = effective / k
    label = "good" if ratio >= 0.7 else "moderate" if ratio >= 0.4 else "low"
    findings.append(AdvisorFinding(
        "diversity", SEVERITY_INFO,
        f"Diversity: {label} — {k} clusters, effective {effective:.1f}",
    ))
    return findings
