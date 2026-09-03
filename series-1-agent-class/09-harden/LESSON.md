# Level 9 — Harden the complete agent

## What Level 9 adds

Level 8 has the complete capability path: streaming, files, shell commands, a
browser, and persistent conversations. This final level keeps those capabilities
and adds cross-cutting failure policy around the model API:

- the OpenAI client retries transient API failures and uses a request timeout;
- an optional `MAX_OUTPUT_TOKENS` setting places a bound on model output;
- every terminal response is checked before any returned tool call is executed;
- terminal answer extraction handles both normal text and refusals;
- expected API and harness failures stop with a short, explicit message.

Tool-call limits and model-readable tool errors were introduced with the agent
loop, where those behaviors first became necessary. They remain in this final
agent, but they are not new here.

## Run it

Start a new persistent conversation:

```sh
uv run --env-file .env series-1-agent-class/09-harden/main.py --new
```

Omit `--new` to continue the newest conversation:

```sh
uv run --env-file .env series-1-agent-class/09-harden/main.py
```

## Retry and timeout policy

The agent configures the client once:

```python
self.client = OpenAI(
    max_retries=API_RETRIES,
    timeout=API_TIMEOUT_SECONDS,
)
```

The retry setting applies to transient API failures handled by the SDK. The API
timeout does not bound file tools, shell commands, or browser operations; those
tools need their own limits because cancelling the wait for a tool does not
necessarily stop its side effect.

## Validate before executing tools

A successful HTTP exchange can still produce an incomplete or failed model
response. `self._require_complete(response)` runs before response output is added to
the active turn and before a function call can be dispatched:

```python
response, text_was_streamed = self._stream_response(...)

self._require_complete(response)
turn_items.extend(
    item.model_dump(mode="json", exclude_none=True)
    for item in response.output
)
```

If a response is incomplete, its function-call arguments may be partial.
Executing that call would mean guessing the missing data. The agent stops the
turn instead, so neither the partial model output nor the active turn is appended
to the JSONL history.

Already-completed tool side effects cannot be rolled back. For example, a file
write can succeed before a later model call fails. Conversation commits and tool
transactions are separate concerns.

## Validate terminal answer content

Earlier levels use `response.output_text` directly when a stream produces no
visible text. The hardened agent also recognizes refusals, which are a distinct
message-content type, and rejects a completed response that contains neither:

```python
@staticmethod
def _response_text(response) -> str:
    if response.output_text:
        return response.output_text
    for item in response.output:
        if item.type != "message":
            continue
        for content in item.content:
            if content.type == "refusal":
                return content.refusal
    raise HarnessError("completed model response contained no answer")
```

This distinction belongs here because it turns an unexpected terminal response
shape into explicit harness policy rather than assuming the normal text path.

## Optional output bound

`MAX_OUTPUT_TOKENS` is deliberately introduced only here because it creates an
additional failure mode that the final agent must handle:

```sh
printf '%s\n' 'Use get_current_time to tell me the current time in Tokyo.' |
  MAX_OUTPUT_TOKENS=16 uv run --env-file .env series-1-agent-class/09-harden/main.py --new
```

The expected result is a short failure such as:

```text
harness failed: model response incomplete: max_output_tokens; no tool from this response was executed
```

The setting is optional. Without it, the request omits `max_output_tokens`.

## Tool failures still belong to the loop

A completed function call always needs a matching `function_call_output`,
including when the Python tool fails. `self._run_tool()` converts failures into
a readable string so the model can correct an argument or explain the problem:

```python
try:
    arguments = json.loads(tool_call.arguments)
    tool_function = TOOL_FUNCTIONS[tool_call.name]
    return tool_function(**arguments)
except Exception as error:
    return f"{type(error).__name__}: {error}"
```

The executed-tool budget also remains in force. Once the budget is exhausted,
the loop returns a `ToolCallLimit` result and makes the next request with
`tool_choice="none"`.

## Done when

1. Start the agent with `--new` and complete a normal tool-using request.
2. Exit, restart without `--new`, and confirm the conversation persists.
3. Ask for an invalid timezone and confirm the tool error becomes model-readable
   output rather than a Python traceback.
4. Run the low-`MAX_OUTPUT_TOKENS` command above.
5. Confirm the incomplete response is rejected and its turn is absent from the
   JSONL chat file.
6. Inspect `main.py` and confirm `self._require_complete(response)` occurs before
   `self._run_tool(tool_call)` can execute a returned call.

This is the end of the series: the earlier lessons build capabilities one at a
time, and this lesson adds the cross-cutting operational policy last.
