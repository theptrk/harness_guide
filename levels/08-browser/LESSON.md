# Level 8 — Use a browser

## What Level 8 adds

Level 7's shell makes browser automation possible, but the model must recognize
that it can write and run a Playwright script. A more capable or more deliberate
model may do that. Another model may stop because no browser tool was named.

Level 8 gives the model three browser tools: `open_page`, `read_page`, and
`click`. You install Chromium once. All three tools operate on one persistent
Playwright page.

---

## Install Chromium once

Playwright is a Python dependency, but its browser binary is installed
separately. Run this once before using Level 8:

```sh
uv run playwright install chromium
```

---

## Run it

Start a new Level 8 conversation:

```sh
uv run --env-file .env levels/08-browser/main.py --new
```

Enter this as one request:

```text
Use write_file to create random-button.html with exactly:

<!doctype html>
<button id="value" onclick="this.textContent = Math.random()">Click me</button>

Then open the rendered page in a browser, click the button once, and report the
exact number displayed on the button. Do not infer a value from the source.
```

The agent first creates the file:

```text
tool › write_file({"path":"random-button.html","content":"<!doctype html>\n<button id=\"value\" onclick=\"this.textContent = Math.random()\">Click me</button>"})
tool ‹ {"path": "random-button.html", "written": true, "characters": 95}
```

It opens the local page:

```text
tool › open_page({"target":"random-button.html"})
tool ‹ {
  "url": "file:///…/levels/08-browser/agent_workspace/random-button.html",
  "title": "",
  "text": "Click me",
  "interactive_elements": [
    {"tag": "button", "id": "value", "visible_text": "Click me"}
  ]
}
```

The `#value` CSS selector selects the element whose HTML is `id="value"`.

```text
tool › click({"selector":"#value"})
tool ‹ {
  "url": "file:///…/random-button.html",
  "title": "",
  "text": "<generated number>",
  "interactive_elements": [
    {"tag": "button", "id": "value", "visible_text": "<same generated number>"}
  ]
}
```

It reads the same page once more:

```text
tool › read_page({})
tool ‹ {
  "url": "file:///…/random-button.html",
  "title": "",
  "text": "<generated number>",
  "interactive_elements": [
    {"tag": "button", "id": "value", "visible_text": "<same generated number>"}
  ]
}
```

The actual result is a run-specific decimal such as
`0.3141592653589793`; it is not fixed. The final answer reports the exact value
returned by that run's `read_page`.

---

## Three browser tools

Level 8 gives the model exactly three browser tools:

- `open_page(target)` opens an `http` or `https` URL, or a relative HTML path
  inside this level's `agent_workspace`.
- `read_page()` returns the current URL, title, rendered text, and visible
  interactive elements.
- `click(selector)` requires exactly one CSS match, clicks it, and returns the
  updated page state.

`browser_tools.py` starts Chromium only when one of these tools first needs it.
The same browser page stays alive across tool calls and user turns in that
process. `open_page`, `click`, and `read_page` therefore operate on the same
page.

The default browser window is visible so you can watch it. The browser closes
when the program exits, including after Ctrl-C or Ctrl-D.

---

## Source is not rendered state

`read_file("random-button.html")` returns source code:

```html
<button id="value" onclick="this.textContent = Math.random()">Click me</button>
```

After the click, `read_page()` returns rendered state. Its text contains the
number now displayed by the button. Reading the source again would still show
`Math.random()`.

Each browser result follows the existing agent loop:

```text
model requests browser tool
→ Python operates the shared page
→ structured page state goes back to the model
→ model chooses the next tool or answers
```

The loop, streaming display, turn IDs, time tool, confined file tools, and shell
approval prompt are unchanged from Level 7.

---

## Done when

1. Run `uv run playwright install chromium`.
2. Run `uv run --env-file .env levels/08-browser/main.py --new`.
3. Enter the `random-button.html` request under **Run it**.
4. Confirm `write_file` creates
   `levels/08-browser/agent_workspace/random-button.html`.
5. Confirm a visible Chromium window opens that local file.
6. Confirm `open_page` reports button text `"Click me"` and id `"value"`.
7. Confirm `click` uses `"#value"` and its result contains a decimal number.
8. Confirm `read_page` returns that same number.
9. Confirm the final answer reports that exact number.
10. Press Ctrl-D and confirm the Chromium window closes.

---

## What breaks next

Ask Level 8 to navigate to Railway and continue into your account. It can reach
the login page, but it has no mechanism to pause the turn, give you control,
learn that you finished signing in, and resume. Your password must be entered
directly into the browser, not sent to the model.

Level 9 adds human takeover: the agent waits while you control the same browser,
then resumes after you finish signing in.
