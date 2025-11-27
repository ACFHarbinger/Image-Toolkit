from urllib.parse import urljoin
from .image_board_crawler import ImageBoardCrawler


class DanbooruCrawler(ImageBoardCrawler):
    """Crawler implementation for Danbooru API."""
    
    def __init__(self, config: dict):
        super().__init__(config)
        if not self.base_url:
            self.base_url = "https://danbooru.donmai.us"

    def fetch_data(self, page):
        # Resource maps to endpoint: posts -> /posts.json, tags -> /tags.json
        endpoint = urljoin(self.base_url, f"/{self.resource}.json")
        
        params = {
            "page": page,
            "limit": self.limit,
        }
        
        # Danbooru uses 'search[...]' params.
        # 'tags' config usually maps to the primary search field for that resource.
        if self.tags:
            if self.resource == "posts":
                params["tags"] = self.tags # Alias for search[tag_string]
            elif self.resource == "tags":
                params["search[name_matches]"] = self.tags
            elif self.resource == "users":
                params["search[name_matches]"] = self.tags
            elif self.resource == "comments":
                # Comments search is complex, usually search[body_matches] or search[post_id]
                # We'll assume generic text search for now or let user use extra_params
                params["search[body_matches]"] = self.tags
            else:
                # Fallback: try to put it in a generic search param if possible, 
                # or rely on extra_params.
                pass 
            
        # Add user-defined extra parameters (e.g. search[order]=count)
        # This allows the user to fully control the 'search[...]=' params from the UI
        params.update(self.extra_params)
        
        # Danbooru Auth: login (username) + api_key
        if self.username and self.api_key:
            params["login"] = self.username
            params["api_key"] = self.api_key
            
        try:
            self.check_rate_limit()
            self.on_status.emit(f"Requesting: {endpoint}")
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.on_status.emit(f"Danbooru Request Failed: {e}")
            return []
