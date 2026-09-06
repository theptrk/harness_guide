# Series 1 — legacy function-based implementation

This is not the default path. [`series-1-agent-class/`](../series-1-agent-class/README.md)
is the canonical Series 1. It covers everything here, splits Level 4 into loop
safety and operational policy, and adds a level for persistence.

This folder is kept because the two are worth reading against each other. Here
the turn is a function, `run_turn()`, and the JSONL file is the conversation
from Level 1 on. There the turn is a method on an `Agent` that holds the
conversation in memory until Level 9.

| Level | Lesson | Adds |
|---|---|---|
| 00 | [Model](00-model/LESSON.md) | one model call |
| 01 | [Conversation](01-conversation/LESSON.md) | an append-only conversation file |
| 02 | [One tool](02-tool/LESSON.md) | one function call and result |
| 03 | [Loop](03-loop/LESSON.md) | repeated model and tool calls |
| 04 | [Harden](04-harden/LESSON.md) | response validation, bounded execution, retries, timeouts |
| 05 | [Stream](05-stream/LESSON.md) | incremental answer display |
| 06 | [Files](06-files/LESSON.md) | confined file tools |
| 07 | [Shell](07-shell/LESSON.md) | approved shell commands |
| 08 | [Browser](08-browser/LESSON.md) | browser tools |

## Where the two differ

- The conversation is a file from Level 1. Level 2 rewrites the line format
  when messages turn out not to hold `function_call` items, and
  `get_input_items()` carries a fallback for files written before that change.
  The class series holds API items in memory and introduces the file once, at
  Level 9, in its final shape.
- Levels 1 through 3 write each item as it happens, so a turn can end partway
  through. Every `function_call` written to the file gets a
  `function_call_output` written too, and `get_input_items()` leaves out a call
  that has none. Level 4 buffers the whole turn and drops both mechanisms.
- Printing is inline. `run_turn()` prints tool activity and the answer, and
  `stream_response()` prints deltas. The class series gives `Agent` an `emit`
  callback and leaves display to the host.
- `shell_tools.request_approval()` reads the keyboard, with
  `approve=request_approval` as a default argument. The class series requires
  `approve` to be passed in, so the module cannot prompt on its own.
- `browser_tools` keeps the Playwright driver, browser, and page in module
  globals. The class series has a `Browser` class that owns its page.

## Run it

Complete the [root setup](../README.md#setup), then:

```sh
uv run --env-file .env series-1/00-model/main.py
```

Level 08 requires Chromium once:

```sh
uv run playwright install chromium
```

## Compare adjacent levels

```sh
diff -ru -x chats -x agent_workspace \
  series-1/03-loop \
  series-1/04-harden
```
