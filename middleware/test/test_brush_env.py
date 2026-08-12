"""Tests for `policies.brush_env.HIEBrushEnv`.

`gymnasium` (and `numpy`) are optional dependencies (the `rl` extra) — the
import-time contract (module always importable, `HIEBrushEnv()` raises a
clear `ModuleNotFoundError` when the extra isn't installed) is tested
unconditionally; everything that constructs a real environment is gated on
`HAVE_GYMNASIUM`.
"""

import pytest

from policies.brush_env import HAVE_GYMNASIUM, TOOLS, HIEBrushEnv

requires_gymnasium = pytest.mark.skipif(
    not HAVE_GYMNASIUM, reason="gymnasium/numpy not installed (optional 'rl' extra)"
)


def test_brush_env_raises_clear_error_without_gymnasium():
    if HAVE_GYMNASIUM:
        pytest.skip("gymnasium is installed in this environment; nothing to assert here")
    with pytest.raises(ModuleNotFoundError, match="gymnasium"):
        HIEBrushEnv()


@requires_gymnasium
def test_brush_env_conforms_to_gymnasium_api():
    from gymnasium.utils.env_checker import check_env

    env = HIEBrushEnv(canvas_size=8, max_steps=5)
    check_env(env, skip_render_check=True)


@requires_gymnasium
def test_brush_env_rejects_invalid_construction_args():
    with pytest.raises(ValueError, match="canvas_size"):
        HIEBrushEnv(canvas_size=1)
    with pytest.raises(ValueError, match="max_steps"):
        HIEBrushEnv(max_steps=0)


@requires_gymnasium
def test_brush_env_reset_is_reproducible_for_the_same_seed():
    import numpy as np

    env_a = HIEBrushEnv(canvas_size=6, max_steps=3)
    obs_a, _ = env_a.reset(seed=99)
    env_b = HIEBrushEnv(canvas_size=6, max_steps=3)
    obs_b, _ = env_b.reset(seed=99)
    assert np.array_equal(obs_a["canvas"], obs_b["canvas"])
    assert np.array_equal(obs_a["cursor"], obs_b["cursor"])


@requires_gymnasium
def test_brush_env_step_before_reset_raises():
    env = HIEBrushEnv()
    with pytest.raises(RuntimeError, match="reset"):
        env.step(env.action_space.sample())


@requires_gymnasium
def test_brush_env_truncates_at_max_steps():
    env = HIEBrushEnv(canvas_size=6, max_steps=3)
    env.reset(seed=1)
    truncated = False
    for _ in range(3):
        _, _, terminated, truncated, _ = env.step(env.action_space.sample())
        if terminated:
            break
    assert truncated or terminated


@requires_gymnasium
@pytest.mark.parametrize("tool_index,tool_name", list(enumerate(TOOLS)))
def test_brush_env_each_tool_moves_the_canvas_in_its_expected_direction(tool_index, tool_name):
    import numpy as np

    env = HIEBrushEnv(canvas_size=8, max_steps=10)
    obs, _ = env.reset(seed=7)
    before_center = float(obs["canvas"][4, 4])

    action = {
        "tool": tool_index,
        "x": np.array([0.5], dtype=np.float32),
        "y": np.array([0.5], dtype=np.float32),
        "radius": np.array([0.3], dtype=np.float32),
        "strength": np.array([1.0], dtype=np.float32),
    }
    obs2, reward, *_ = env.step(action)
    after_center = float(obs2["canvas"][4, 4])

    if tool_name == "dodge":
        assert after_center > before_center
    elif tool_name == "burn":
        assert after_center < before_center
    else:
        # sharpen/tone move the pixel toward or away from a reference value
        # (local mean / target tone) rather than in one fixed direction —
        # just assert the stroke actually changed something.
        assert after_center != before_center


@requires_gymnasium
def test_brush_env_record_reward_attaches_to_correct_step():
    env = HIEBrushEnv(canvas_size=6, max_steps=5)
    env.reset(seed=3)
    env.step(env.action_space.sample())
    env.step(env.action_space.sample())

    env.record_reward(0, 0.9)
    history = env.reward_history()
    assert history[0]["artist_reward"] == 0.9
    assert history[1]["artist_reward"] is None


@requires_gymnasium
def test_brush_env_record_reward_validates_range_and_step_index():
    env = HIEBrushEnv(canvas_size=6, max_steps=5)
    env.reset(seed=3)
    env.step(env.action_space.sample())

    with pytest.raises(ValueError, match="between -1 and 1"):
        env.record_reward(0, 5.0)
    with pytest.raises(IndexError):
        env.record_reward(999, 0.5)


@requires_gymnasium
def test_brush_env_reset_clears_reward_history():
    env = HIEBrushEnv(canvas_size=6, max_steps=5)
    env.reset(seed=1)
    env.step(env.action_space.sample())
    assert env.reward_history()

    env.reset(seed=2)
    assert env.reward_history() == []


@requires_gymnasium
def test_brush_env_rejects_out_of_range_tool_index():
    env = HIEBrushEnv(canvas_size=6, max_steps=5)
    env.reset(seed=1)
    action = {
        "tool": len(TOOLS),  # out of range
        "x": [0.5],
        "y": [0.5],
        "radius": [0.2],
        "strength": [0.5],
    }
    with pytest.raises(ValueError, match="invalid tool index"):
        env.step(action)
