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

    def normalize_rating_tag(self, rating: str) -> str | None:
        """Safebooru is exclusively SFW/general; rating filters are a no-op."""
        return None

