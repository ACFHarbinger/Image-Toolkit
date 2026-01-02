from .image_board_crawler import ImageBoardCrawler

class DanbooruCrawler(ImageBoardCrawler):
    """Crawler implementation for Danbooru (Rust-accelerated)."""

    def __init__(self, config: dict):
        if not config.get("url"):
            config["url"] = "https://danbooru.donmai.us"
        super().__init__(config)
