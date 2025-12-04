from urllib.parse import urljoin
from .image_board_crawler import ImageBoardCrawler


class GelbooruCrawler(ImageBoardCrawler):
    """Crawler implementation for Gelbooru API."""

    def __init__(self, config: dict):
        super().__init__(config)
        if not self.base_url:
            self.base_url = "https://gelbooru.com"
        if config.get("limit") is None:
            self.limit = 100

    def fetch_data(self, page):
        endpoint = urljoin(self.base_url, "/index.php")

        # Gelbooru Resource Mapping:
        # posts -> s=post
        # tags -> s=tag
        # comments -> s=comment
        # Convert plural (common input) to singular (Gelbooru requirement) if needed
        s_param = self.resource.rstrip("s")

        params = {
            "page": "dapi",
            "s": s_param,
            "q": "index",
            "json": 1,
            "limit": self.limit,
            "pid": page - 1,
        }

        if self.tags:
            # Different resources use different primary search keys in Gelbooru
            if s_param == "post":
                params["tags"] = self.tags
            elif s_param == "tag":
                params["name_pattern"] = f"%{self.tags}%"  # Wildcard search
            elif s_param == "user":
                params["name_pattern"] = f"%{self.tags}%"
            elif s_param == "comment":
                # Comments usually require post_id, no direct text search in standard dapi
                # We'll leave it to extra_params if needed
                pass

        # Add user-defined extra parameters (e.g., deleted=show, order=date)
        params.update(self.extra_params)

        # Gelbooru Auth
        if self.username and self.api_key:
            params["user_id"] = self.username
            params["api_key"] = self.api_key

        try:
            self.check_rate_limit()
            self.on_status.emit(f"Requesting: {endpoint}?s={s_param}&q=index")
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Key handling for Gelbooru's inconsistent JSON wrapper
            # It might be 'post', 'tag', 'comment', 'user', etc.
            # We try the exact resource name, then plural, then generic 'posts' fallback
            possible_keys = [
                s_param,
                self.resource,
                "post",
                "posts",
                "tag",
                "tags",
                "comment",
                "comments",
                "user",
                "users",
            ]

            items = []

            # Check if it's a direct list first (some versions/endpoints)
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                # Search inside keys
                for key in possible_keys:
                    if key in data:
                        val = data[key]
                        if isinstance(val, list):
                            items = val
                        elif isinstance(val, dict):
                            # Sometimes single items are returned as a dict, not list
                            items = [val]
                        break

            return items

        except Exception as e:
            self.on_status.emit(f"Gelbooru Request Failed: {e}")
            return []
