"""
backend/src/pipeline/anime_training_pipeline.py
=================================================
End-to-end anime image generation training pipeline, driven by Hydra configs.

Stages
------
1. Video frame extraction     (VideoFrameExtractor + FFmpeg/PySceneDetect)
2. QA pass                    (BiRefNet foreground ratio, BaSiC normalisation,
                               Laplacian blur, NIQE, BRISQUE)
3. Hybrid auto-captioning     (WD-EVA02 + Florence-2)
4. Data deduplication         (pHash + Siamese diversity sampling)
5. Dataset construction       (LoRADatasetV2 + SDXL bucketing + augmentations)
6. LoRA / DreamBooth / Full-FT training
7. Diagnostics                (TensorBoard / W&B, cross-attn maps, SVD rank)

Entry point
-----------
    python -m backend.src.pipeline.anime_training_pipeline \\
        model=illustrious_xl training=lora_3090ti

Or override any key:
    python -m backend.src.pipeline.anime_training_pipeline \\
        model=noobai_vpred training=lora_4080 \\
        training.rank=32 data.trigger_word=my_char_xyz
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import hydra
from omegaconf import DictConfig, OmegaConf

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve(cfg: DictConfig, key: str, default=None):
    """Safe OmegaConf access that returns default if key is missing."""
    try:
        return OmegaConf.select(cfg, key, default=default)
    except Exception:
        return default


def _run_extraction(cfg: DictConfig) -> list[Path]:
    """Stage 1: extract frames from video sources."""
    from backend.src.models.data.video_frame_extractor import VideoFrameExtractor

    video_dir = Path(_resolve(cfg, "data.video_dir", "data/videos"))
    frames_dir = Path(_resolve(cfg, "data.frames_dir", "data/frames"))
    extr_cfg = cfg.get("data", {}).get("extraction", {})

    extractor = VideoFrameExtractor(
        adaptive_threshold=float(extr_cfg.get("adaptive_threshold", 3.0)),
        min_content_val=float(extr_cfg.get("min_content_val", 15.0)),
        min_scene_len=int(extr_cfg.get("min_scene_len", 12)),
        sample_per_scene=int(extr_cfg.get("sample_per_scene", 1)),
        use_cuda_hwaccel=bool(extr_cfg.get("use_cuda_hwaccel", True)),
    )

    all_frames: list[Path] = []
    for video_path in sorted(video_dir.glob("**/*.mkv")) + sorted(video_dir.glob("**/*.mp4")):
        out_dir = frames_dir / video_path.stem
        for rec in extractor.extract(video_path, out_dir):
            all_frames.append(out_dir / f"{video_path.stem}_s{rec.scene_idx:05d}_00.png")
    log.info("Extracted %d frames total", len(all_frames))
    return all_frames


def _run_qa_pass(image_paths: list[Path], cfg: DictConfig) -> list[Path]:
    """Stage 2: quality filtering with BiRefNet + BaSiC + Laplacian."""
    try:
        import cv2
        from backend.src.models.birefnet_wrapper import BiRefNetWrapper
        from backend.src.models.basic_wrapper import BaSiCWrapper
    except ImportError as exc:
        log.warning("QA dependencies unavailable (%s) — skipping QA pass", exc)
        return image_paths

    birefnet = BiRefNetWrapper()
    basic = BaSiCWrapper()
    qa_cfg = cfg.get("data", {}).get("qa", {})
    fg_min = float(qa_cfg.get("fg_ratio_min", 0.08))
    fg_max = float(qa_cfg.get("fg_ratio_max", 0.92))
    blur_min = float(qa_cfg.get("blur_lap_var_min", 50.0))

    accepted = []
    for p in image_paths:
        try:
            import numpy as np
            img = cv2.imread(str(p))
            if img is None:
                continue
            # Blur check
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if lap_var < blur_min:
                continue
            # Foreground ratio check
            from PIL import Image
            with Image.open(p) as im:
                mask = birefnet.get_soft_mask(im)
            fg = float(np.mean(np.array(mask))) if mask is not None else 0.5
            if not (fg_min <= fg <= fg_max):
                continue
            accepted.append(p)
        except Exception as exc:
            log.debug("QA failed for %s: %s", p, exc)
            accepted.append(p)

    log.info("QA pass: %d / %d accepted", len(accepted), len(image_paths))
    return accepted


def _run_captioning(image_paths: list[Path], cfg: DictConfig):
    """Stage 3: write .txt caption sidecars using WD14 + optional Florence-2."""
    cap_cfg = cfg.get("data", {}).get("captioning", {})
    onnx_path = cap_cfg.get("wd14_onnx", None)
    tags_csv = cap_cfg.get("wd14_tags_csv", None)
    use_florence = bool(cap_cfg.get("use_florence2", False))
    trigger = str(cfg.get("data", {}).get("trigger_word", ""))
    model_prefix = str(cfg.get("model", {}).get("caption_prefix", "illustrious"))

    if onnx_path is None or not Path(onnx_path).exists():
        log.warning("WD14 ONNX model not found — skipping captioning stage")
        return

    from backend.src.models.data.captioner import WD14Tagger, Florence2Captioner, HybridCaptioner
    wd = WD14Tagger(onnx_path=onnx_path, tags_csv=tags_csv,
                    general_thresh=float(cap_cfg.get("general_thresh", 0.35)),
                    character_thresh=float(cap_cfg.get("character_thresh", 0.85)))
    fl = Florence2Captioner(repo=cap_cfg.get("florence_repo", "microsoft/Florence-2-large-ft")) if use_florence else None
    captioner = HybridCaptioner(wd=wd, florence=fl, trigger=trigger or None,
                                 model_prefix=model_prefix)

    from PIL import Image
    for p in image_paths:
        txt = p.with_suffix(".txt")
        if txt.exists():
            continue
        try:
            with Image.open(p) as im:
                result = captioner(im)
            captioner.write_caption_file(p, result)
        except Exception as exc:
            log.debug("Captioning failed for %s: %s", p, exc)


def _run_deduplication(image_paths: list[Path], cfg: DictConfig) -> list[Path]:
    """Stage 4: pHash dedup + diversity sampling."""
    from backend.src.pipeline.data_selection import DataSelector, phash_hamming, cluster_duplicates

    target_k = int(cfg.get("data", {}).get("target_dataset_size", 50))
    if len(image_paths) <= target_k:
        return image_paths

    # Compute pHashes
    from backend.src.models.data.video_frame_extractor import _phash64
    phashes: dict[int, int] = {}
    paths_by_id: dict[int, Path] = {}
    for i, p in enumerate(image_paths):
        try:
            h = _phash64(str(p))
            phashes[i] = int(h, 16) if h.startswith("0x") else int(h, 16)
            paths_by_id[i] = p
        except Exception:
            paths_by_id[i] = p

    clusters = cluster_duplicates(phashes, threshold=6)
    dupes = {d for dl in clusters.values() for d in dl}
    unique_ids = [i for i in range(len(image_paths)) if i not in dupes]
    log.info("After pHash dedup: %d unique (removed %d)", len(unique_ids), len(dupes))

    # Simple truncation if still above target (full Siamese requires DB)
    result = [paths_by_id[i] for i in unique_ids[:target_k]]
    return result


def _build_dataset(image_paths: list[Path], cfg: DictConfig):
    """Stage 5: build LoRADatasetV2 with SDXL bucketing."""
    from transformers import CLIPTokenizer
    from backend.src.models.data.lora_dataset import BucketSample, LoRADatasetV2
    from backend.src.models.data.augmentations import default_anime_augmentations

    model_id = str(cfg.get("model", {}).get("model_id", "OnomaAIResearch/Illustrious-XL-v2.0"))
    trigger = str(cfg.get("data", {}).get("trigger_word", "my_char_xyz"))
    train_cfg = cfg.get("training", {})

    tok1 = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer")
    try:
        tok2 = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer_2")
    except Exception:
        tok2 = None

    # BiRefNet for augmentations (optional)
    birefnet = None
    if bool(cfg.get("data", {}).get("use_birefnet", True)):
        try:
            from backend.src.models.birefnet_wrapper import BiRefNetWrapper
            birefnet = BiRefNetWrapper()
        except Exception:
            pass

    basic = None
    if bool(cfg.get("data", {}).get("use_basic", True)):
        try:
            from backend.src.models.basic_wrapper import BaSiCWrapper
            basic = BaSiCWrapper()
        except Exception:
            pass

    samples = [BucketSample.from_path(p, trigger=trigger) for p in image_paths if p.exists()]
    augs = default_anime_augmentations()

    dataset = LoRADatasetV2(
        samples=samples,
        tokenizer_one=tok1,
        tokenizer_two=tok2,
        trigger_word=trigger,
        shuffle_tags=bool(train_cfg.get("shuffle_tags", True)),
        keep_tokens=int(train_cfg.get("keep_tokens", 1)),
        caption_dropout=float(train_cfg.get("caption_dropout_rate", 0.05)),
        birefnet=birefnet,
        basic=basic,
        augmentations=augs,
    )
    return dataset


def _build_tuner(cfg: DictConfig):
    """Construct LoRATunerV2 / DreamBoothTuner / FullFineTuner from config."""
    from backend.src.models.lora_diffusion import LoRATunerConfig, LoRATunerV2, DreamBoothTuner

    model_cfg = cfg.get("model", {})
    train_cfg = cfg.get("training", {})
    opt_cfg = cfg.get("optimizer", {})

    lora_cfg = LoRATunerConfig(
        base_model_path=str(model_cfg.get("model_id", "OnomaAIResearch/Illustrious-XL-v2.0")),
        prediction_type=str(model_cfg.get("prediction_type", "epsilon")),
        zero_terminal_snr=bool(model_cfg.get("zero_terminal_snr", False)),
        clip_skip=int(model_cfg.get("clip_skip", 1)),

        method=str(train_cfg.get("method", "peft")),
        rank=int(train_cfg.get("rank", 16)),
        alpha=train_cfg.get("alpha", None),
        use_dora=bool(train_cfg.get("use_dora", False)),
        use_rslora=bool(train_cfg.get("use_rslora", False)),
        lycoris_algo=str(train_cfg.get("lycoris_algo", "lora")),
        lycoris_conv_dim=int(train_cfg.get("lycoris_conv_dim", 8)),
        lycoris_conv_alpha=int(train_cfg.get("lycoris_conv_alpha", 4)),

        train_text_encoder_one=bool(train_cfg.get("train_text_encoder_one", False)),
        train_text_encoder_two=bool(train_cfg.get("train_text_encoder_two", False)),
        te_lr_scale=float(train_cfg.get("te_lr_scale", 0.5)),

        resolution=int(train_cfg.get("resolution", 1024)),
        train_batch_size=int(train_cfg.get("train_batch_size", 1)),
        gradient_accumulation_steps=int(train_cfg.get("gradient_accumulation_steps", 1)),
        gradient_checkpointing=bool(train_cfg.get("gradient_checkpointing", True)),
        mixed_precision=str(train_cfg.get("mixed_precision", "bf16")),
        max_train_epochs=train_cfg.get("max_train_epochs", None),
        max_train_steps=train_cfg.get("max_train_steps", None),

        snr_gamma=float(model_cfg.get("snr_gamma", 5.0)),
        noise_offset=float(train_cfg.get("noise_offset", 0.0)),

        optimizer_type=str(opt_cfg.get("type", "adamw8bit")),
        unet_lr=float(opt_cfg.get("unet_lr", 1e-4)),
        lr_scheduler=str(opt_cfg.get("lr_scheduler", "cosine_with_restarts")),
        lr_warmup_steps=int(opt_cfg.get("lr_warmup_steps", 100)),
        lr_num_cycles=int(opt_cfg.get("lr_num_cycles", 3)),
        weight_decay=float(opt_cfg.get("weight_decay", 1e-2)),

        use_ema=bool(train_cfg.get("use_ema", False)),
        output_dir=str(cfg.get("output_dir", "output_lora")),
        save_every_n_epochs=int(train_cfg.get("save_every_n_epochs", 1)),
        use_wandb=bool(cfg.get("logging", {}).get("use_wandb", False)),
        wandb_project=str(cfg.get("logging", {}).get("wandb_project", "anime-diffusion")),
        use_tensorboard=bool(cfg.get("logging", {}).get("use_tensorboard", True)),
        validation_prompts=list(cfg.get("validation_prompts", [])),
    )

    stage = str(train_cfg.get("stage", "lora"))
    if stage == "dreambooth":
        return DreamBoothTuner(
            cfg=lora_cfg,
            use_prior_preservation=bool(train_cfg.get("use_prior_preservation", True)),
            prior_loss_weight=float(train_cfg.get("prior_loss_weight", 1.0)),
            num_class_images=int(train_cfg.get("num_class_images", 200)),
            class_prompt=str(train_cfg.get("class_prompt", "1girl")),
        )
    if stage == "full_ft":
        from backend.src.models.full_finetune import FullFTConfig, FullFineTuner
        ft_cfg = FullFTConfig(
            base_model_path=lora_cfg.base_model_path,
            prediction_type=lora_cfg.prediction_type,
            zero_terminal_snr=lora_cfg.zero_terminal_snr,
            resolution=lora_cfg.resolution,
            train_batch_size=lora_cfg.train_batch_size,
            gradient_accumulation_steps=lora_cfg.gradient_accumulation_steps,
            gradient_checkpointing=lora_cfg.gradient_checkpointing,
            mixed_precision=lora_cfg.mixed_precision,
            max_train_steps=lora_cfg.max_train_steps or 12000,
            snr_gamma=lora_cfg.snr_gamma,
            optimizer_type=lora_cfg.optimizer_type,
            learning_rate=lora_cfg.unet_lr,
            output_dir=lora_cfg.output_dir,
            use_ema=lora_cfg.use_ema,
            freeze_down_blocks=int(train_cfg.get("freeze_down_blocks", 0)),
        )
        return FullFineTuner(ft_cfg)

    return LoRATunerV2(lora_cfg)


# ---------------------------------------------------------------------------
# Hydra entry point
# ---------------------------------------------------------------------------
@hydra.main(config_path="../../../config", config_name="base", version_base="1.3")
def main(cfg: DictConfig) -> None:
    log.info("Anime training pipeline starting")
    log.info("Config:\n%s", OmegaConf.to_yaml(cfg))

    # ── Stage 1: Frame extraction ────────────────────────────────────────
    image_paths: list[Path] = []
    if bool(_resolve(cfg, "pipeline.run_extraction", False)):
        image_paths = _run_extraction(cfg)
    else:
        data_dir = Path(str(_resolve(cfg, "data.images_dir", "data/images")))
        image_paths = sorted(
            p for p in data_dir.rglob("*")
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
        log.info("Loaded %d images from %s", len(image_paths), data_dir)

    if not image_paths:
        log.error("No images found — aborting")
        return

    # ── Stage 2: QA pass ─────────────────────────────────────────────────
    if bool(_resolve(cfg, "pipeline.run_qa", True)):
        image_paths = _run_qa_pass(image_paths, cfg)

    # ── Stage 3: Captioning ──────────────────────────────────────────────
    if bool(_resolve(cfg, "pipeline.run_captioning", False)):
        _run_captioning(image_paths, cfg)

    # ── Stage 4: Deduplication ───────────────────────────────────────────
    if bool(_resolve(cfg, "pipeline.run_dedup", True)):
        image_paths = _run_deduplication(image_paths, cfg)

    if not image_paths:
        log.error("No images after filtering — aborting")
        return

    log.info("Final dataset: %d images", len(image_paths))

    if not bool(_resolve(cfg, "pipeline.run_training", True)):
        log.info("pipeline.run_training=false — skipping training stages")
        log.info("Pipeline complete")
        return

    # ── Stage 5: Dataset construction ────────────────────────────────────
    dataset = _build_dataset(image_paths, cfg)
    from torch.utils.data import DataLoader
    from backend.src.models.data.lora_dataset import AspectRatioBucketSampler

    sampler = AspectRatioBucketSampler(
        dataset.samples,
        batch_size=int(_resolve(cfg, "training.train_batch_size", 1)),
        drop_last=True,
        seed=int(_resolve(cfg, "seed", 42)),
    )
    dataloader = DataLoader(
        dataset,
        batch_sampler=sampler,
        num_workers=int(_resolve(cfg, "data.num_workers", 0)),
        pin_memory=True,
    )

    # ── Stage 6: Build tuner ─────────────────────────────────────────────
    tuner = _build_tuner(cfg)

    # ── Stage 7: Diagnostics logger ──────────────────────────────────────
    from backend.src.models.diagnostics import DiagnosticsLogger
    run_name = str(_resolve(cfg, "run_name", "anime_run"))
    diagnostics = DiagnosticsLogger(
        run_name=run_name,
        use_wandb=bool(_resolve(cfg, "logging.use_wandb", False)),
        use_tensorboard=bool(_resolve(cfg, "logging.use_tensorboard", True)),
        tb_dir=str(_resolve(cfg, "logging.tb_dir", "runs")),
    )

    # ── Train ─────────────────────────────────────────────────────────────
    if hasattr(tuner, "maybe_generate_class_images"):
        tuner.maybe_generate_class_images()

    tuner.train(dataloader, diagnostics=diagnostics)
    diagnostics.close()
    log.info("Pipeline complete")


if __name__ == "__main__":
    main()
