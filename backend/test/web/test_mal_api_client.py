from unittest.mock import MagicMock, patch

from backend.src.web.clients import mal_api_client


class TestFetchMalAnimeData:
    @patch("backend.src.web.clients.mal_api_client._client_id", return_value=None)
    def test_missing_client_id_returns_actionable_error(self, mock_client_id):
        result = mal_api_client.fetch_mal_anime_data("Naruto")

        assert "error" in result
        assert "client ID" in result["error"]

    @patch("backend.src.web.clients.mal_api_client._client_id", return_value="abc123")
    @patch("requests.get")
    def test_successful_lookup(self, mock_get, mock_client_id):
        search_resp = MagicMock(ok=True)
        search_resp.json.return_value = {"data": [{"node": {"id": 20}}]}
        detail_resp = MagicMock(ok=True)
        detail_resp.json.return_value = {
            "synopsis": "A ninja story.",
            "num_episodes": 220,
            "mean": 8.02,
            "status": "finished_airing",
            "genres": [{"name": "Action"}, {"name": "Adventure"}],
            "start_season": {"year": 2002},
            "studios": [{"name": "Studio Pierrot"}],
        }
        mock_get.side_effect = [search_resp, detail_resp]

        result = mal_api_client.fetch_mal_anime_data("Naruto")

        assert result["synopsis"] == "A ninja story."
        assert result["episodes"] == 220
        assert result["score"] == 8.02
        assert result["status"] == "Completed"
        assert result["genres"] == "Action, Adventure"
        assert result["year"] == 2002
        assert result["studios"] == ["Studio Pierrot"]
        assert result["mal_url"] == "https://myanimelist.net/anime/20"
        assert result["characters_available"] is False
        assert result["characters"] == []

    @patch("backend.src.web.clients.mal_api_client._client_id", return_value="abc123")
    @patch("requests.get")
    def test_no_results(self, mock_get, mock_client_id):
        search_resp = MagicMock(ok=True)
        search_resp.json.return_value = {"data": []}
        mock_get.return_value = search_resp

        result = mal_api_client.fetch_mal_anime_data("Nonexistent Title")

        assert "error" in result
        assert "No results found" in result["error"]

    @patch("backend.src.web.clients.mal_api_client._client_id", return_value="abc123")
    @patch("requests.get")
    def test_search_http_error_surfaces_status(self, mock_get, mock_client_id):
        search_resp = MagicMock(ok=False, status_code=401, text="Invalid client ID")
        mock_get.return_value = search_resp

        result = mal_api_client.fetch_mal_anime_data("Naruto")

        assert "error" in result
        assert "401" in result["error"]
