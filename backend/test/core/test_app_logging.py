"""GUI/UX §2.9F (issue #48): log_level / file_logging_enabled preference wiring."""
import logging
import logging.handlers

import pytest

from backend.src.app import (
    _LOG_FILE_HANDLER_TAG,
    _make_file_handler,
    _reconfigure_logging,
)


@pytest.fixture(autouse=True)
def _clean_root_logger():
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    for h in saved_handlers:
        root.removeHandler(h)
    yield
    for h in list(root.handlers):
        root.removeHandler(h)
        if isinstance(h, logging.handlers.RotatingFileHandler):
            h.close()
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)


def test_make_file_handler_is_tagged():
    handler = _make_file_handler()
    try:
        assert getattr(handler, _LOG_FILE_HANDLER_TAG, False) is True
        assert isinstance(handler, logging.handlers.RotatingFileHandler)
    finally:
        handler.close()


def test_reconfigure_sets_console_level_from_preference():
    root = logging.getLogger()
    console = logging.StreamHandler()
    root.addHandler(console)

    _reconfigure_logging("DEBUG", file_logging_enabled=False)
    assert console.level == logging.DEBUG

    _reconfigure_logging("WARNING", file_logging_enabled=False)
    assert console.level == logging.WARNING


def test_reconfigure_adds_file_handler_when_enabled():
    root = logging.getLogger()
    assert not any(getattr(h, _LOG_FILE_HANDLER_TAG, False) for h in root.handlers)

    _reconfigure_logging("INFO", file_logging_enabled=True)
    assert any(getattr(h, _LOG_FILE_HANDLER_TAG, False) for h in root.handlers)


def test_reconfigure_removes_file_handler_when_disabled():
    root = logging.getLogger()
    root.addHandler(_make_file_handler())
    assert any(getattr(h, _LOG_FILE_HANDLER_TAG, False) for h in root.handlers)

    _reconfigure_logging("INFO", file_logging_enabled=False)
    assert not any(getattr(h, _LOG_FILE_HANDLER_TAG, False) for h in root.handlers)


def test_reconfigure_is_idempotent_when_already_enabled():
    root = logging.getLogger()
    _reconfigure_logging("INFO", file_logging_enabled=True)
    count_after_first = sum(
        1 for h in root.handlers if getattr(h, _LOG_FILE_HANDLER_TAG, False)
    )
    _reconfigure_logging("INFO", file_logging_enabled=True)
    count_after_second = sum(
        1 for h in root.handlers if getattr(h, _LOG_FILE_HANDLER_TAG, False)
    )
    assert count_after_first == count_after_second == 1


def test_reconfigure_unknown_level_name_defaults_to_info():
    root = logging.getLogger()
    console = logging.StreamHandler()
    root.addHandler(console)

    _reconfigure_logging("NOT_A_REAL_LEVEL", file_logging_enabled=False)
    assert console.level == logging.INFO
