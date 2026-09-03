# Level 7 — Use a browser

## What Level 7 adds

The Level 6 harness already provides enough raw access to automate a browser.
The model must recognize that route and plan the Playwright setup, script, and
command. Success therefore depends on the model and its reasoning budget.

Level 7 moves that work into the harness. You install Chromium once, and
`browser_tools.py` starts and preserves the browser page. The model only has to
choose among `open_page`, `read_page`, `type_text`, and `click`.

---

## Install Chromium once

Playwright is a Python dependency, but its browser binary is installed
separately. Run this once before using Level 7:

```sh
uv run playwright install chromium
```

---

## Run it

Level 7 asked the model to write `random-button.html` and click it through the
shell. Each level has its own workspace, so write the file again here and click
it with the browser tools.

Start a new Level 7 conversation:

```sh
uv run --env-file .env series-1-agent-class/07-browser/main.py
```

Enter this as one request:

```text
Write random-button.html in the workspace. The page has one button. Clicking
the button shows a random number. Then open that file with open_page, click
the button, and report the number.
```

`open_page` accepts a workspace-relative path and opens it as a `file://` URL.
The snapshot lists visible interactive elements. A button on that page looks
similar to:

```text
{"tag": "button", "text": "..."}
```

Those attributes let the model construct a CSS selector for the button, then
`click` it. `click` returns a snapshot of the page after the click, so the
random number is in that result.

A live Google search is a second exercise at the end of this lesson. It is not
the check for these tools. The local file does not depend on a network or a
CAPTCHA.

---

## The tools are wrappers around Playwright

`open_page`, `read_page`, `type_text`, and `click` are functions in
`browser_tools.py`. They are not Playwright function names. Each function calls
a smaller part of the Playwright API and returns a JSON string for
`function_call_output`.

The model does not see those Python functions. It sees JSON schemas such as:

```python
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
}
```

`main.py` adds all four schemas to the same `TOOLS` list used by every earlier
tool:

```python
TOOLS = (
    [TIME_TOOL]
    + file_tools.TOOLS
    + [shell_tools.RUN_COMMAND_TOOL]
    + browser_tools.TOOLS
)
```

Their Python functions go into the existing dispatch dictionary:

```python
TOOL_FUNCTIONS = {
    # ...
    "open_page": browser_tools.open_page,
    "read_page": browser_tools.read_page,
    "type_text": browser_tools.type_text,
    "click": browser_tools.click,
}
```

The agent loop is unchanged. `main()` still calls
`agent.handle_message(said)`. If the model returns a `function_call` named
`click`, `self._run_tool()` selects `browser_tools.click` from this dictionary and
passes in the model's JSON arguments.

---

## What is in browser_tools.py

Level 7 adds one module, `browser_tools.py`. `main.py` imports that module,
registers its schemas and functions, and closes the browser when the CLI exits.
The existing agent loop still handles every `function_call`.

Four functions are model-callable tools:

- `open_page(target)` navigates the shared page and returns a JSON snapshot.
- `read_page()` returns a new snapshot without navigating or clicking.
- `type_text(selector, text, press_enter)` fills one text field and can submit
  it.
- `click(selector)` clicks one element and returns a snapshot of the result.

The four model tools reuse the two central helpers:

```text
open_page(target) ─┐
read_page() ───────┼→ _current_page() → shared Playwright Page
type_text(...) ─────┤
click(selector) ────┘

shared Playwright Page → _page_state(page) → JSON tool result
```

The sections below explain those pieces in that order: create and retain the
page, navigate it, convert it to JSON, type, click, and close the browser.

---

## Start one browser page and keep it

`_current_page()` is a utility function used by all four browser tools. On its
first call, it starts Playwright and Chromium and creates one Playwright `Page`.
Later calls return that same `Page`:

```python
_playwright: Playwright | None = None
_browser: Browser | None = None
_page: Page | None = None

def _current_page() -> Page:
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
```

The module variables retain those objects after the function returns. That is
why the number from `click` is still on the page when `read_page` runs in a
later user turn.

Chromium is visible by default. Setting `LEVEL8_HEADLESS=1` launches it without
a visible window.

---

## Open a URL or a workspace file

`open_page(target)` is the first model-callable browser function. It gets the
shared Playwright `Page`, navigates it with `page.goto()`, and converts the
resulting page into JSON:

```python
page = _current_page()
page.goto(url, wait_until="domcontentloaded")
return _page_state(page)
```

`domcontentloaded` waits until the browser has parsed the document. JavaScript
can then change the DOM without changing the file on disk.

`page.goto()` needs a URL. For an `http` or `https` target, `open_page()` uses
the target directly. For a relative workspace path such as
`index.html`, it creates a `file://` URL:

```python
if Path(target).is_absolute():
    raise ValueError("local HTML paths must be relative to the agent workspace")
path = workspace.resolve_path(target)
if not path.is_file():
    raise FileNotFoundError(f"not a file: {target}")
url = path.as_uri()
```

