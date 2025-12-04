import requests

from .image_board_crawler import ImageBoardCrawler


class SankakuCrawler(ImageBoardCrawler):
    """Crawler implementation for Sankaku Complex API (V2)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = "https://capi-v2.sankakucomplex.com"
        self.login_url = "https://login.sankakucomplex.com/auth/token"

        # Sankaku requires specific headers to mimic a browser/app
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.85 YaBrowser/21.11.0.1996 Yowser/2.5 Safari/537.36",
                "Content-Type": "application/json; charset=utf-8",
                "x-requested-with": "com.android.browser",
                "Accept-Encoding": "gzip, deflate, br",
                # Host header is set dynamically or by requests, but API expects capi-v2 for data
                "Host": "capi-v2.sankakucomplex.com",
            }
        )

        # Check if we have credentials to log in
        if self.username and self.api_key:
            self.authenticate()

    def authenticate(self):
        """Performs authentication to retrieve an access token."""
        try:
            self.on_status.emit("Authenticating with Sankaku Complex...")

            # Payload for login
            payload = {
                "login": self.username,
                "password": self.api_key,  # Using api_key field for password storage
            }

            # Prepare headers for login (different Host)
            login_headers = self.session.headers.copy()
            login_headers["Host"] = "login.sankakucomplex.com"

            response = requests.post(
                self.login_url, json=payload, headers=login_headers, timeout=15
            )
            response.raise_for_status()
            data = response.json()

            if "access_token" in data and "token_type" in data:
                token = data["access_token"]
                token_type = data["token_type"]

                # Update session headers with the token for subsequent requests
                self.session.headers.update({"Authorization": f"{token_type} {token}"})
                self.on_status.emit("Authentication successful.")
            else:
                self.on_status.emit(
                    "Authentication failed: Access token not found in response."
                )

        except Exception as e:
            self.on_status.emit(f"Authentication Error: {e}")

    def fetch_posts(self, page):
        """Fetches posts from Sankaku V2 API."""
        endpoint = f"{self.base_url}/posts"

        # Base parameters
        params = {"lang": "en", "page": page, "limit": self.limit, "tags": self.tags}

        # Add user-defined extra parameters (e.g., order=popularity)
        if hasattr(self, "extra_params") and self.extra_params:
            params.update(self.extra_params)

        try:
            self.check_rate_limit()
            self.on_status.emit(f"Requesting: {endpoint} (Page {page})")

            # Note: The session headers already contain the Authorization token if logged in
            response = self.session.get(endpoint, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()

            # V2 API typically returns a list of posts or a dict with a "data" key
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "data" in data:
                return data["data"]

            return []

        except Exception as e:
            self.on_status.emit(f"Sankaku Request Failed: {e}")
            return []

    def extract_file_url(self, post):
        """Extracts the best available image URL from the post object."""
        # Try file_url first (original)
        url = post.get("file_url")

        # Fallback to sample_url if file_url is missing (common for non-premium on large files)
        if not url:
            url = post.get("sample_url")

        # Fallback to preview_url as a last resort
        if not url:
            url = post.get("preview_url")

        return url
