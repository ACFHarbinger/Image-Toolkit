from unittest.mock import MagicMock, patch

from backend.src.web.clients import mal_scrape_client

# Minimal fragments mirroring real myanimelist.net markup (verified live
# against https://myanimelist.net/anime.php?q=Naruto and
# https://myanimelist.net/anime/20/Naruto as of 2026-07-12).

SEARCH_HTML = """
<html><body>
<table>
<tr><td>
  <a href="https://myanimelist.net/anime/1735/Naruto__Shippuuden">Naruto: Shippuuden</a>
</td></tr>
<tr><td>
  <a href="https://myanimelist.net/anime/1735/Naruto__Shippuuden/video">Video</a>
</td></tr>
<tr><td>
  <a href="https://myanimelist.net/anime/20/Naruto">Naruto</a>
</td></tr>
</table>
</body></html>
"""

SEARCH_HTML_NO_RESULTS = "<html><body><table><tr><td>No results</td></tr></table></body></html>"

DETAIL_HTML = """
<html><body>
<span itemprop="ratingValue" class="score-label score-8">8.02</span>
<p itemprop="description">Twelve years ago, a colossal demon fox terrorized the world.</p>
<span itemprop="genre">Action</span>
<span itemprop="genre">Adventure</span>
<div class="spaceit_pad">Episodes: 220</div>
<div class="spaceit_pad">Status: Finished Airing</div>
<div class="spaceit_pad">Aired: Oct 3, 2002 to Feb 8, 2007</div>
<div class="spaceit_pad">Producers: TV Tokyo, Aniplex</div>
<div class="spaceit_pad">Studios: Studio Pierrot</div>
</body></html>
"""

CHARACTERS_HTML = """
<html><body>
<table class="js-anime-character-table">
  <tr>
    <td><a href="https://myanimelist.net/character/145/Sakura_Haruno"><img alt="x"/></a></td>
    <td>
      <a href="https://myanimelist.net/character/145/Sakura_Haruno">
        <h3 class="h3_character_name">Haruno, Sakura</h3>
      </a>
      <table class="js-anime-character-va">
        <tr class="js-anime-character-va-lang">
          <td>
            <a href="https://myanimelist.net/people/300/Chie_Nakamura">Nakamura, Chie</a>
            <div class="js-anime-character-language">Japanese</div>
          </td>
        </tr>
        <tr class="js-anime-character-va-lang">
          <td>
            <a href="https://myanimelist.net/people/318/Kate_Higgins">Higgins, Kate</a>
            <div class="js-anime-character-language">English</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
<h2>Staff</h2>
<table>
  <tr>
    <td><a href="https://myanimelist.net/people/78886/Ken_Hagino"><img alt="x"/></a></td>
    <td>
      <a href="https://myanimelist.net/people/78886/Ken_Hagino">Hagino, Ken</a>
      <div class="spaceit_pad"><small>Producer</small></div>
    </td>
  </tr>
</table>
<table>
  <tr>
    <td><a href="https://myanimelist.net/people/1/Someone_Else"><img alt="x"/></a></td>
    <td>
      <a href="https://myanimelist.net/people/1/Someone_Else">Else, Someone</a>
      <div class="spaceit_pad"><small>Director, Storyboard</small></div>
    </td>
  </tr>
</table>
</body></html>
"""


class TestFindFirstResult:
    def test_finds_first_unique_anime_id(self):
        match = mal_scrape_client._find_first_result(SEARCH_HTML)
        assert match == ("1735", "Naruto__Shippuuden")

    def test_returns_none_for_no_results(self):
        assert mal_scrape_client._find_first_result(SEARCH_HTML_NO_RESULTS) is None


class TestParseDetailPage:
    def test_parses_all_fields(self):
        data = mal_scrape_client._parse_detail_page(DETAIL_HTML, "20")

        assert data["score"] == 8.02
        assert "colossal demon fox" in data["synopsis"]
        assert data["genres"] == "Action, Adventure"
        assert data["episodes"] == 220
        assert data["status"] == "Completed"
        assert data["year"] == 2002
        assert data["producers"] == ["TV Tokyo", "Aniplex"]
        assert data["studios"] == ["Studio Pierrot"]
        assert data["mal_url"] == "https://myanimelist.net/anime/20"


class TestParseCharactersPage:
    def test_parses_characters_japanese_va_only_and_staff(self):
        characters, voice_actors, staff = mal_scrape_client._parse_characters_page(
            CHARACTERS_HTML
        )

        assert characters == ["Sakura Haruno"]
        assert voice_actors == ["Chie Nakamura"]  # English VA filtered out
        assert staff == [
            {"name": "Ken Hagino", "positions": ["Producer"]},
            {"name": "Someone Else", "positions": ["Director", "Storyboard"]},
        ]


class TestFetchMalAnimeData:
    @patch("backend.src.web.clients.mal_scrape_client.make_session")
    @patch("time.sleep", MagicMock())
    def test_end_to_end_success(self, mock_make_session):
        session = MagicMock()
        search_resp = MagicMock(ok=True, text=SEARCH_HTML)
        search_resp.raise_for_status = MagicMock()
        detail_resp = MagicMock(ok=True, text=DETAIL_HTML)
        detail_resp.raise_for_status = MagicMock()
        char_resp = MagicMock(ok=True, text=CHARACTERS_HTML)
        session.get.side_effect = [search_resp, detail_resp, char_resp]
        mock_make_session.return_value = session

        result = mal_scrape_client.fetch_mal_anime_data("Naruto")

        assert "error" not in result
        assert result["score"] == 8.02
        assert result["characters"] == ["Sakura Haruno"]
        assert result["voice_actors"] == ["Chie Nakamura"]
        assert result["characters_available"] is True
        session.close.assert_called_once()

    @patch("backend.src.web.clients.mal_scrape_client.make_session")
    def test_no_results_returns_error(self, mock_make_session):
        session = MagicMock()
        search_resp = MagicMock(ok=True, text=SEARCH_HTML_NO_RESULTS)
        search_resp.raise_for_status = MagicMock()
        session.get.return_value = search_resp
        mock_make_session.return_value = session

        result = mal_scrape_client.fetch_mal_anime_data("Nonexistent Title")

        assert "error" in result
        assert "No results found" in result["error"]

    @patch("backend.src.web.clients.mal_scrape_client.make_session")
    @patch("time.sleep", MagicMock())
    def test_characters_page_failure_is_best_effort_not_fatal(self, mock_make_session):
        session = MagicMock()
        search_resp = MagicMock(ok=True, text=SEARCH_HTML)
        search_resp.raise_for_status = MagicMock()
        detail_resp = MagicMock(ok=True, text=DETAIL_HTML)
        detail_resp.raise_for_status = MagicMock()
        char_resp = MagicMock(ok=False)
        session.get.side_effect = [search_resp, detail_resp, char_resp]
        mock_make_session.return_value = session

        result = mal_scrape_client.fetch_mal_anime_data("Naruto")

        assert "error" not in result
        assert result["characters_available"] is False
        assert result["characters"] == []
