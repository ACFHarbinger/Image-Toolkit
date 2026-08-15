from backend.src.web.crawlers.gelbooru_crawler import GelbooruCrawler


class SafebooruCrawler(GelbooruCrawler):
    """Crawler implementation for Safebooru (Gelbooru API-compatible, Issue #370)."""

    def __init__(self, config: dict):
        if not config.get("url"):
            config["url"] = "https://safebooru.org"
        super().__init__(config)

    def get_crawler_backend_name(self) -> str:
        """Safebooru uses the Gelbooru DAPI schema."""
        return "gelbooru"
