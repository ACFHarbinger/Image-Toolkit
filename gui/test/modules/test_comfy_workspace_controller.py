import time

import pytest
from backend.src.constants.comfy import ServerState, ViewState
from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController
from PySide6.QtTest import QTest as qt_test

pytestmark = pytest.mark.gui


class Manager:
    state = ServerState.STOPPED
    owns_server = False
    url = "http://127.0.0.1:8188"
    port = 8188

    def __init__(self):
        self.stops = 0
        self.starts = 0
        self.listener = lambda state: None
        self.runs_listener = lambda record: None

    def subscribe_state(self, listener):
        self.listener = listener

    def subscribe_log(self, listener):
        pass

    def subscribe_runs(self, listener):
        self.runs_listener = listener

    def subscribe_object_info(self, listener):
        pass

    def get_object_info(self):
        return {}

    def validate_template(self, template, **kwargs):
        return []

    def set_state(self, state):
        self.state = state
        self.listener(state)

    def start(self, *args, **kwargs):
        self.starts += 1
        self.owns_server = True
        self.set_state(ServerState.STARTING)

    def wait_until_ready(self, **kwargs):
        self.set_state(ServerState.READY)
        return True

    def connect(self, port):
        self.port = port
        self.set_state(ServerState.READY)
        return True

    def stop(self):
        self.stops += 1
        self.owns_server = False
        self.set_state(ServerState.STOPPED)

    def refresh_state(self):
        return self.state == ServerState.READY


def settle(controller):
    deadline = time.monotonic() + 2
    while controller.busy and time.monotonic() < deadline:
        qt_test.qWait(5)
    assert not controller.busy


@pytest.fixture
def controller(q_app):
    manager = Manager()
    coordinator = ComfyWorkspaceController(manager, opener=lambda _url: True)
    yield coordinator
    coordinator.shutdown()


def test_ready_without_view_and_browser_failure_is_independent(controller):
    controller.start()
    settle(controller)
    assert controller.server_state == ServerState.READY
    assert controller.view_state == ViewState.NOT_CREATED
    assert controller.open_external()
    controller._opener = lambda url: False
    assert not controller.open_external()
    assert controller.server_state == ServerState.READY
    assert controller.manager.starts == 1
    assert controller.view_state == ViewState.NOT_CREATED


def test_stop_cancels_start_and_never_restarts(controller):
    def pending(**kwargs):
        kwargs["cancel"].wait(1)
        return False
    controller.manager.wait_until_ready = pending
    controller.start()
    controller.start()
    controller.stop()
    settle(controller)
    assert controller.server_state == ServerState.STOPPED
    assert controller.manager.starts == 1
    assert controller.manager.stops == 1


def test_tab_close_does_not_stop_shared_service(controller):
    from gui.src.tabs.models.gen.comfy_generate_tab import ComfyUITab
    controller.connect()
    settle(controller)
    tab = ComfyUITab(controller=controller)
    assert tab._stop_btn.text() == "Disconnect"
    assert tab._open_btn.isEnabled()
    tab.close()
    assert controller.manager.stops == 0
    assert controller.view_state == ViewState.NOT_CREATED


def test_server_restart_does_not_construct_view(controller):
    controller.start()
    settle(controller)
    controller.stop()
    settle(controller)
    controller.start()
    settle(controller)
    assert controller.manager.starts == 2
    assert controller.server_state == ServerState.READY
    assert controller.view_state == ViewState.NOT_CREATED


def test_http_action_runs_off_ui_thread(controller):
    import threading
    seen = []
    controller.connect()
    settle(controller)
    ui_thread = threading.get_ident()
    assert controller.run_http_action(lambda: seen.append(threading.get_ident()))
    settle(controller)
    assert seen and seen[0] != ui_thread


def test_run_records_are_forwarded_as_signal(controller):
    record = object()
    received = []
    controller.run_record_changed.connect(received.append)
    controller.manager.runs_listener(record)
    qt_test.qWait(10)
    assert received == [record]


def test_shutdown_stops_run_forwarding(controller):
    received = []
    controller.run_record_changed.connect(received.append)
    controller.shutdown()
    controller.manager.runs_listener(object())
    qt_test.qWait(10)
    assert received == []
