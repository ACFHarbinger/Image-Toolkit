"""Tests for the browser-extension bridge endpoints (§7.5A / §7.6)."""

import base64
import io
import shutil
from pathlib import Path
from unittest import mock

import numpy as np
from django.test import SimpleTestCase, Client
from PIL import Image


def _png_bytes(seed=0, size=(64, 64)) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (*size, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "PNG")
    return buf.getvalue()


class BridgeTestCase(SimpleTestCase):
    """Common setup: isolated bridge dir (token/config/index) in a temp path."""

    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp(prefix="ext_bridge_test_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.images_dir = self.tmp / "library"
        self.images_dir.mkdir()

        # Redirect token/config/index storage away from the real home dir
        patches = [
            mock.patch(
                "extension_api.bridge_config.TOKEN_PATH", self.tmp / "token.txt"
            ),
            mock.patch(
                "extension_api.bridge_config.CONFIG_PATH", self.tmp / "config.json"
            ),
            mock.patch(
                "extension_api.bridge_config.BRIDGE_DIR", self.tmp
            ),
            mock.patch(
                "backend.src.core.dir_phash_index.DEFAULT_DB_PATH",
                self.tmp / "phash_index.db",
            ),
            mock.patch(
                "backend.src.core.dir_phash_index.BRIDGE_DIR", self.tmp
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        from extension_api.bridge_config import get_token, save_config

        self.token = get_token()
        save_config({"dup_root": str(self.images_dir), "recursive": True, "threshold": 10})
        self.client = Client()

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}


class TestPing(BridgeTestCase):
    def test_rejects_missing_token(self):
        resp = self.client.get("/api/extension/ping/")
        self.assertEqual(resp.status_code, 403)

    def test_rejects_wrong_token(self):
        resp = self.client.get(
            "/api/extension/ping/", HTTP_AUTHORIZATION="Bearer wrong"
        )
        self.assertEqual(resp.status_code, 403)

    def test_ok_with_token(self):
        resp = self.client.get("/api/extension/ping/", **self._auth())
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("dup-check", body["features"])
        self.assertTrue(body["dup_root_configured"])

    def test_cors_preflight(self):
        resp = self.client.options(
            "/api/extension/ping/", HTTP_ORIGIN="chrome-extension://abc"
        )
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(
            resp["Access-Control-Allow-Origin"], "chrome-extension://abc"
        )
        self.assertIn("Authorization", resp["Access-Control-Allow-Headers"])


class TestDupCheck(BridgeTestCase):
    def _post(self, payload):
        return self.client.post(
            "/api/extension/dup-check/",
            payload,
            content_type="application/json",
            **self._auth(),
        )

    def test_requires_token(self):
        resp = self.client.post(
            "/api/extension/dup-check/", {}, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 403)

    def test_409_when_root_unconfigured(self):
        from extension_api.bridge_config import save_config

        save_config({"dup_root": ""})
        resp = self._post({"data_b64": base64.b64encode(_png_bytes()).decode()})
        self.assertEqual(resp.status_code, 409)

    def test_400_without_url_or_data(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)

    def test_400_on_undecodable_image(self):
        resp = self._post({"data_b64": base64.b64encode(b"not an image").decode()})
        self.assertEqual(resp.status_code, 400)

    def test_finds_duplicate_in_library(self):
        data = _png_bytes(seed=7)
        (self.images_dir / "existing.png").write_bytes(data)
        (self.images_dir / "other.png").write_bytes(_png_bytes(seed=8))

        resp = self._post({"data_b64": base64.b64encode(data).decode()})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["scanned"], 2)
        self.assertEqual(len(body["matches"]), 1)
        match = body["matches"][0]
        self.assertEqual(match["hamming"], 0)
        self.assertTrue(match["path"].endswith("existing.png"))
        self.assertEqual(match["width"], 64)
        self.assertIsNotNone(match["thumb_b64"])

    def test_no_match_for_unseen_image(self):
        (self.images_dir / "other.png").write_bytes(_png_bytes(seed=9))
        resp = self._post(
            {"data_b64": base64.b64encode(_png_bytes(seed=42)).decode(), "threshold": 5}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["matches"], [])
