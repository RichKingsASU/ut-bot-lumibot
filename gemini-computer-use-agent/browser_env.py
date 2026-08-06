"""Playwright browser environment manager and action executor for Computer Use API."""

import time
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from config import AgentConfig


def denormalize_x(x: int, screen_width: int) -> int:
    """Convert normalized model coordinate (0-1000) to actual screen pixel X coordinate."""
    return int((x / 1000.0) * screen_width)


def denormalize_y(y: int, screen_height: int) -> int:
    """Convert normalized model coordinate (0-1000) to actual screen pixel Y coordinate."""
    return int((y / 1000.0) * screen_height)


def is_url_permitted(url: str, allowed_domains: List[str], blocked_domains: List[str]) -> Tuple[bool, str]:
    """Validates whether a target URL is permitted according to domain allowlist/blocklist configuration."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain and parsed.path:
            domain = parsed.path.split("/")[0].lower()
    except Exception:
        return False, f"Invalid URL format: {url}"

    # Check blocklist first
    if blocked_domains:
        for b_domain in blocked_domains:
            if b_domain.lower() in domain:
                return False, f"Domain '{domain}' is blocked by security policy."

    # Check allowlist if configured
    if allowed_domains:
        allowed = any(a_domain.lower() in domain for a_domain in allowed_domains)
        if not allowed:
            return False, f"Domain '{domain}' is not in the allowed domains list: {allowed_domains}"

    return True, "Permitted"


class BrowserEnvironment:
    """Manages the sandboxed Playwright Chromium browser context and action execution."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.playwright: Any = None
        self.browser: Any = None
        self.context: Any = None
        self.page: Any = None

    def start(self) -> None:
        """Starts Playwright Chromium session with fixed viewport dimensions."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.config.headless)
        self.context = self.browser.new_context(
            viewport={
                "width": self.config.screen_width,
                "height": self.config.screen_height,
            },
            device_scale_factor=1.0,
        )
        self.page = self.context.new_page()

        if self.config.initial_url:
            permitted, reason = is_url_permitted(
                self.config.initial_url, self.config.allowed_domains, self.config.blocked_domains
            )
            if permitted:
                self.page.goto(self.config.initial_url, wait_until="domcontentloaded")

    def stop(self) -> None:
        """Closes Playwright browser session."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def capture_screenshot(self) -> bytes:
        """Captures screenshot bytes of the current webpage."""
        return self.page.screenshot(type="png")

    def get_current_url(self) -> str:
        """Returns the current page URL."""
        return self.page.url

    def execute_action(self, fname: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a Computer Use UI action on the active Playwright page."""
        width = self.config.screen_width
        height = self.config.screen_height

        if fname == "open_web_browser":
            return {"status": "success", "info": "Browser is already open."}

        elif fname == "search":
            search_url = "https://www.google.com"
            permitted, reason = is_url_permitted(search_url, self.config.allowed_domains, self.config.blocked_domains)
            if not permitted:
                return {"error": reason}
            self.page.goto(search_url, wait_until="domcontentloaded")
            return {"status": "success", "url": search_url}

        elif fname == "navigate":
            target_url = args.get("url", "")
            if not target_url:
                return {"error": "Missing 'url' argument for navigate action."}
            if not target_url.startswith("http://") and not target_url.startswith("https://"):
                target_url = "https://" + target_url

            permitted, reason = is_url_permitted(target_url, self.config.allowed_domains, self.config.blocked_domains)
            if not permitted:
                return {"error": reason}

            self.page.goto(target_url, wait_until="domcontentloaded")
            return {"status": "success", "url": self.page.url}

        elif fname == "go_back":
            self.page.go_back()
            return {"status": "success", "url": self.page.url}

        elif fname == "go_forward":
            self.page.go_forward()
            return {"status": "success", "url": self.page.url}

        elif fname == "click_at":
            actual_x = denormalize_x(args["x"], width)
            actual_y = denormalize_y(args["y"], height)
            self.page.mouse.click(actual_x, actual_y)
            self._wait_for_idle()
            return {"status": "success", "clicked_at": {"x": actual_x, "y": actual_y}}

        elif fname == "hover_at":
            actual_x = denormalize_x(args["x"], width)
            actual_y = denormalize_y(args["y"], height)
            self.page.mouse.move(actual_x, actual_y)
            return {"status": "success", "hovered_at": {"x": actual_x, "y": actual_y}}

        elif fname == "type_text_at":
            actual_x = denormalize_x(args["x"], width)
            actual_y = denormalize_y(args["y"], height)
            text = args.get("text", "")
            press_enter = args.get("press_enter", True)
            clear_before = args.get("clear_before_typing", True)

            self.page.mouse.click(actual_x, actual_y)
            if clear_before:
                # Clear text field (Ctrl+A / Cmd+A + Backspace)
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")

            self.page.keyboard.type(text)
            if press_enter:
                self.page.keyboard.press("Enter")

            self._wait_for_idle()
            return {"status": "success", "typed_text": text, "at": {"x": actual_x, "y": actual_y}}

        elif fname == "key_combination":
            keys = args.get("keys", "")
            self.page.keyboard.press(keys)
            self._wait_for_idle()
            return {"status": "success", "pressed_keys": keys}

        elif fname == "scroll_document":
            direction = args.get("direction", "down").lower()
            delta_y = 500 if direction == "down" else (-500 if direction == "up" else 0)
            delta_x = 500 if direction == "right" else (-500 if direction == "left" else 0)
            self.page.evaluate(f"window.scrollBy({delta_x}, {delta_y})")
            time.sleep(0.5)
            return {"status": "success", "direction": direction}

        elif fname == "scroll_at":
            actual_x = denormalize_x(args["x"], width)
            actual_y = denormalize_y(args["y"], height)
            direction = args.get("direction", "down").lower()
            magnitude = args.get("magnitude", 800)
            scaled_magnitude = int((magnitude / 1000.0) * height)

            delta_y = scaled_magnitude if direction == "down" else (-scaled_magnitude if direction == "up" else 0)
            delta_x = scaled_magnitude if direction == "right" else (-scaled_magnitude if direction == "left" else 0)

            self.page.mouse.move(actual_x, actual_y)
            self.page.mouse.wheel(delta_x, delta_y)
            time.sleep(0.5)
            return {"status": "success", "scroll_at": {"x": actual_x, "y": actual_y}, "direction": direction}

        elif fname == "drag_and_drop":
            src_x = denormalize_x(args["x"], width)
            src_y = denormalize_y(args["y"], height)
            dst_x = denormalize_x(args["destination_x"], width)
            dst_y = denormalize_y(args["destination_y"], height)

            self.page.mouse.move(src_x, src_y)
            self.page.mouse.down()
            self.page.mouse.move(dst_x, dst_y, steps=5)
            self.page.mouse.up()
            self._wait_for_idle()
            return {"status": "success", "from": {"x": src_x, "y": src_y}, "to": {"x": dst_x, "y": dst_y}}

        elif fname == "wait_5_seconds":
            time.sleep(5)
            return {"status": "success", "info": "Waited 5 seconds."}

        else:
            return {"error": f"Unknown or unsupported UI action: {fname}"}

    def _wait_for_idle(self) -> None:
        """Helper to wait briefly for network and rendering idle."""
        try:
            self.page.wait_for_load_state(timeout=3000)
        except Exception:
            pass
        time.sleep(0.5)
