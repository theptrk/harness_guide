"""Expose one persistent Playwright page as four model-callable tools."""


import atexit
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from . import workspace

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

_playwright: Playwright | None = None
_browser: Browser | None = None
_page: Page | None = None


def _headless() -> bool:
    return os.getenv("AGENT_HEADLESS", "").lower() in {"1", "true", "yes"}


def _current_page() -> Page:
    """Start Chromium lazily and return the shared page."""
    global _playwright, _browser, _page
    if _page is None:
        _playwright = sync_playwright().start()
        try:
            _browser = _playwright.chromium.launch(headless=_headless())
            _page = _browser.new_page()
        except Exception:
            _playwright.stop()
            _playwright = None
            raise
    return _page


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


def open_page(target: str) -> str:
    """Navigate the shared page to a web URL or confined local file."""
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

    page = _current_page()
    page.goto(url, wait_until="domcontentloaded")
    return _page_state(page)


def read_page() -> str:
    """Return the current shared page state."""
    return _page_state(_current_page())


def type_text(selector: str, text: str, press_enter: bool) -> str:
    """Fill one text field, optionally submit it, and return the new page state."""
    page = _current_page()
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


def click(selector: str) -> str:
    """Click one CSS match and return the updated shared page state."""
    page = _current_page()
    matches = page.locator(selector)
    count = matches.count()
    if count != 1:
        raise ValueError(f"selector must match exactly one element; matched {count}: {selector}")
    matches.click()
    page.wait_for_timeout(100)
    return _page_state(page)


def close_browser() -> None:
    """Close Playwright resources if the browser was started."""
    global _playwright, _browser, _page
    if _browser is not None:
        _browser.close()
    if _playwright is not None:
        _playwright.stop()
    _page = None
    _browser = None
    _playwright = None


atexit.register(close_browser)
