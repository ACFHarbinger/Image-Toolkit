from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.src.web.clients import jikan_client


def _resp(status_code, json_data=None):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.json.return_value = json_data or {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} Server Error", response=resp
        )
    else:
        resp.raise_for_status.side_effect = None
    return resp


@patch("time.sleep", MagicMock())
class TestGetWithRetry:
    @patch("requests.get")
    def test_succeeds_immediately_on_200(self, mock_get):
        mock_get.return_value = _resp(200, {"data": []})

        resp = jikan_client._get_with_retry("https://api.jikan.moe/v4/anime")

        assert resp.status_code == 200
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_retries_on_504_then_succeeds(self, mock_get):
        mock_get.side_effect = [_resp(504), _resp(504), _resp(200, {"data": []})]

        resp = jikan_client._get_with_retry("https://api.jikan.moe/v4/anime")

        assert resp.status_code == 200
        assert mock_get.call_count == 3

    @patch("requests.get")
    def test_exhausts_retries_and_returns_last_bad_response(self, mock_get):
        mock_get.return_value = _resp(504)

        resp = jikan_client._get_with_retry("https://api.jikan.moe/v4/anime")

        assert resp.status_code == 504
        assert mock_get.call_count == jikan_client._MAX_RETRIES + 1

    @patch("requests.get")
    def test_does_not_retry_non_transient_4xx(self, mock_get):
        mock_get.return_value = _resp(404)

        resp = jikan_client._get_with_retry("https://api.jikan.moe/v4/anime")

        assert resp.status_code == 404
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_retries_connection_errors(self, mock_get):
        mock_get.side_effect = [
            requests.ConnectionError("boom"),
            _resp(200, {"data": []}),
        ]

        resp = jikan_client._get_with_retry("https://api.jikan.moe/v4/anime")

        assert resp.status_code == 200
        assert mock_get.call_count == 2

    @patch("requests.get")
    def test_raises_after_exhausting_connection_error_retries(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("boom")

        with pytest.raises(requests.ConnectionError):
            jikan_client._get_with_retry("https://api.jikan.moe/v4/anime")

        assert mock_get.call_count == jikan_client._MAX_RETRIES + 1


@patch("time.sleep", MagicMock())
class TestFetchMalAnimeData:
    @patch("requests.get")
    def test_recovers_from_transient_504(self, mock_get):
        mock_get.side_effect = [
            _resp(504),
            _resp(200, {"data": [{"mal_id": 1, "title": "Test"}]}),
            _resp(200, {"data": []}),  # characters
            _resp(200, {"data": []}),  # staff
        ]

        result = jikan_client.fetch_mal_anime_data("Test")

        assert "error" not in result

    @patch("requests.get")
    def test_persistent_504_surfaces_network_error(self, mock_get):
        mock_get.return_value = _resp(504)

        result = jikan_client.fetch_mal_anime_data("Test")

        assert "error" in result
        assert "504" in result["error"]

    @patch("requests.get")
    def test_persistent_504_explains_upstream_outage_not_generic_network_error(
        self, mock_get
    ):
        resp = _resp(504)
        resp.json.return_value = {
            "status": 504,
            "type": "BadResponseException",
            "message": (
                "Jikan failed to connect to MyAnimeList. MyAnimeList may be "
                "down/unavailable or refuses to connect"
            ),
            "error": None,
        }
        mock_get.return_value = resp

        result = jikan_client.fetch_mal_anime_data("Kutsujoku")

        assert "error" in result
        assert "Jikan" in result["error"]
        assert "MyAnimeList" in result["error"]
        assert "Kutsujoku" in result["error"]
