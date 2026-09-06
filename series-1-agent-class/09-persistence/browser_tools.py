"""Expose one persistent Playwright page as four model-callable tools."""

import atexit
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Browser as PlaywrightBrowser
from playwright.sync_api import Page, Playwright, sync_playwright

import workspace

MAX_PAGE_TEXT = 4_000

TOOLS = [
    {
        "type": "function",
        "name": "open_page",
        "description": "Open an http/https URL or an HTML file from the agent workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "An http/https URL or a relative workspace HTML path.",
                }
            },
            "required": ["target"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "read_page",
        "description": "Read the current rendered page and its interactive elements.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "click",
        "description": "Click exactly one element on the current page using a CSS selector.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "A CSS selector for exactly one element.",
                }
            },
            "required": ["selector"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "type_text",
        "description": "Fill one text field and optionally press Enter.",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "A CSS selector for one input or textarea.",
                },
                "text": {
                    "type": "string",
                    "description": "The text that replaces the field's current value.",
                },
                "press_enter": {
                    "type": "boolean",
                    "description": "Whether to press Enter after filling the field.",
                },
            },
            "required": ["selector", "text", "press_enter"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


# Playwright's sync API allows one driver per thread, so the driver is a
# process-level resource. Each Browser below launches its own Chromium from
# it: the window and the page are per instance, the driver is not.
_driver: Playwright | None = None


def _playwright() -> Playwright:
    """Start the Playwright driver on first use. It stops when the process exits."""
    global _driver
    if _driver is None:
        _driver = sync_playwright().start()
        atexit.register(_driver.stop)
    return _driver


def _page_state(page: Page) -> str:
    """Describe the current rendered page as concise JSON."""
    text = page.locator("body").inner_text().strip()
    if len(text) > MAX_PAGE_TEXT:
        text = text[:MAX_PAGE_TEXT] + "\n…"

    elements = page.locator(
        "a, button, input, select, textarea, [role]"
    ).evaluate_all(
        """elements => elements
            .filter(element => {
                const style = getComputedStyle(element);
                return style.visibility !== "hidden"
                    && style.display !== "none"
                    && element.getClientRects().length > 0;
            })
            .map(element => ({
                tag: element.tagName.toLowerCase(),
                ...(element.id ? {id: element.id} : {}),
                ...(element.getAttribute("name")
                    ? {name: element.getAttribute("name")}
                    : {}),
                ...(element.getAttribute("type")
                    ? {type: element.getAttribute("type")}
                    : {}),
                ...(element.getAttribute("role")
                    ? {role: element.getAttribute("role")}
                    : {}),
                ...(element.getAttribute("placeholder")
                    ? {placeholder: element.getAttribute("placeholder")}
                    : {}),
                ...(element.getAttribute("aria-label")
                    ? {aria_label: element.getAttribute("aria-label")}
                    : {}),
                ...(element.getAttribute("href")
                    ? {href: element.getAttribute("href")}
                    : {}),
                visible_text: (element.innerText || element.value || "").trim(),
            }))"""
    )
    return json.dumps(
        {
            "url": page.url,
            "title": page.title(),
            "text": text,
            "interactive_elements": elements,
        }
    )


class Browser:
    """One Chromium window with one page, launched on first use and kept until close().

    Each Browser launches its own Chromium. Two agents in one process get two
    windows, not one shared page.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._browser: PlaywrightBrowser | None = None
        self._page: Page | None = None

    def _current_page(self) -> Page:
        """Launch Chromium lazily and return this browser's page."""
        if self._page is None:
            self._browser = _playwright().chromium.launch(headless=self.headless)
            self._page = self._browser.new_page()
        return self._page

    def open_page(self, target: str) -> str:
        """Navigate the page to a web URL or confined local file."""
        parsed = urlparse(target)
        if parsed.scheme in {"http", "https"}:
            if not parsed.netloc:
                raise ValueError("http and https URLs must include a host")
            url = target
        elif parsed.scheme or parsed.netloc:
            raise ValueError("only http, https, and relative workspace paths are allowed")
        else:
            if Path(target).is_absolute():
                raise ValueError("local HTML paths must be relative to the agent workspace")
            path = workspace.resolve_path(target)
            if not path.is_file():
                raise FileNotFoundError(f"not a file: {target}")
            url = path.as_uri()

        page = self._current_page()
        page.goto(url, wait_until="domcontentloaded")
        return _page_state(page)

    def read_page(self) -> str:
        """Return the current page state."""
        return _page_state(self._current_page())

    def type_text(self, selector: str, text: str, press_enter: bool) -> str:
        """Fill one text field, optionally submit it, and return the new page state."""
        page = self._current_page()
        matches = page.locator(selector)
        count = matches.count()
        if count != 1:
            raise ValueError(f"selector must match exactly one element; matched {count}: {selector}")
        matches.fill(text)
        if press_enter:
            matches.press("Enter")
            page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(100)
        return _page_state(page)

    def click(self, selector: str) -> str:
        """Click one CSS match and return the updated page state."""
        page = self._current_page()
        matches = page.locator(selector)
        count = matches.count()
        if count != 1:
            raise ValueError(f"selector must match exactly one element; matched {count}: {selector}")
        matches.click()
        page.wait_for_timeout(100)
        return _page_state(page)

    def close(self) -> None:
        """Close this browser's Chromium if it was launched."""
        if self._browser is not None:
            self._browser.close()
        self._page = None
        self._browser = None
