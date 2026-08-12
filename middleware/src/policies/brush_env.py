"""Gymnasium environment for the interactive Brush Assistant RL policy.

Models local dodge/burn/sharpen/tone brush strokes over an abstract,
low-resolution canvas — deliberately NOT real pixel data, so importing and
unit-testing this module never needs a heavyweight image-processing runtime
(matches every other policy/model contract in this package, e.g.
`BrushAssistantPolicy`'s "deterministic proposal shell" in
`brush_assistant.py`). A real renderer maps `HIEBrushEnv` actions onto
actual document layers; this environment is the RL training/simulation
surface for the brush-assistant policy itself, not the renderer.

`gymnasium` is an optional dependency (the `rl` extra in `pyproject.toml`)
— importing this module always succeeds; only constructing `HIEBrushEnv`
requires it installed. See `HAVE_GYMNASIUM` below.
"""

from __future__ import annotations

from typing import Any

try:
    import gymnasium as gym
    import numpy as np
    from gymnasium import spaces

    HAVE_GYMNASIUM = True
except ImportError:
    gym = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    spaces = None  # type: ignore[assignment]
    HAVE_GYMNASIUM = False


#: The four local retouching tools this environment models. Index into this
#: tuple is the `Discrete` action space's `tool` value.
TOOLS = ("dodge", "burn", "sharpen", "tone")

#: Abstract canvas grid resolution — a stand-in for whatever real-image
#: statistics (local brightness/edge maps) a renderer would compute, not an
#: actual image size.
DEFAULT_CANVAS_SIZE = 16

#: How strongly one stroke can move the canvas per step, before radius
#: falloff. Kept small so `max_steps` strokes are needed to reach a target,
#: giving the RL formalism a non-trivial episode to learn over.
_STROKE_GAIN = 0.3


