"""Tests for the browser-extension bridge endpoints (§7.5A / §7.6)."""

import base64
import io
import shutil
from pathlib import Path
from unittest import mock

import numpy as np
from django.test import Client, SimpleTestCase
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


class TestIngest(BridgeTestCase):
    def _post(self, payload):
        return self.client.post(
            "/api/extension/ingest/",
            payload,
            content_type="application/json",
            **self._auth(),
        )

    def test_saves_image_with_sidecar(self):
        data = _png_bytes(seed=11)
        resp = self._post(
            {
                "data_b64": base64.b64encode(data).decode(),
                "url": "https://site.com/imgs/photo.png",
                "source_page_url": "https://site.com/gallery",
                "page_title": "Gallery",
            }
        )
        self.assertEqual(resp.status_code, 201)
        saved = Path(resp.json()["path"])
        self.assertTrue(saved.exists())
        self.assertEqual(saved.name, "photo.png")
        self.assertEqual(saved.parent, self.images_dir / "inbox")
        import json

        sidecar = json.loads((saved.parent / (saved.name + ".json")).read_text())
        self.assertEqual(sidecar["page_url"], "https://site.com/gallery")
        self.assertEqual(sidecar["page_title"], "Gallery")

    def test_uniquifies_existing_names(self):
        data1 = _png_bytes(seed=21)
        data2 = _png_bytes(seed=22)
        payload = {"url": "https://site.com/a.png"}
        r1 = self._post({**payload, "data_b64": base64.b64encode(data1).decode()})
        r2 = self._post({**payload, "data_b64": base64.b64encode(data2).decode()})
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertNotEqual(r1.json()["path"], r2.json()["path"])

    def test_409_for_known_duplicate(self):
        data = _png_bytes(seed=31)
        (self.images_dir / "existing.png").write_bytes(data)
        resp = self._post({"data_b64": base64.b64encode(data).decode()})
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(resp.json()["existing"][0].endswith("existing.png"))

    def test_force_bypasses_dup_check(self):
        data = _png_bytes(seed=31)
        (self.images_dir / "existing.png").write_bytes(data)
        resp = self._post(
            {"data_b64": base64.b64encode(data).decode(), "force": True}
        )
        self.assertEqual(resp.status_code, 201)

    def test_409_when_no_dirs_configured(self):
        from extension_api.bridge_config import save_config

        save_config({"dup_root": "", "ingest_dir": ""})
        resp = self._post({"data_b64": base64.b64encode(_png_bytes()).decode()})
        self.assertEqual(resp.status_code, 409)


class TestSimilar(BridgeTestCase):
    """§7.8 ranked visual-similarity search (pHash-degraded path)."""

    def _post(self, payload):
        return self.client.post(
            "/api/extension/similar/",
            payload,
            content_type="application/json",
            **self._auth(),
        )

    def test_requires_token(self):
        resp = self.client.post(
            "/api/extension/similar/", {}, content_type="application/json"
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

    def test_ranked_results_sorted_and_scored(self):
        query = _png_bytes(seed=100)
        (self.images_dir / "exact.png").write_bytes(query)
        (self.images_dir / "other1.png").write_bytes(_png_bytes(seed=101))
        (self.images_dir / "other2.png").write_bytes(_png_bytes(seed=102))

        resp = self._post({"data_b64": base64.b64encode(query).decode()})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["method"], "phash")
        self.assertEqual(body["scanned"], 3)
        self.assertEqual(len(body["results"]), 3)

        # Sorted nearest-first: hamming ascending == score descending.
        hammings = [r["hamming"] for r in body["results"]]
        self.assertEqual(hammings, sorted(hammings))
        scores = [r["score"] for r in body["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

        best = body["results"][0]
        self.assertTrue(best["path"].endswith("exact.png"))
        self.assertEqual(best["hamming"], 0)
        self.assertEqual(best["score"], 1.0)
        self.assertIsNotNone(best["thumb_b64"])
        self.assertEqual(best["width"], 64)

    def test_top_k_limits_result_count(self):
        query = _png_bytes(seed=200)
        for i in range(5):
            (self.images_dir / f"lib{i}.png").write_bytes(_png_bytes(seed=200 + i))

        resp = self._post(
            {"data_b64": base64.b64encode(query).decode(), "top_k": 2}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["results"]), 2)

    def test_top_k_defaults_to_twelve(self):
        for i in range(20):
            (self.images_dir / f"lib{i}.png").write_bytes(_png_bytes(seed=300 + i))

        resp = self._post(
            {"data_b64": base64.b64encode(_png_bytes(seed=300)).decode()}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["results"]), 12)

    def test_returns_results_even_beyond_dup_check_threshold(self):
        # Unlike dup-check, /similar/ never returns an empty list just
        # because nothing is a close match — it always ranks what exists.
        (self.images_dir / "unrelated.png").write_bytes(_png_bytes(seed=999))
        resp = self._post(
            {"data_b64": base64.b64encode(_png_bytes(seed=1)).decode()}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["results"]), 1)


class TestPhashSnapshot(BridgeTestCase):
    """§7.16C client-side pre-check snapshot export."""

    def _get(self):
        return self.client.get("/api/extension/phash-snapshot/", **self._auth())

    def test_requires_token(self):
        resp = self.client.get("/api/extension/phash-snapshot/")
        self.assertEqual(resp.status_code, 403)

    def test_409_when_root_unconfigured(self):
        from extension_api.bridge_config import save_config

        save_config({"dup_root": ""})
        resp = self._get()
        self.assertEqual(resp.status_code, 409)

    def test_empty_library_returns_empty_snapshot(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["hashes"], [])
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["scanned"], 0)
        self.assertTrue(body["cold_scan"])
        self.assertIn("generated_at", body)

    def test_exports_distinct_sorted_hex_hashes(self):
        for i in range(5):
            (self.images_dir / f"lib{i}.png").write_bytes(_png_bytes(seed=400 + i))
        # A byte-identical duplicate must not double-count in the snapshot.
        (self.images_dir / "dup_of_lib0.png").write_bytes(_png_bytes(seed=400))

        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["scanned"], 6)
        # 5 distinct source images -> at most 5 distinct hashes (could be
        # fewer if two different random seeds happen to collide, which is
        # possible but never more than the distinct-image count).
        self.assertLessEqual(body["count"], 5)
        self.assertEqual(len(body["hashes"]), body["count"])
        self.assertEqual(body["hashes"], sorted(body["hashes"]))
        # Every hash is a 16-hex-digit (64-bit) lowercase string.
        for h in body["hashes"]:
            self.assertEqual(len(h), 16)
            self.assertEqual(h, h.lower())
            int(h, 16)  # raises if not valid hex

    def test_no_paths_leaked_in_snapshot(self):
        (self.images_dir / "secret_filename.png").write_bytes(_png_bytes(seed=500))
        resp = self._get()
        body_text = resp.content.decode()
        self.assertNotIn("secret_filename", body_text)
        self.assertNotIn(str(self.images_dir), body_text)
