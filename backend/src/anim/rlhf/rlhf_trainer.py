"""
RLHF training orchestrator.

Two entry points:
  1. ``train_reward_model``   — train or fine-tune the CNN reward model from a
                                FeedbackStore filled with human ratings.
  2. ``fine_tune_drl_agent``  — train the RegistrationAgent using the reward
                                model's scores instead of SSIM, so the agent
                                learns to prefer the kinds of alignments humans
                                rated highly.
"""

from __future__ import annotations

import math
import random
from typing import Callable, List, Optional, Tuple

import cv2
import numpy as np

from .feedback_store import FeedbackStore
from .reward_model import StitchRewardModel


# ---------------------------------------------------------------------------
# Reward-model training (thin wrapper kept for IDE discoverability)
# ---------------------------------------------------------------------------

def train_reward_model(
    store: FeedbackStore,
    model_path: Optional[str] = None,
    epochs: int = 20,
    lr: float = 1e-3,
    progress_cb: Optional[Callable[[int, int, float], None]] = None,
) -> StitchRewardModel:
    """
    Train the reward model from a FeedbackStore and return the trained instance.

    Parameters
    ----------
    store       : feedback data source.
    model_path  : where to save weights; defaults to ~/.config/image-toolkit/stitch_reward_model.pt.
    epochs      : training epochs.
    lr          : learning rate.
    progress_cb : called as (current_epoch, total_epochs, val_loss) each epoch.
    """
    model = StitchRewardModel(model_path=model_path)
    model.train_from_feedback(store, epochs=epochs, lr=lr, progress_cb=progress_cb)
    return model


# ---------------------------------------------------------------------------
# DRL fine-tuning with RLHF reward
# ---------------------------------------------------------------------------

def _overlap_region(
    img_ref: np.ndarray,
    img_warped: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return the sub-images where both frames have content (non-black)."""
    valid = (img_ref.max(axis=2) > 0) & (img_warped.max(axis=2) > 0)
    ys, xs = np.where(valid)
    if ys.size < 100:
        return img_ref, img_warped
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    return img_ref[y0:y1, x0:x1], img_warped[y0:y1, x0:x1]


def _stitch_preview(
    img_ref: np.ndarray,
    img_warped: np.ndarray,
) -> np.ndarray:
    """
    Quick horizontal blend preview of ref + warped for reward model evaluation.
    Pixels covered by both images are blended 50/50; others kept as-is.
    """
    h = max(img_ref.shape[0], img_warped.shape[0])
    w = max(img_ref.shape[1], img_warped.shape[1])
    canvas = np.zeros((h, w, 3), dtype=np.uint8)
    canvas[: img_ref.shape[0], : img_ref.shape[1]] = img_ref
    valid_w = img_warped.max(axis=2) > 0
    valid_c = canvas[: img_warped.shape[0], : img_warped.shape[1]].max(axis=2) > 0
    both = valid_w & valid_c
    only_w = valid_w & ~both
    ph, pw = img_warped.shape[:2]
    patch = canvas[:ph, :pw]
    patch[both] = (
        patch[both].astype(np.uint16) + img_warped[both].astype(np.uint16)
    ) // 2
    patch[only_w] = img_warped[only_w]
    canvas[:ph, :pw] = patch
    return canvas


def fine_tune_drl_agent(
    agent,                              # RegistrationAgent instance
    reward_model: StitchRewardModel,
    frame_pairs: List[Tuple[np.ndarray, np.ndarray]],
    episodes: int = 12,
    max_steps: int = 40,
    epsilon_start: float = 0.9,
    epsilon_end: float = 0.1,
    target_update: int = 20,
    progress_cb: Optional[Callable[[int, int, float], None]] = None,
) -> None:
    """
    Fine-tune ``agent`` using ``reward_model`` scores as the reward signal.

    For each (ref, src) pair in ``frame_pairs`` the agent attempts to align
    src to ref over ``episodes`` episodes.  The reward at each step is:

        r = reward_model(stitch_preview) - prev_reward

    so the agent learns to prefer transformations that human raters liked.

    Parameters
    ----------
    agent        : RegistrationAgent (from mfsr.drl_registration).
    reward_model : trained StitchRewardModel.
    frame_pairs  : list of (ref_bgr, src_bgr) numpy arrays.
    """
    from ..mfsr.drl_registration import _AXIS_STEPS, _warp

    if not frame_pairs:
        return

    total_ep = episodes * len(frame_pairs)
    ep_idx = 0
    step_counter = 0

    for ref, src in frame_pairs:
        h, w = ref.shape[:2]

        for ep in range(episodes):
            ep_idx += 1
            # Random initial perturbation so the agent sees diverse states
            params = np.array([
                random.uniform(-w * 0.15, w * 0.15),
                random.uniform(-h * 0.15, h * 0.15),
                1.0,
                0.0,
            ], dtype=np.float64)

            warped = _warp(src, params, h, w)
            preview = _stitch_preview(ref, warped)
            prev_score = reward_model.predict(preview)
            state = agent._state_vector(ref, warped, agent.state_dim)

            epsilon = epsilon_start + (epsilon_end - epsilon_start) * ep_idx / max(1, total_ep)

            for t in range(max_steps):
                action = agent._select_action(state, epsilon)
                axis, step = _AXIS_STEPS[action]
                params[axis] += step

                warped = _warp(src, params, h, w)
                preview = _stitch_preview(ref, warped)
                cur_score = reward_model.predict(preview)

                reward = float(cur_score - prev_score)
                prev_score = cur_score

                next_state = agent._state_vector(ref, warped, agent.state_dim)
                done = bool(cur_score > 0.95 or t == max_steps - 1)

                agent.memory.append((state, action, reward, next_state, done))
                state = next_state
                agent._trained = True

                loss = agent._replay_step()
                step_counter += 1
                if step_counter % target_update == 0:
                    agent.target.load_state_dict(agent.online.state_dict())

                if done:
                    break

            if progress_cb:
                progress_cb(ep_idx, total_ep, prev_score)


__all__ = ["train_reward_model", "fine_tune_drl_agent"]
