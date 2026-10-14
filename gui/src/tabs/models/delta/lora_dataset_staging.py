"""Dataset import and staging helpers for the LoRA Train tab (split from lora_train_tab)."""
import os
import shutil
import tempfile
from pathlib import Path
from typing import NamedTuple

# Content Gen §1.3: LyCORIS variants (LoCon/LoHa/LoKr), each a Hydra config
# preset under backend/config/training/. "standard" keeps the existing
# LoRATuner (legacy) path byte-for-byte unchanged; the three LyCORIS
# entries route through the already-built LoRATunerV2 pipeline
# (backend/src/pipeline/anime_training_pipeline.py) via the project's own
# Hydra CLI dispatcher, rather than re-implementing dataset/tuner
# construction inline here.
_TRAINING_ENGINES = [
    ("Standard (LoRA)", "standard"),
    ("LyCORIS: LoCon (style-bound characters)", "locon"),
    ("LyCORIS: LoHa (small datasets)", "loha"),
    ("LyCORIS: LoKr (tiny datasets / storage-constrained)", "lokr"),
]


_DATASET_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})


def _signal_process_group(proc, sig: int) -> bool:
    """Signal the LyCORIS session. False means the caller should use ``terminate``."""
    if proc is None or proc.poll() is not None:
        return True
    pid = getattr(proc, "pid", None)
    # MagicMock pid is not a session id. bool is an int subclass and is not a pid.
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.killpg(pid, sig)
    except OSError:
        return False
    return True


class ImportedDataset(NamedTuple):
    train_dir: str | None
    source_paths: tuple[str, ...]
    scope: str
    staged: bool


def combine_trigger_and_prompt(trigger: str, prompt: str) -> str:
    """Prepend the activation token to the instance prompt when missing."""
    trigger = trigger.strip()
    prompt = prompt.strip()
    if not trigger:
        return prompt
    tokens = [part.strip() for part in prompt.split(",") if part.strip()]
    if trigger in tokens:
        return prompt
    return f"{trigger}, {prompt}" if prompt else trigger


def _image_paths_under(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(
            child
            for child in path.iterdir()
            if child.is_file() and child.suffix.lower() in _DATASET_IMAGE_EXTS
        )
    if path.is_file() and path.suffix.lower() in _DATASET_IMAGE_EXTS:
        return [path]
    return []


def _existing_images(paths: list[Path]) -> list[Path]:
    images: list[Path] = []
    for path in paths:
        if path.is_dir():
            images.extend(_image_paths_under(path))
        elif path.is_file() and path.suffix.lower() in _DATASET_IMAGE_EXTS:
            images.append(path)
    unique: list[Path] = []
    seen: set[Path] = set()
    for image in images:
        key = image.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(image)
    return unique


def _exclusive_parent(unique: list[Path]) -> Path | None:
    parents = {image.resolve().parent for image in unique}
    if len(parents) != 1:
        return None
    parent = next(iter(parents))
    siblings = {child.resolve() for child in _image_paths_under(parent)}
    if siblings == {image.resolve() for image in unique}:
        return parent
    return None


def _unique_staged_name(src: Path, used_names: set[str], used_stems: set[str]) -> str:
    name = src.name
    if name not in used_names and Path(name).stem not in used_stems:
        return name
    stem, suffix = src.stem, src.suffix
    name = f"{src.parent.name}_{stem}{suffix}"
    extra = 2
    while name in used_names or Path(name).stem in used_stems:
        name = f"{src.parent.name}_{stem}_{extra}{suffix}"
        extra += 1
    return name


def _stage_images(unique: list[Path], staging_root: Path | None) -> Path | None:
    staging_root = staging_root or Path.home() / "Downloads" / "Data" / "Tests"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="itk-train-dataset-", dir=str(staging_root)))
    used_names: set[str] = set()
    used_stems: set[str] = set()
    for src in unique:
        if not src.is_file():
            continue
        name = _unique_staged_name(src, used_names, used_stems)
        used_names.add(name)
        used_stems.add(Path(name).stem)
        (staging / name).symlink_to(src.resolve())
        caption = src.with_suffix(".txt")
        if caption.is_file():
            (staging / Path(name).with_suffix(".txt")).symlink_to(caption.resolve())
    has_image = any(
        child.is_file() and child.suffix.lower() in _DATASET_IMAGE_EXTS
        for child in staging.iterdir()
    )
    if not has_image:
        shutil.rmtree(staging, ignore_errors=True)
        return None
    return staging


def resolve_imported_dataset(
    paths: tuple[str, ...],
    *,
    staging_root: Path | None = None,
    exclusions: frozenset[str] | None = None,
) -> ImportedDataset:
    """Map a handoff to the exact files training and Review Tags will see.

    A single directory stays folder-wide (Extractor / Browse) unless
    *exclusions* are set — excluded files must not remain visible to a
    folder-scoped training run, so the kept images fall through to the
    explicit-selection staging path below. Explicit file selections are the
    training set: the parent is reused only when it contains nothing else,
    otherwise the selection is staged so siblings and other directories
    cannot leak in. Missing or non-image paths are dropped before any
    symlink is created.
    """
    if not paths:
        return ImportedDataset(None, (), "selection", False)

    resolved = [Path(item) for item in paths]
    if len(resolved) == 1 and resolved[0].is_dir():
        images = _image_paths_under(resolved[0])
        if not exclusions:
            return ImportedDataset(str(resolved[0]), tuple(str(p) for p in images), "folder", False)
        resolved = [p for p in images if str(p.resolve()) not in exclusions]

    unique = _existing_images(resolved)
    if exclusions:
        unique = [p for p in unique if str(p.resolve()) not in exclusions]
    if not unique:
        return ImportedDataset(None, (), "selection", False)

    parent = _exclusive_parent(unique)
    if parent is not None:
        return ImportedDataset(str(parent), tuple(str(p) for p in unique), "selection", False)

    staging = _stage_images(unique, staging_root)
    if staging is None:
        return ImportedDataset(None, (), "selection", False)
    return ImportedDataset(str(staging), tuple(str(p) for p in unique), "selection", True)


def dataset_folder_from_paths(
    paths: tuple[str, ...],
    *,
    staging_root: Path | None = None,
) -> str | None:
    """Train directory for a handoff. Exact file selections are staged."""
    return resolve_imported_dataset(paths, staging_root=staging_root).train_dir
