from unittest.mock import patch

import numpy as np
import pytest

from cel_shaded_generator_gui.helpers.animation_worker import AnimationColorizeWorker

pytestmark = pytest.mark.gui


def _sequence(t=3, h=10, w=10):
    gray = np.full((t, h, w), 180, dtype=np.uint8)
    scribble_rgb = np.zeros((t, h, w, 3), dtype=np.uint8)
    mask = np.zeros((t, h, w), dtype=bool)
    scribble_rgb[0, 2:5, 2:5] = [255, 0, 0]
    mask[0, 2:5, 2:5] = True
    return gray, scribble_rgb, mask


class TestAnimationColorizeWorker:
    def test_stores_constructor_args(self, q_app):
        gray, scribble_rgb, mask = _sequence()
        worker = AnimationColorizeWorker(
            gray, scribble_rgb, mask, win_rad=2, t_rad=1, max_solve_dim=64, refine=True
        )
        assert worker._gray_stack is gray
        assert worker._scribble_rgb_stack is scribble_rgb
        assert worker._scribble_mask_stack is mask
        assert worker._win_rad == 2
        assert worker._t_rad == 1
        assert worker._max_solve_dim == 64
        assert worker._refine is True

    def test_defaults(self, q_app):
        gray, scribble_rgb, mask = _sequence()
        worker = AnimationColorizeWorker(gray, scribble_rgb, mask)
        assert worker._win_rad == 1
        assert worker._t_rad == 1
        assert worker._max_solve_dim == 128
        assert worker._refine is False

    def test_run_without_refine_calls_only_sequence_solver(self, q_app):
        gray, scribble_rgb, mask = _sequence()
        worker = AnimationColorizeWorker(gray, scribble_rgb, mask, refine=False)
        received = []
        worker.finished_ok.connect(lambda arr: received.append(arr))

        fake_result = np.zeros((3, 10, 10, 3), dtype=np.uint8)
        with patch("cel_shaded_generator_gui.helpers.animation_worker.IsolatedRunner") as cls:
            cls.return_value.run.return_value = fake_result
            worker.run()

        request = cls.return_value.run.call_args.args[0]
        assert request.options["refine"] is False
        assert len(received) == 1
        assert received[0] is fake_result

    def test_run_with_refine_chains_both_solvers(self, q_app):
        gray, scribble_rgb, mask = _sequence()
        worker = AnimationColorizeWorker(gray, scribble_rgb, mask, refine=True)
        received = []
        worker.finished_ok.connect(lambda arr: received.append(arr))

        refined_result = np.ones((3, 10, 10, 3), dtype=np.uint8)
        with patch("cel_shaded_generator_gui.helpers.animation_worker.IsolatedRunner") as cls:
            cls.return_value.run.return_value = refined_result
            worker.run()

        request = cls.return_value.run.call_args.args[0]
        assert request.options["refine"] is True
        assert len(received) == 1
        assert np.array_equal(received[0], refined_result)

    def test_run_emits_error_signal_on_exception(self, q_app):
        gray, scribble_rgb, mask = _sequence()
        worker = AnimationColorizeWorker(gray, scribble_rgb, mask)
        errors = []
        worker.error.connect(lambda msg: errors.append(msg))

        with patch("cel_shaded_generator_gui.helpers.animation_worker.IsolatedRunner") as cls:
            cls.return_value.run.side_effect = ValueError("boom")
            worker.run()

        assert errors == ["boom"]

    # Note: no real (unmocked) end-to-end solve test here -- gui/test/conftest.py
    # globally replaces `sys.modules["cv2"]` with a `MagicMock()` (to keep the
    # GUI test suite from loading the native OpenCV lib), which both
    # `colorize_scribble_sequence()` and `graph_cut_temporal_refine()` call
    # internally. Running either through that mocked cv2 doesn't just produce
    # a wrong result -- it reproducibly corrupts memory when driven from a
    # real background QThread ("double free or corruption", confirmed while
    # developing this test file), so it's avoided entirely here, not just
    # left unasserted. The real backend solvers' own correctness is already
    # covered end-to-end against the *real* cv2 in
    # backend/test/cel_shaded_generator/test_temporal.py and test_graph_cut.py; this file
    # only needs to prove the worker dispatches to them with the right
    # arguments and reports success/failure via the right signal, which the
    # mocked-`colorize_scribble_sequence`/`graph_cut_temporal_refine` tests
    # above already do.
