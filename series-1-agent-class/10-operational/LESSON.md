# Level 10 — Add operational policy

## What broke

Level 9 has the complete capability path, but its model client has no explicit
retry or timeout policy. A transient API failure ends the turn immediately. A
completed refusal can also leave `response.output_text` empty even though the
model returned content.

Level 10 keeps every capability and adds operational policy:

- SDK retries for transient API failures and an SDK request timeout;
- an optional `MAX_OUTPUT_TOKENS` output cap;
- terminal answer extraction for normal text and refusals;
- a terminal exit policy for API and harness failures.

Response validation, model-readable tool errors, and tool-call limits remain
in force from Level 4. They are retained safety rules, not additions in this
level.

## Run it

Start a new persistent conversation:

```sh
uv run --env-file .env series-1-agent-class/10-operational/main.py --new
```

Omit `--new` to continue the newest conversation:

```sh
uv run --env-file .env series-1-agent-class/10-operational/main.py
```

## Retry and timeout policy

`main()` configures the client once and hands it to the agent:

```python
client = OpenAI(max_retries=API_RETRIES, timeout=API_TIMEOUT_SECONDS)
agent = Agent(client, browser, chat_file_path, emit=..., approve=..., max_output_tokens=...)
```

The retry setting applies to transient API failures handled by the SDK. The API
timeout does not bound file tools, shell commands, or browser operations; those
tools need their own limits because cancelling the wait for a tool does not
necessarily stop its side effect.

## Response validation remains in force

Level 4 established that a response must be complete before any returned tool
call runs. This level retains that check. `self._require_complete(response)`
runs before response output is added to the active turn and before a function
call can be dispatched:

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

Level 5 uses `response.output_text` directly when a stream produces no visible
text. This level also recognizes refusals, which are a distinct
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
  MAX_OUTPUT_TOKENS=16 uv run --env-file .env series-1-agent-class/10-operational/main.py --new
```

The expected result is a short failure such as:

```text
harness failed: model response incomplete: max_output_tokens; no tool from this response was executed
```

The setting is optional. Without it, the request omits `max_output_tokens`.

## Level 4 tool safety remains in force

Level 4 requires a matching `function_call_output` for every completed function
call, including when the Python tool fails. This level retains
`self._run_tool()`, which converts failures into a readable string so the model
can correct an argument or explain the problem:

```python
try:
    arguments = json.loads(tool_call.arguments)
    tool_function = self.tool_functions.get(tool_call.name)
    if tool_function is None:
        raise LookupError(f"unknown tool: {tool_call.name}")
    return tool_function(**arguments)
except Exception as error:
    return f"{type(error).__name__}: {error}"
```

The Level 4 executed-tool budget also remains in force. Once the budget is exhausted,
the loop returns a `ToolCallLimit` result and makes the next request with
`tool_choice="none"`.

## The agent raises, main() decides

`handle_message()` does not catch `OpenAIError` or `HarnessError`. Both leave
the method, and nothing from that turn reaches the chat file. `main()` catches
them and exits:

```python
try:
    agent.handle_message(said)
except OpenAIError as error:
    sys.exit(f"API failed after retries: {error}")
except HarnessError as error:
    sys.exit(f"harness failed: {error}")
```

Ending the process is the terminal's policy. A host that serves many
conversations would report the error and keep running. The agent does not
know which host it has.

`MAX_OUTPUT_TOKENS` is read by `configured_output_limit()` in `main()` and
passed to `Agent` as `max_output_tokens`. The agent reads no environment
variables.

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

This is the end of the series. The earlier lessons add capabilities one at a
time. This lesson adds operational policy to the complete agent.
