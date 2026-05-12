"""
Deep Reinforcement Learning (DRL) for autonomous image registration.

Frames the registration as an MDP:
  State:   Concatenated visual feature maps of reference + moving image.
  Actions: [dx, dy, dscale, dtheta] adjustments to the transformation.
  Reward:  SSIM improvement after applying the action.

Uses a lightweight CNN policy network (no heavy RL framework required).
Can be trained offline and then used for fast inference.

Architecture: Double DQN with experience replay.
"""

from __future__ import annotations

import math
import random
from collections import deque
from typing import Deque, List, Optional, Tuple

import cv2
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False

from ..constants import (
    DRL_ACTION_DIM,
    DRL_BATCH_SIZE,
    DRL_GAMMA,
    DRL_LR,
    DRL_MEMORY_SIZE,
    DRL_STATE_SIZE,
)


# ---------------------------------------------------------------------------
# Action discretisation
# ---------------------------------------------------------------------------

# 4 axes * (negative, positive) * (small, large) = 16 discrete actions
_AXIS_STEPS = [
    (0, +1.0),    # +dx fine
    (0, -1.0),
    (0, +8.0),    # +dx coarse
    (0, -8.0),
    (1, +1.0),    # +dy fine
    (1, -1.0),
    (1, +8.0),
    (1, -8.0),
    (2, +0.01),   # +dscale fine
    (2, -0.01),
    (2, +0.05),
    (2, -0.05),
    (3, +0.01),   # +dtheta fine (radians)
    (3, -0.01),
    (3, +0.05),
    (3, -0.05),
]

_NUM_ACTIONS = len(_AXIS_STEPS)


def _ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Simple SSIM proxy: per-channel mean + variance correlation."""
    if a.ndim == 3:
        a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    if b.ndim == 3:
        b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    af = a.astype(np.float64)
    bf = b.astype(np.float64)
    mu_a = af.mean()
    mu_b = bf.mean()
    var_a = af.var() + 1e-6
    var_b = bf.var() + 1e-6
    cov = ((af - mu_a) * (bf - mu_b)).mean()
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    den = (mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2)
    return float(num / den)


def _params_to_M(params: np.ndarray) -> np.ndarray:
    """params = [dx, dy, scale, theta_rad] -> (2,3) affine."""
    dx, dy, s, theta = (float(params[k]) for k in range(4))
    s = max(0.5, min(2.0, s))
    cos = math.cos(theta) * s
    sin = math.sin(theta) * s
    return np.array([[cos, -sin, dx], [sin, cos, dy]], dtype=np.float32)


def _warp(img: np.ndarray, params: np.ndarray, h: int, w: int) -> np.ndarray:
    return cv2.warpAffine(
        img,
        _params_to_M(params),
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


# ---------------------------------------------------------------------------
# DQN network
# ---------------------------------------------------------------------------

if _TORCH_OK:

    class _DuelingDQN(nn.Module):
        """A small dueling DQN over a low-dimensional state vector."""

        def __init__(self, state_dim: int = DRL_STATE_SIZE, n_actions: int = _NUM_ACTIONS):
            super().__init__()
            self.feature = nn.Sequential(
                nn.Linear(state_dim, 256),
                nn.ReLU(inplace=True),
                nn.Linear(256, 256),
                nn.ReLU(inplace=True),
            )
            self.value = nn.Linear(256, 1)
            self.advantage = nn.Linear(256, n_actions)

        def forward(self, x):
            h = self.feature(x)
            v = self.value(h)
            a = self.advantage(h)
            return v + (a - a.mean(dim=1, keepdim=True))

else:

    class _DuelingDQN:  # type: ignore
        """Dummy stand-in when torch is unavailable."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError("torch is required for the DRL agent")


