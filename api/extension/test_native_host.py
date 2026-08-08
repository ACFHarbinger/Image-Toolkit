"""Tests for the §7.5B native-messaging host (`native_host.py`).

Reuses `BridgeTestCase`'s isolated bridge-dir setup from `tests.py` so
`dispatch()` (which calls straight into `bridge_handlers`, the same
functions the HTTP views use) exercises real config/token/index paths
without touching the real `~/.image-toolkit/` directory.
"""

import io
import struct

from api.extension import native_host
from api.extension.tests import BridgeTestCase, _png_bytes


class TestFraming(BridgeTestCase):
    """Wire-protocol round-trip: 4-byte native-order length + UTF-8 JSON."""

    def test_write_then_read_round_trips(self):
        stream = io.BytesIO()
        native_host.write_message(stream, {"hello": "world", "n": 3})
        stream.seek(0)
        msg = native_host.read_message(stream)
        self.assertEqual(msg, {"hello": "world", "n": 3})

    def test_read_returns_none_at_eof(self):
        stream = io.BytesIO(b"")
        self.assertIsNone(native_host.read_message(stream))

    def test_read_returns_none_on_truncated_length_prefix(self):
        stream = io.BytesIO(b"\x01\x02")  # fewer than 4 bytes
        self.assertIsNone(native_host.read_message(stream))

    def test_read_returns_none_on_truncated_body(self):
        stream = io.BytesIO(struct.pack("@I", 100) + b"short")
        self.assertIsNone(native_host.read_message(stream))

    def test_write_message_length_prefix_matches_body(self):
        stream = io.BytesIO()
        native_host.write_message(stream, {"x": 1})
        stream.seek(0)
        (length,) = struct.unpack("@I", stream.read(4))
        body = stream.read(length)
        self.assertEqual(len(body), length)
        self.assertEqual(body.decode("utf-8"), '{"x": 1}')


class TestDispatch(BridgeTestCase):
    """`dispatch()` routes to the same `bridge_handlers` the HTTP views use."""

    def test_unknown_action_returns_400(self):
        resp = native_host.dispatch({"action": "not_a_real_action"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["status"], 400)
        self.assertIn("error", resp["body"])

    def test_ping_matches_http_ping_shape(self):
        resp = native_host.dispatch({"action": "ping"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["status"], 200)
        self.assertEqual(resp["body"]["dup_root_configured"], True)
        self.assertIn("version", resp["body"])
        self.assertIn("features", resp["body"])

    def test_dup_check_missing_payload_key_defaults_to_empty(self):
        # No "payload" key at all -> handler gets {} -> 400 (needs url/data_b64).
        resp = native_host.dispatch({"action": "dup_check"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["status"], 400)

    def test_dup_check_finds_match_via_shared_handler(self):
        import base64

        data = _png_bytes(seed=1)
        (self.images_dir / "existing.png").write_bytes(data)
        resp = native_host.dispatch(
            {
                "action": "dup_check",
                "payload": {"data_b64": base64.b64encode(data).decode()},
            }
        )
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["status"], 200)
        self.assertEqual(len(resp["body"]["matches"]), 1)

    def test_handler_exception_returns_500_not_a_crash(self):
        from unittest import mock

        with mock.patch(
            "api.extension.bridge_handlers.handle_ping",
            side_effect=RuntimeError("boom"),
        ):
            resp = native_host.dispatch({"action": "ping"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["status"], 500)
        self.assertIn("boom", resp["body"]["error"])
