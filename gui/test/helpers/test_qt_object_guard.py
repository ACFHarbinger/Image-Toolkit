"""R0.6 (#552): the shared deleted-QObject guard swallows only teardown races."""

from __future__ import annotations

import logging

import pytest

from gui.src.qt_object_guard import deleted_qobject_guard, is_deleted_qobject_error


class TestIsDeletedQObjectError:
    def test_pyside_message(self):
        assert is_deleted_qobject_error(RuntimeError("Internal C++ object (QLabel) already deleted.")) is True

    def test_pyqt_message(self):
        assert is_deleted_qobject_error(
            RuntimeError("wrapped C/C++ object of type QWidget has been deleted")
        ) is True

    def test_reference_error(self):
        assert is_deleted_qobject_error(ReferenceError("weakly-referenced object no longer exists")) is True

    def test_unrelated_runtime_error(self):
        assert is_deleted_qobject_error(RuntimeError("boom")) is False

    def test_other_types(self):
        assert is_deleted_qobject_error(ValueError("nope")) is False


class TestDeletedQObjectGuard:
    def test_swallow_deleted(self):
        deleted_qobject_guard(RuntimeError("Internal C++ object already deleted."), "card teardown")

    def test_reraise_unrelated(self):
        with pytest.raises(RuntimeError, match="boom"):
            deleted_qobject_guard(RuntimeError("boom"), "card teardown")

    def test_reraise_wrong_type(self):
        with pytest.raises(ValueError, match="nope"):
            deleted_qobject_guard(ValueError("nope"), "card teardown")

    def test_swallow_logs_debug(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="gui.src.qt_object_guard"):
            deleted_qobject_guard(RuntimeError("already deleted."), "card teardown")
        assert "card teardown" in caplog.text
