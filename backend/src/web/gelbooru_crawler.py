from .image_board_crawler import ImageBoardCrawler


class GelbooruCrawler(ImageBoardCrawler):
    """Crawler implementation for Gelbooru (Rust-accelerated)."""

    def __init__(self, config: dict):
        if not config.get("url"):
            config["url"] = "https://gelbooru.com"
        if config.get("limit") is None:
            config["limit"] = 100
        super().__init__(config)
