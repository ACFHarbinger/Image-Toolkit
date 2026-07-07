"""Offline parser tests for the reverse-search engine strategies.

Network calls are never made — each strategy exposes a static ``_parse_*``
method that turns a captured API/HTML payload into normalized results.
"""

from backend.src.web.search_engines.bing_visual_strategy import BingVisualSearchStrategy
from backend.src.web.search_engines.iqdb_strategy import IqdbStrategy
from backend.src.web.search_engines.saucenao_strategy import SauceNaoStrategy
from backend.src.web.search_engines.yandex_strategy import YandexSearchStrategy


class TestSauceNao:
    def test_parses_and_filters(self):
        payload = {"results": [
            {"header": {"similarity": "92.5", "index_name": "Danbooru"},
             "data": {"ext_urls": ["https://danbooru.donmai.us/posts/1"], "title": "art"}},
            {"header": {"similarity": "40.0"},
             "data": {"ext_urls": ["https://x.com/2"]}},
        ]}
        results = SauceNaoStrategy._parse_response(payload, min_similarity=60.0)
        assert len(results) == 1
        assert results[0].url == "https://danbooru.donmai.us/posts/1"
        assert results[0].score == 0.925
        assert results[0].engine == "saucenao"

    def test_empty_payload(self):
        assert SauceNaoStrategy._parse_response({}, 60.0) == []

    def test_multiple_ext_urls_expand(self):
        payload = {"results": [
            {"header": {"similarity": "88"},
             "data": {"ext_urls": ["https://a.com/1", "https://b.com/1"]}},
        ]}
        results = SauceNaoStrategy._parse_response(payload, 60.0)
        assert {r.url for r in results} == {"https://a.com/1", "https://b.com/1"}


class TestIqdb:
    def test_parses_similarity_and_resolution(self):
        html = (
            '<table><tr><td><a href="#">local</a></td></tr>'
            '<tr><td>Best match</td></tr>'
            '<tr><td><a href="//danbooru.donmai.us/posts/9">t</a></td></tr>'
            '<tr><td>1920×1080 [Safe]</td></tr>'
            '<tr><td>95% similarity</td></tr></table>'
        )
        results = IqdbStrategy._parse_response(html, min_similarity=60.0)
        assert len(results) == 1
        assert results[0].url == "https://danbooru.donmai.us/posts/9"
        assert results[0].resolution == "1920x1080"
        assert results[0].score == 0.95

    def test_below_threshold_dropped(self):
        html = ('<table><tr><td><a href="//x.com/1">t</a></td></tr>'
                '<tr><td>30% similarity</td></tr></table>')
        assert IqdbStrategy._parse_response(html, min_similarity=60.0) == []


class TestBing:
    def test_api_response(self):
        payload = {"tags": [{"actions": [
            {"actionType": "PagesIncluding", "data": {"value": [
                {"hostPageUrl": "https://reddit.com/r/x/1", "width": 800,
                 "height": 600, "name": "post"}]}}]}]}
        results = BingVisualSearchStrategy._parse_api_response(payload)
        assert results[0].url == "https://reddit.com/r/x/1"
        assert results[0].resolution == "800x600"

    def test_api_dedups(self):
        payload = {"tags": [{"actions": [
            {"actionType": "VisualSearch", "data": {"value": [
                {"hostPageUrl": "https://a.com/1"},
                {"hostPageUrl": "https://a.com/1"}]}}]}]}
        assert len(BingVisualSearchStrategy._parse_api_response(payload)) == 1

    def test_scrape_response(self):
        html = ('<a class="iusc" m=\'{"purl":"https://site.com/p",'
                '"murl":"https://site.com/i.jpg","t":"Title",'
                '"width":1024,"height":768}\'>x</a>')
        results = BingVisualSearchStrategy._parse_scrape_response(html)
        assert results[0].url == "https://site.com/p"
        assert results[0].title == "Title"
        assert results[0].resolution == "1024x768"


class TestYandex:
    def test_parse_upload(self):
        cbir_id, url = YandexSearchStrategy._parse_upload(
            {"cbir_id": "abc123", "sizes": {"preview": {"path": "//av.yandex/x"}}})
        assert cbir_id == "abc123"
        assert url == "https://av.yandex/x"

    def test_parse_results_from_data_state(self):
        html = ('<div class="CbirSites" data-state=\'{"sites":[{'
                '"url":"https://reddit.com/a","title":"T",'
                '"originalImage":{"width":500,"height":400}}]}\'></div>')
        results = YandexSearchStrategy._parse_results(html)
        assert results[0].url == "https://reddit.com/a"
        assert results[0].resolution == "500x400"

    def test_parse_results_anchor_fallback(self):
        html = '<a class="CbirSites-ItemTitle" href="https://x.com/p">Page</a>'
        results = YandexSearchStrategy._parse_results(html)
        assert results[0].url == "https://x.com/p"
