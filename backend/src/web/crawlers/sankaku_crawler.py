from backend.src.web.crawlers.image_board_crawler import ImageBoardCrawler


class SankakuCrawler(ImageBoardCrawler):
    """Crawler implementation for Sankaku Complex (C++-accelerated)."""

    def __init__(self, config: dict):
        if not config.get("url"):
            config["url"] = "https://capi-v2.sankakucomplex.com"
        # The C++ side handles the login_url and authentication logic
        super().__init__(config)

    def normalize_rating_tag(self, rating: str) -> str | None:
        """Sankaku rating tag normalization."""
        if not rating:
            return None
        r = rating.strip().lower()
        if r in ("safe", "general", "g"):
            return "rating:safe"
        if r in ("questionable", "q"):
            return "rating:questionable"
        if r in ("explicit", "e"):
            return "rating:explicit"
        return f"rating:{r}"