`as_uri()` performs the path-to-URL conversion. `workspace.resolve_path()`
reuses Level 6's containment check so a browser tool cannot open an arbitrary
local file.

---

## Convert a Playwright Page into a tool result

`_page_state(page)` is a utility function used by `open_page`, `read_page`, and
`click`. It converts selected information from a live Playwright `Page` into a
JSON string the model can receive as `function_call_output`.

A Playwright `Page` is a Python object connected to an open browser tab. The
model cannot receive that object or call its methods. `_page_state()` extracts
four things the model can use:

- the current URL;
- the document title;
- up to 4,000 characters of rendered body text;
- visible links, buttons, inputs, selects, text areas, and elements with a
  `role`.

The snapshot is capped at 4,000 characters, as `read_file` is capped at 200
lines. There is no `offset`; omitted page text is not available in a later
call.

Each interactive-element dictionary includes its tag and visible text, plus
attributes that are present such as `id`, `name`, `type`, `role`, `placeholder`,
`aria_label`, and `href`. The model uses those attributes to construct CSS
selectors.

The snapshot describes the current DOM, not the HTML originally downloaded.
Typing changes an input's value, clicking can change the document, and
JavaScript can add or remove elements. `page.locator("body").inner_text()` reads
the text after those changes.

The second locator selects elements that a model may want to operate.
`evaluate_all()` runs JavaScript in the page to remove hidden matches and turn
each visible match into a small dictionary. With those operations established,
the complete utility function is:

```python
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
```

`json.dumps()` creates the string returned to the model. The string is a
snapshot; the live `Page` remains in `_page` for the next browser tool call.

`read_page()` has no additional browser logic. It gets the shared `Page` and
passes it to this utility:

```python
def read_page() -> str:
    return _page_state(_current_page())
```

---

## Fill and submit one text field

`type_text()` is the model-callable wrapper used for Google's search field. It
requires one CSS match, replaces that field's value with `fill()`, and can press
Enter to submit the form:

```python
def type_text(selector: str, text: str, press_enter: bool) -> str:
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
```

For the Google field reported as `{"tag": "textarea", "name": "q"}`, the
selector is `textarea[name="q"]`. `press_enter=true` submits the search. The
returned JSON snapshot contains either the results page or the verification
page that Google displayed.

---

## Select and click one element

Playwright's `page.locator(selector)` finds elements using a CSS selector:

```python
def click(selector: str) -> str:
    page = _current_page()
    matches = page.locator(selector)
    count = matches.count()
    if count != 1:
        raise ValueError(f"selector must match exactly one element; matched {count}: {selector}")
    matches.click()
    page.wait_for_timeout(100)
    return _page_state(page)
```

A result link's `href` from the JSON snapshot can be used in a selector such as
`a[href="https://example.com/page"]`. Requiring exactly one match avoids
silently clicking the wrong element. After the click, the function returns a
new JSON snapshot so the model can observe what changed.

---

## Close the browser

`main()` closes Chromium whether the CLI ends normally or raises an exception:

```python
try:
    # CLI loop
    ...
finally:
    browser_tools.close_browser()
```

`atexit.register(close_browser)` in `browser_tools.py` provides a second cleanup
path if another caller imports the module without using this `main()` function.

---

## Done when

1. Run `uv run playwright install chromium`.
2. Run `uv run --env-file .env series-1-agent-class/07-browser/main.py`.
3. Enter the `random-button.html` request under **Run it**.
4. Confirm a file tool writes `random-button.html` in this level's workspace.
5. Confirm `open_page` opens that file and lists a button.
6. Confirm `click` runs and the model reports the number on the page.
7. Press Ctrl-D and confirm the Chromium window closes.

## Try a live page

A public search page is a second check, not the first one. Start a new
conversation and enter:

```text
Open https://www.google.com and search for:
On what date did the Golden Gate Bridge open to vehicle traffic?

Use the rendered website, not prior knowledge. Open a credible result, then
report the date and source URL. If Google shows a CAPTCHA or human-verification
page, ask me to complete it in the open browser and wait for me to say I am
done.
```

`main.py` tells the model how to handle verification:

```python
"If a page requires a CAPTCHA or other human verification, ask the person "
"to complete it in the visible browser and tell you when they are done."
```

Google may return results, or it may return a CAPTCHA. Completing a CAPTCHA
in the open Chromium window and telling the model you are done is the path
this lesson supports. It is not a required `Done when` step.

---

## What breaks next

The browser can search Google, but Google may return a CAPTCHA instead of search
results. Completing it manually works, but public web search should not require
driving a search-engine page or asking a person for help.

The first chapter of [Advanced Agent Concepts](../../roadmap-intermediate.md)
adds a hosted web-search tool. The model can retrieve public information with
cited sources while keeping the browser for pages that require interaction.
