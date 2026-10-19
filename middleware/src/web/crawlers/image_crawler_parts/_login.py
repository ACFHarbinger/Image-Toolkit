"""Login (browser + HTTP), cookie sync, and verification-wait logic for ImageCrawler."""

import contextlib
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup


class _LoginMixin:
    """Login/authentication methods for ``ImageCrawler``."""

    def _perform_login(  # noqa: C901
        self, driver, login_url: str, username: str | None, password: str | None
    ) -> bool:
        """Attempt automated login via Selenium."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys

        self.on_status.publish(f"🔑 Navigating to login page: {login_url}")
        try:
            if not self._navigate_browser(driver, login_url):
                return False
            time.sleep(2.0)

            # Check if user is already authenticated
            page_src = driver.page_source.lower()
            if "logout" in page_src or "sign out" in page_src or "/user/index" in page_src:
                self.on_status.publish("ℹ️ Already authenticated session detected.")
                return True

            # Find user/email input
            user_el = None
            for sel in [
                "input[name='email']",
                "input[type='email']",
                "input[id='email']",
                "input[name='username']",
                "input[id='username']",
                "input[name='user']",
                "input[type='text']",
            ]:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    if el.is_displayed():
                        user_el = el
                        break
                if user_el:
                    break

            if user_el and username:
                user_el.clear()
                user_el.send_keys(username)

            # Find password input
            pass_el = None
            for sel in [
                "input[name='password']",
                "input[type='password']",
                "input[id='password']",
            ]:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elements:
                    if el.is_displayed():
                        pass_el = el
                        break
                if pass_el:
                    break

            if pass_el and password:
                pass_el.clear()
                pass_el.send_keys(password)

            # Check Remember Me if present
            with contextlib.suppress(Exception):
                remember_boxes = driver.find_elements(
                    By.CSS_SELECTOR,
                    "input[name='remember'], input[id='remember'], input[type='checkbox']",
                )
                for box in remember_boxes:
                    if not box.is_selected():
                        box.click()

            # Detect Captcha / Cloudflare Turnstile
            captcha_elements = driver.find_elements(
                By.CSS_SELECTOR,
                ".g-recaptcha, .cf-turnstile, div[class*='recaptcha'], div[class*='turnstile'], iframe[src*='turnstile'], iframe[src*='recaptcha']",
            )
            if captcha_elements:
                self.on_status.publish(
                    "⚠️ Captcha/Turnstile detected on login page. If login does not complete automatically, "
                    "launch your browser with --remote-debugging-port=9222 and log in manually first."
                )

            # Submit form
            submitted = False
            for btn_sel in [
                "button[type='submit']",
                "input[type='submit']",
                "form button",
                ".btn-primary",
            ]:
                btns = driver.find_elements(By.CSS_SELECTOR, btn_sel)
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        submitted = True
                        break
                if submitted:
                    break

            if not submitted and pass_el:
                pass_el.send_keys(Keys.RETURN)

            time.sleep(3.0)
            self.on_status.publish(
                f"🔑 Login form submitted. Current page: {driver.current_url}"
            )
            return True
        except Exception as e:
            self.on_status.publish(f"⚠️ Automated login encounter: {e}")
            return False

    def _perform_http_login(
        self,
        session: requests.Session,
        login_url: str,
        username: str | None,
        password: str | None,
        headers: dict,
    ) -> bool:
        """Best-effort HTTP form POST login fallback when WebDriver is unavailable."""
        try:
            resp = session.get(login_url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            form = soup.find("form")
            if not form:
                return False

            payload = {}
            for inp in form.find_all("input"):
                name = inp.get("name")
                val = inp.get("value", "")
                if name:
                    payload[name] = val

            for k in payload:
                lk = k.lower()
                if ("user" in lk or "email" in lk) and username:
                    payload[k] = username
                elif "pass" in lk and password:
                    payload[k] = password

            action = form.get("action")
            post_url = urllib.parse.urljoin(login_url, action) if action else login_url
            post_resp = session.post(post_url, data=payload, headers=headers, timeout=10)
            self.on_status.publish(
                f"🔑 HTTP login POST sent to {post_url} (Status: {post_resp.status_code})"
            )
            return post_resp.status_code in (200, 302)
        except Exception as e:
            self.on_status.publish(f"⚠️ HTTP login fallback failed: {e}")
            return False

    def _sync_cookies_to_session(self, driver, session: requests.Session) -> None:
        """Transfer browser cookies into requests session for authenticated media downloads."""
        try:
            cookies = driver.get_cookies()
            for c in cookies:
                session.cookies.set(
                    c["name"],
                    c["value"],
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                )
            if cookies:
                self.on_status.publish(
                    f"🍪 Synchronized {len(cookies)} browser cookie(s) to HTTP session."
                )
        except Exception as e:
            self.on_status.publish(f"⚠️ Cookie synchronization warning: {e}")

    def _navigate_browser(self, driver, url: str) -> bool:
        from selenium.common.exceptions import TimeoutException

        driver.set_page_load_timeout(30)
        try:
            driver.get(url)
        except TimeoutException:
            if not self._browser_has_challenge(driver):
                raise
            # Challenge resources can keep navigation pending before polling starts.
            self.on_status.publish("⚠️ Navigation is waiting on website security verification.")
        return self._wait_for_browser_access(driver)

    def _browser_has_challenge(self, driver) -> bool:
        from selenium.webdriver.common.by import By

        title = (driver.title or "").lower()
        if any(marker in title for marker in ("just a moment", "attention required")):
            return True
        try:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
        except Exception:
            return False
        return any(marker in body for marker in (
            "performing security verification",
            "this page is displayed while the website verifies you are not a bot",
            "verifying you are human",
        ))

    def _wait_for_browser_access(self, driver) -> bool:
        """Allow verification to finish without treating a challenge as a gallery.

        Challenge handling (Cloudflare / CAPTCHA):
        - Headless: fails immediately — cannot solve a visual challenge.
        - Non-headless: fires ``on_verification_required``, then blocks the
          crawler thread on ``_resume_event`` until the GUI calls
          :meth:`resume` (user pressed OK) or :meth:`stop` (cancel).

        Login-gate handling (site shows "log in to view more"):
        - Waits up to 120 s for the user to log in and the gallery to appear.
        """
        from selenium.webdriver.common.by import By

        headless = self.config.get("headless")
        # Deadline is only used for the login-pending path (user has 2 min).
        login_deadline = time.monotonic() + 120
        notified = False
        login_pending = False
        album_url = None
        restored_album = False
        while self._is_running:
            challenge = self._browser_has_challenge(driver)
            if not challenge and not login_pending:
                body = driver.find_element(By.TAG_NAME, "body").text
                if self._has_album_login_gate(body):
                    login_pending = True
                    album_url = driver.current_url
                    self.on_status.publish(
                        "🔑 This browser is not logged in: the site is showing only an album preview. "
                        "Log in in the connected browser window within two minutes. "
                        "Your normal Brave window uses a different profile."
                    )
            if not challenge and not login_pending:
                return True
            if login_pending and not challenge and driver.find_elements(By.CSS_SELECTOR, ".photos-list img"):
                if driver.current_url != album_url and not restored_album:
                    restored_album = True
                    driver.get(album_url)
                    continue
                return True
            if login_pending and time.monotonic() >= login_deadline:
                self._access_blocked = True
                self._login_blocked = True
                self.on_status.publish(
                    "⚠️ Login is still pending; stopping the crawl without trying subsequent pages."
                )
                return False
            if challenge and not notified:
                if headless:
                    # Headless sessions can never solve a visual challenge.
                    self.on_status.publish(
                        "⚠️ Browser verification required but running headless — disable Headless and retry."
                    )
                    self._access_blocked = True
                    return False
                # Non-headless: pause and ask the user to solve it, then press OK.
                msg = (
                    "⏸️ Human verification required. Complete the check in the browser window, "
                    "then press OK in the dialog to resume the crawl."
                )
                self.on_status.publish(msg)
                self._resume_event.clear()
                self.on_verification_required.publish(msg)
                # Block the crawler thread until resume() is called (or stop()).
                while self._is_running and not self._resume_event.is_set():
                    self._resume_event.wait(timeout=0.5)
                if not self._is_running:
                    return False
                self._resume_event.clear()
                notified = True  # suppress further pause prompts for same page
            time.sleep(0.5)
        return False

    @staticmethod
    def _has_album_login_gate(text: str) -> bool:
        return isinstance(text, str) and "you need to log in to view more content of this album" in " ".join(text.lower().split())

