from unittest.mock import MagicMock, patch

from backend.src.web.clients import mal_dispatcher


class TestFetchMalAnimeData:
    def test_defaults_to_jikan(self):
        mock_jikan = MagicMock(return_value={"synopsis": "x"})
        with patch.dict(mal_dispatcher._DISPATCH, {"jikan": mock_jikan}):
            result = mal_dispatcher.fetch_mal_anime_data("Naruto")

        mock_jikan.assert_called_once_with("Naruto")
        assert result == {"synopsis": "x"}

    def test_dispatches_to_official_api(self):
        mock_official = MagicMock(return_value={"synopsis": "y"})
        with patch.dict(mal_dispatcher._DISPATCH, {"official_api": mock_official}):
            result = mal_dispatcher.fetch_mal_anime_data(
                "Naruto", method="official_api"
            )

        mock_official.assert_called_once_with("Naruto")
        assert result == {"synopsis": "y"}

    def test_dispatches_to_scrape(self):
        mock_scrape = MagicMock(return_value={"synopsis": "z"})
        with patch.dict(mal_dispatcher._DISPATCH, {"scrape": mock_scrape}):
            result = mal_dispatcher.fetch_mal_anime_data("Naruto", method="scrape")

        mock_scrape.assert_called_once_with("Naruto")
        assert result == {"synopsis": "z"}

    def test_unrecognized_method_falls_back_to_jikan(self):
        mock_jikan = MagicMock(return_value={"synopsis": "x"})
        with patch.dict(mal_dispatcher._DISPATCH, {"jikan": mock_jikan}):
            result = mal_dispatcher.fetch_mal_anime_data(
                "Naruto", method="carrier_pigeon"
            )

        mock_jikan.assert_called_once_with("Naruto")
        assert result == {"synopsis": "x"}

    def test_mal_fetch_methods_keys_match_dispatch_table(self):
        keys = {key for key, _label in mal_dispatcher.MAL_FETCH_METHODS}
        assert keys == set(mal_dispatcher._DISPATCH.keys())
