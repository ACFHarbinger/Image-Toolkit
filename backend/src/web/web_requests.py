import os
import time
import requests

from PySide6.QtCore import QObject, Signal


class WebRequestsLogic(QObject):
    """
    Performs a sequence of web requests using the 'requests' library
    and emits Qt signals for status updates.
    """

    # === SIGNALS ===
    on_status = Signal(str)
    on_error = Signal(str)
    on_finished = Signal(str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.base_url = config.get("base_url")
        self.request_list = config.get("requests", [])
        self.action_list = config.get("actions", [])
        self._is_running = True  # Flag to control cancellation

    def stop(self):
        """Sets the flag to stop the execution loop."""
        self._is_running = False
        self.on_status.emit("Cancellation pending...")

    def _parse_post_data(self, param_str: str) -> dict:
        """Converts 'key:val, k2:v2' into a dictionary."""
        if not param_str:
            return {}

        data_dict = {}
        try:
            pairs = param_str.split(",")
            for pair in pairs:
                if ":" in pair:
                    key, value = pair.split(":", 1)
                    data_dict[key.strip()] = value.strip()
                else:
                    self.on_error.emit(f"Invalid POST data format: '{pair}'. Skipping.")
            return data_dict
        except Exception as e:
            self.on_error.emit(f"Error parsing POST data: {e}")
            return {}

    def _run_actions(self, response: requests.Response):
        """Runs the defined action list on the given response."""

        for action in self.action_list:
            if not self._is_running:
                return  # Stop processing actions if cancelled

            action_type = action.get("type")
            param = action.get("param")

            try:
                if action_type == "Print Response URL":
                    self.on_status.emit(f"  > Action: Response URL: {response.url}")

                elif action_type == "Print Response Status Code":
                    self.on_status.emit(
                        f"  > Action: Status Code: {response.status_code}"
                    )

                elif action_type == "Print Response Headers":
                    headers_str = "\n".join(
                        f"    {k}: {v}" for k, v in response.headers.items()
                    )
                    self.on_status.emit(
                        f"  > Action: Response Headers:\n {headers_str}"
                    )

                elif action_type == "Print Response Content (Text)":
                    # Truncate to avoid flooding the log
                    content_preview = response.text.strip()
                    self.on_status.emit(
                        f"  > Action: Response Content:\n {content_preview}"
                    )

                elif action_type == "Save Response Content (Binary)":
                    if not param:
                        self.on_error.emit(
                            "  > Action: Save failed. No file path provided in parameter."
                        )
                        continue

                    # Check if param is a directory
                    if os.path.isdir(param):
                        # Try to get a filename from the URL
                        try:
                            filename = os.path.basename(response.url.split("?")[0])
                            if not filename:
                                filename = f"response_{int(time.time())}.dat"
                        except Exception:
                            filename = f"response_{int(time.time())}.dat"
                        filepath = os.path.join(param, filename)
                    else:
                        filepath = param

                    try:
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        with open(filepath, "wb") as f:
                            f.write(response.content)
                        self.on_status.emit(
                            f"  > Action: Response content saved to {filepath}"
                        )
                    except Exception as e:
                        self.on_error.emit(
                            f"  > Action: Failed to save file to {filepath}: {e}"
                        )

            except Exception as e:
                self.on_error.emit(
                    f"  > Action: Failed to execute '{action_type}': {e}"
                )

    def run(self):
        """
        Main execution loop.
        Iterates through the request list and performs actions.
        """
        self.on_status.emit(f"Starting request sequence for {self.base_url}")

        for i, req in enumerate(self.request_list):
            if not self._is_running:
                self.on_status.emit("Request sequence cancelled.")
                self.on_finished.emit("Cancelled.")
                return

            req_type = req.get("type", "GET")
            param = req.get("param")

            url_to_request = self.base_url

            self.on_status.emit(
                f"--- Request {i+1}/{len(self.request_list)}: [{req_type}] ---"
            )

            try:
                response = None
                if req_type == "GET":
                    if param:  # Use param as URL suffix
                        url_to_request = os.path.join(self.base_url, param).replace(
                            "\\", "/"
                        )
                    self.on_status.emit(f"Executing GET: {url_to_request}")
                    response = requests.get(
                        url_to_request, timeout=10, allow_redirects=True
                    )

                elif req_type == "POST":
                    post_data = self._parse_post_data(param)
                    self.on_status.emit(
                        f"Executing POST: {url_to_request} with data: {post_data}"
                    )
                    response = requests.post(
                        url_to_request, data=post_data, timeout=10, allow_redirects=True
                    )

                if response is not None:
                    self.on_status.emit(
                        f"Request complete. Status: {response.status_code}"
                    )
                    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

                    # Run all defined actions on this response
                    self._run_actions(response)

            except requests.exceptions.HTTPError as he:
                self.on_error.emit(
                    f"Request failed: HTTP {he.response.status_code} {he.response.reason}"
                )
            except requests.exceptions.ConnectionError as ce:
                self.on_error.emit(f"Request failed: Connection Error: {ce}")
            except requests.exceptions.Timeout as te:
                self.on_error.emit(f"Request failed: Timeout: {te}")
            except Exception as e:
                self.on_error.emit(f"Request failed: An unexpected error occurred: {e}")

            time.sleep(0.5)  # Small delay between requests

        if self._is_running:
            self.on_status.emit("--- All requests finished. ---")
            self.on_finished.emit("All requests finished.")
