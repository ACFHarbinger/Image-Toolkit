from .image_board_crawler import ImageBoardCrawler

class SankakuCrawler(ImageBoardCrawler):
    """Crawler implementation for Sankaku Complex (Rust-accelerated)."""

    def __init__(self, config: dict):
        if not config.get("url"):
            config["url"] = "https://capi-v2.sankakucomplex.com"
        # The Rust side handles the login_url and authentication logic
        super().__init__(config)