if HAVE_GYMNASIUM:

    class HIEBrushEnv(gym.Env):
        """Local brush-tool RL environment: dodge, burn, sharpen, and tone.

        Observation (`Dict`):
            `canvas` — `Box(0, 1, (canvas_size, canvas_size))`, the current
            abstract brightness grid.
            `cursor` — `Box(0, 1, (2,))`, the last stroke's normalized
            `(x, y)` position.

        Action (`Dict`):
            `tool` — `Discrete(4)`, indexes `TOOLS` (dodge/burn/sharpen/tone).
            `x`, `y` — `Box(0, 1, (1,))`, normalized stroke center.
            `radius` — `Box(0.05, 0.5, (1,))`, brush falloff radius.
            `strength` — `Box(0, 1, (1,))`, stroke intensity.

        Reward: `step()` returns an automatic shaping reward — how much
        closer (or further) the stroke moved the canvas toward a target
        canvas fixed at `reset()` — clipped implicitly by the bounded
        canvas values. `record_reward` additionally lets an artist (human)
        attach a reward correction to a specific *past* step after
        reviewing a rendered stroke sequence, for RLHF-style preference
        logging; it annotates history only and never replays environment
        dynamics or affects `step()`'s own return value.
        """

        metadata: dict[str, Any] = {"render_modes": []}

        def __init__(
            self,
            canvas_size: int = DEFAULT_CANVAS_SIZE,
            max_steps: int = 20,
        ) -> None:
            super().__init__()
            if canvas_size < 2:
                raise ValueError("canvas_size must be at least 2")
            if max_steps < 1:
                raise ValueError("max_steps must be at least 1")
            self.canvas_size = canvas_size
            self.max_steps = max_steps

            self.observation_space = spaces.Dict(
                {
                    "canvas": spaces.Box(
                        low=0.0, high=1.0, shape=(canvas_size, canvas_size), dtype=np.float32
                    ),
                    "cursor": spaces.Box(low=0.0, high=1.0, shape=(2,), dtype=np.float32),
                }
            )
            self.action_space = spaces.Dict(
                {
                    "tool": spaces.Discrete(len(TOOLS)),
                    "x": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32),
                    "y": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32),
                    "radius": spaces.Box(low=0.05, high=0.5, shape=(1,), dtype=np.float32),
                    "strength": spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32),
                }
            )

            self._canvas: Any = None
            self._target: Any = None
            self._cursor = None
            self._steps_taken = 0
            self._reward_log: list[dict[str, Any]] = []

        def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
            super().reset(seed=seed)
            rng = self.np_random
            self._canvas = rng.uniform(0.2, 0.8, size=(self.canvas_size, self.canvas_size)).astype(
                np.float32
            )
            self._target = rng.uniform(0.2, 0.8, size=(self.canvas_size, self.canvas_size)).astype(
                np.float32
            )
            self._cursor = np.array([0.5, 0.5], dtype=np.float32)
            self._steps_taken = 0
            self._reward_log = []
            return self._observation(), {}

        def step(self, action: dict[str, Any]):
            if self._canvas is None:
                raise RuntimeError("call reset() before step()")

            tool_idx = int(action["tool"])
            if not 0 <= tool_idx < len(TOOLS):
                raise ValueError(f"invalid tool index {tool_idx}; expected 0..{len(TOOLS) - 1}")
            tool = TOOLS[tool_idx]
            x = float(np.clip(np.asarray(action["x"]).reshape(-1)[0], 0.0, 1.0))
            y = float(np.clip(np.asarray(action["y"]).reshape(-1)[0], 0.0, 1.0))
            radius = float(np.clip(np.asarray(action["radius"]).reshape(-1)[0], 0.05, 0.5))
            strength = float(np.clip(np.asarray(action["strength"]).reshape(-1)[0], 0.0, 1.0))

            before_error = self._distance_to_target()
            self._apply_stroke(tool, x, y, radius, strength)
            after_error = self._distance_to_target()

            reward = float(before_error - after_error)  # positive = moved closer to target
            self._cursor = np.array([x, y], dtype=np.float32)
            self._steps_taken += 1
            terminated = after_error < 1e-3
            truncated = self._steps_taken >= self.max_steps

            self._reward_log.append(
                {"step": self._steps_taken - 1, "tool": tool, "reward": reward, "artist_reward": None}
            )

            info = {"tool": tool, "before_error": before_error, "after_error": after_error}
            return self._observation(), reward, terminated, truncated, info

        def record_reward(self, step_index: int, reward: float) -> None:
            """Attach an artist-supplied reward correction to a past step.

            Purely an annotation on the recorded history (see
            `reward_history`) — does not replay environment dynamics or
            change what `step()` already returned. Intended for RLHF-style
            preference logging once a human has reviewed a rendered stroke
            sequence and wants to correct the automatic shaping reward.

            Raises `ValueError` if `reward` is out of `[-1, 1]`, `IndexError`
            if `step_index` was never recorded (e.g. before any `step()`
            call, or after `reset()` cleared the log).
            """
            if not -1.0 <= reward <= 1.0:
                raise ValueError("reward must be between -1 and 1")
            for entry in self._reward_log:
                if entry["step"] == step_index:
                    entry["artist_reward"] = float(reward)
                    return
            raise IndexError(f"no recorded step {step_index} to attach a reward to")

        def reward_history(self) -> list[dict[str, Any]]:
            """Return a copy of the per-step reward log (automatic + any artist corrections)."""
            return [dict(entry) for entry in self._reward_log]

        def _observation(self) -> dict[str, Any]:
            return {"canvas": self._canvas.copy(), "cursor": self._cursor.copy()}

        def _distance_to_target(self) -> float:
            return float(np.mean(np.abs(self._canvas - self._target)))

        def _apply_stroke(self, tool: str, x: float, y: float, radius: float, strength: float) -> None:
            grid = self.canvas_size
            yy, xx = np.mgrid[0:grid, 0:grid].astype(np.float32) / max(grid - 1, 1)
            dist = np.sqrt((xx - x) ** 2 + (yy - y) ** 2)
            mask = np.clip(1.0 - dist / radius, 0.0, 1.0)  # radial falloff, 1.0 at the stroke center

            if tool == "dodge":
                self._canvas = self._canvas + mask * strength * _STROKE_GAIN
            elif tool == "burn":
                self._canvas = self._canvas - mask * strength * _STROKE_GAIN
            elif tool == "sharpen":
                local_mean = float(np.mean(self._canvas))
                self._canvas = self._canvas + mask * strength * _STROKE_GAIN * (self._canvas - local_mean)
            elif tool == "tone":
                target_tone = float(np.mean(self._target))
                self._canvas = self._canvas + mask * strength * _STROKE_GAIN * (target_tone - self._canvas)
            else:  # pragma: no cover - guarded by the tool_idx bounds check in step()
                raise ValueError(f"unknown tool: {tool!r}")

            self._canvas = np.clip(self._canvas, 0.0, 1.0).astype(np.float32)

else:

    class HIEBrushEnv:  # type: ignore[no-redef]
        """Placeholder used when `gymnasium` isn't installed.

        Importing `hie_middleware.policies.brush_env` always succeeds
        (matches this package's dependency-light contract convention, e.g.
        `models/base.py`'s docstring); only *constructing* `HIEBrushEnv`
        requires the optional `gymnasium`/`numpy` dependencies (the `rl`
        extra in `pyproject.toml`).
        """

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ModuleNotFoundError(
                "HIEBrushEnv requires the optional 'gymnasium' and 'numpy' dependencies "
                "(install the 'rl' extra) — they are not required just to import this module"
            )
