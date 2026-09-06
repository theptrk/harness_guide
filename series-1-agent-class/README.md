# Series 1 — Build an Agent Harness

This is the canonical Series 1 path. It builds one local `Agent` class in 11
levels.

| Level | Lesson | Adds |
|---|---|---|
| 00 | [Model](00-model/LESSON.md) | one model call |
| 01 | [Conversation](01-conversation/LESSON.md) | in-memory conversation state |
| 02 | [One tool](02-tool/LESSON.md) | one function call and result |
| 03 | [Loop](03-loop/LESSON.md) | repeated model and tool calls |
| 04 | [Safe loop](04-safe-loop/LESSON.md) | response validation and bounded execution |
| 05 | [Stream](05-stream/LESSON.md) | incremental answer display |
| 06 | [Files](06-files/LESSON.md) | confined file tools |
| 07 | [Shell](07-shell/LESSON.md) | approved shell commands |
| 08 | [Browser](08-browser/LESSON.md) | browser tools |
| 09 | [Persistence](09-persistence/LESSON.md) | append-only conversation history |
| 10 | [Operational policy](10-operational/LESSON.md) | retries, timeouts, output bounds, and failure handling |

## Stable boundaries

The levels add capabilities without moving terminal policy into `Agent`.

- `Agent` does not print, read the keyboard, read environment variables, or
  exit the process.
- The host owns environment checks, input, display, approval prompts,
  interruption behavior, failure presentation, and process exit.
- The host constructs dependencies and passes them to `Agent`: the OpenAI
  client, `emit`, `approve`, the browser, the selected chat path, and configured
  limits as each becomes necessary.
- The public lifecycle is construction, `handle_message(said)`, and, once the
  browser exists, `close()`.

`emit(event)` reports model starts, answer text, tool calls, tool results, and
the completed-turn summary. The terminal host decides how to display each
event. `approve(command)` asks the host for a shell-command decision.

## Stable turn rules

- Conversation state uses canonical Responses API items: user messages,
  returned `message` and `function_call` items, and
  `function_call_output` items with the matching `call_id`.
- An active turn stays local and commits to conversation history only after the
  model completes the turn.
- A terminal model response is validated before any function call from that
  response executes.
- Every completed function call receives a `function_call_output`, including an
  unknown tool, invalid arguments, a rejected command, or an exhausted budget.
- Tool errors are strings returned to the model. They are data in the loop, not
  unhandled tool exceptions.
- Model and tool execution is bounded by the policies introduced in the safe
  loop, shell, browser, and operational levels.
- Streamed text deltas are display events only. Completed response items are the
  conversation record.
- Discarding a failed active turn does not roll back completed tool side effects.

## Run it

Complete the [root setup](../README.md#setup), then start Level 00:

```sh
uv run --env-file .env series-1-agent-class/00-model/main.py
```

Level 08 requires Chromium once:

```sh
uv run playwright install chromium
```

## Compare adjacent levels

Run diffs from the repository root. Exclude generated conversations and agent
workspace files:

```sh
diff -ru -x chats -x agent_workspace \
  series-1-agent-class/03-loop \
  series-1-agent-class/04-safe-loop
```

Change both folder names to inspect another adjacent pair. Each folder is a
complete runnable level, so the diff shows the implementation and lesson
changes for the next level.