class RegistrationAgent:
    """
    DRL agent for image registration.

    Use ``align()`` for inference; it works even without training (a small
    random-walk + greedy descent loop is run when the network is untrained).
    """

    def __init__(
        self,
        state_dim: int = DRL_STATE_SIZE,
        n_actions: int = _NUM_ACTIONS,
        lr: float = DRL_LR,
        gamma: float = DRL_GAMMA,
        memory_size: int = DRL_MEMORY_SIZE,
        batch_size: int = DRL_BATCH_SIZE,
    ):
        self.state_dim = state_dim
        self.n_actions = n_actions
        self.gamma = gamma
        self.batch_size = batch_size
        self.memory: Deque[Tuple] = deque(maxlen=memory_size)
        self._trained = False

        if _TORCH_OK:
            self.device = torch.device(
                "cuda" if torch.cuda.is_available() else "cpu"
            )
            self.online = _DuelingDQN(state_dim, n_actions).to(self.device)
            self.target = _DuelingDQN(state_dim, n_actions).to(self.device)
            self.target.load_state_dict(self.online.state_dict())
            self.optim = torch.optim.Adam(self.online.parameters(), lr=lr)
        else:
            self.device = "cpu"
            self.online = None
            self.target = None
            self.optim = None

    # ------------------------------------------------------------------ state
    @staticmethod
    def _state_vector(ref: np.ndarray, src: np.ndarray, dim: int) -> np.ndarray:
        """Encode a (ref, src) pair into a flat feature vector of length `dim`."""
        ref_g = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY) if ref.ndim == 3 else ref
        src_g = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY) if src.ndim == 3 else src
        side = max(8, int(math.sqrt(dim / 2)))
        ref_s = cv2.resize(ref_g, (side, side), interpolation=cv2.INTER_AREA)
        src_s = cv2.resize(src_g, (side, side), interpolation=cv2.INTER_AREA)
        vec = np.concatenate([
            ref_s.astype(np.float32).flatten() / 255.0,
            src_s.astype(np.float32).flatten() / 255.0,
        ])
        if vec.size < dim:
            vec = np.pad(vec, (0, dim - vec.size))
        return vec[:dim]

    # ------------------------------------------------------------- select
    def _select_action(self, state: np.ndarray, epsilon: float) -> int:
        if (not _TORCH_OK) or self.online is None or not self._trained:
            return random.randrange(self.n_actions)
        if random.random() < epsilon:
            return random.randrange(self.n_actions)
        with torch.no_grad():
            s = torch.from_numpy(state.astype(np.float32)).unsqueeze(0).to(self.device)
            q = self.online(s)
            return int(q.argmax(dim=1).item())

    # ---------------------------------------------------------- replay step
    def _replay_step(self) -> Optional[float]:
        if (not _TORCH_OK) or len(self.memory) < self.batch_size:
            return None
        batch = random.sample(self.memory, self.batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        s = torch.from_numpy(np.stack(states).astype(np.float32)).to(self.device)
        a = torch.tensor(actions, dtype=torch.long, device=self.device).unsqueeze(1)
        r = torch.tensor(rewards, dtype=torch.float32, device=self.device).unsqueeze(1)
        s2 = torch.from_numpy(np.stack(next_states).astype(np.float32)).to(self.device)
        d = torch.tensor(dones, dtype=torch.float32, device=self.device).unsqueeze(1)

        q = self.online(s).gather(1, a)
        with torch.no_grad():
            # Double DQN: argmax from online, value from target
            next_a = self.online(s2).argmax(dim=1, keepdim=True)
            q_next = self.target(s2).gather(1, next_a)
            target = r + (1.0 - d) * self.gamma * q_next

        loss = F.smooth_l1_loss(q, target)
        self.optim.zero_grad()
        loss.backward()
        for p in self.online.parameters():
            if p.grad is not None:
                p.grad.data.clamp_(-1.0, 1.0)
        self.optim.step()
        return float(loss.item())

    # ----------------------------------------------------------------- train
    def train_on_pair(
        self,
        img_ref: np.ndarray,
        img_src: np.ndarray,
        episodes: int = 8,
        max_steps: int = 40,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.1,
        target_update: int = 16,
    ) -> None:
        """
        A self-contained training loop on a single (ref, src) pair.

        For each episode we sample a random initial transformation, then let
        the agent improve it.  Useful as a warm-up before calling ``align()``.
        """
        if not _TORCH_OK:
            return
        h, w = img_ref.shape[:2]
        step_counter = 0
        for ep in range(episodes):
            params = np.array([
                np.random.uniform(-w * 0.2, w * 0.2),
                np.random.uniform(-h * 0.2, h * 0.2),
                1.0,
                0.0,
            ], dtype=np.float64)
            warped = _warp(img_src, params, h, w)
            state = self._state_vector(img_ref, warped, self.state_dim)
            prev_ssim = _ssim(img_ref, warped)
            epsilon = epsilon_start + (epsilon_end - epsilon_start) * ep / max(1, episodes - 1)

            for t in range(max_steps):
                action = self._select_action(state, epsilon)
                axis, step = _AXIS_STEPS[action]
                params[axis] += step
                warped = _warp(img_src, params, h, w)
                cur_ssim = _ssim(img_ref, warped)
                reward = float(cur_ssim - prev_ssim)
                prev_ssim = cur_ssim

                next_state = self._state_vector(img_ref, warped, self.state_dim)
                done = bool(cur_ssim > 0.98 or t == max_steps - 1)
                self.memory.append((state, action, reward, next_state, done))
                state = next_state
                self._trained = True

                self._replay_step()
                step_counter += 1
                if step_counter % target_update == 0:
                    self.target.load_state_dict(self.online.state_dict())

                if done:
                    break

    # -------------------------------------------------------------- inference
    def align(
        self,
        img_ref: np.ndarray,
        img_src: np.ndarray,
        init_M: Optional[np.ndarray] = None,
        max_steps: int = 50,
    ) -> Tuple[np.ndarray, float]:
        """Align img_src to img_ref, returning (affine_M, final_ssim)."""
        h, w = img_ref.shape[:2]

        if init_M is not None:
            # Decompose (2,3) affine into [dx, dy, scale, theta]
            a, b, dx = init_M[0]
            c, d, dy = init_M[1]
            scale = float(math.sqrt(a * a + c * c)) or 1.0
            theta = float(math.atan2(c, a))
            params = np.array([float(dx), float(dy), scale, theta], dtype=np.float64)
        else:
            params = np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float64)

        warped = _warp(img_src, params, h, w)
        best_ssim = _ssim(img_ref, warped)
        best_params = params.copy()

        for t in range(max_steps):
            state = self._state_vector(img_ref, warped, self.state_dim)
            action = self._select_action(state, epsilon=0.05 if self._trained else 1.0)
            axis, step = _AXIS_STEPS[action]
            trial = params.copy()
            trial[axis] += step
            trial_warped = _warp(img_src, trial, h, w)
            trial_ssim = _ssim(img_ref, trial_warped)

            if trial_ssim > best_ssim:
                params = trial
                warped = trial_warped
                best_ssim = trial_ssim
                best_params = trial.copy()
            else:
                # Random-walk fallback: occasionally accept a worse step
                # to escape local optima.
                if random.random() < 0.05:
                    params = trial
                    warped = trial_warped

        return _params_to_M(best_params), float(best_ssim)


__all__ = ["RegistrationAgent"]
