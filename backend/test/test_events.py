"""Unit tests for the issue #529 ``Observable`` event primitive."""

import ast
import threading
from pathlib import Path

from backend.src.events import Observable


def test_publish_delivers_to_subscriber_in_order():
    obs: Observable[str] = Observable()
    seen = []
    obs.subscribe(seen.append)
    obs.publish("a")
    obs.publish("b")
    assert seen == ["a", "b"]


def test_multiple_subscribers_all_receive():
    obs: Observable[int] = Observable()
    first, second = [], []
    obs.subscribe(first.append)
    obs.subscribe(second.append)
    obs.publish(1)
    assert first == [1]
    assert second == [1]


def test_unsubscribe_stops_delivery_and_is_repeat_safe():
    obs: Observable[str] = Observable()
    seen = []
    unsubscribe = obs.subscribe(seen.append)
    obs.publish("before")
    unsubscribe()
    unsubscribe()  # must not raise
    obs.publish("after")
    assert seen == ["before"]


def test_instances_do_not_share_subscribers():
    first: Observable[str] = Observable()
    second: Observable[str] = Observable()
    seen = []
    first.subscribe(seen.append)
    second.publish("x")
    assert seen == []


def test_raising_subscriber_does_not_break_others_or_publish():
    obs: Observable[str] = Observable()

    def bad(_event):
        raise RuntimeError("listener bug")

    seen = []
    obs.subscribe(bad)
    obs.subscribe(seen.append)
    obs.publish("go")  # must not propagate the RuntimeError
    assert seen == ["go"]


def test_concurrent_publish_from_threads_delivers_all():
    obs: Observable[int] = Observable()
    seen = []
    lock = threading.Lock()

    def record(value):
        with lock:
            seen.append(value)

    obs.subscribe(record)
    threads = [
        threading.Thread(target=obs.publish, args=(i,)) for i in range(50)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(seen) == list(range(50))


def test_subscribe_during_publish_does_not_deadlock_or_drop():
    # RLock: a subscriber that subscribes mid-publish must not deadlock,
    # and the snapshot semantics mean it only sees later events.
    obs: Observable[str] = Observable()
    late = []
    obs.subscribe(lambda _e: obs.subscribe(late.append))
    obs.publish("one")
    obs.publish("two")
    assert late == ["two"]


def test_events_module_has_zero_qt_imports():
    # D7 hard constraint, self-tested: Observable must not import PySide.
    # AST-based (not sys.modules) so the result cannot depend on which
    # Qt modules the test session already imported.
    path = Path(__file__).resolve().parents[1] / "src" / "events.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    qt_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            (alias.name == "PySide6" or alias.name.startswith("PySide6."))
            for alias in node.names
        )
    ]
    assert qt_imports == []
