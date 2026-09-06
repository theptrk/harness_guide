# Level 4 — Make the agent loop safe

## What broke

Level 3 repeats model and tool calls until the model answers. It still assumes
that every model response is complete and every tool succeeds.

Run Level 3 and ask it to use an invalid timezone:

```sh
uv run --env-file .env series-1-agent-class/03-loop/main.py
```

```text
📝 you › Use get_current_time with Mars/Olympus. If it fails, explain why.
```

`ZoneInfo` raises an exception. The turn ends before the model receives a
`function_call_output`, so it cannot explain or correct the failure.

Level 4 establishes the safety rules that every later tool uses:

1. Validate a model response before executing anything it requested.
2. Turn a tool failure into a matching `function_call_output`.
3. Bound tool execution and force an answer after the budget is exhausted.
4. Add only completed turns to conversation history.

These are tool-protocol rules. API retry and timeout policy arrives after the
complete agent exists.

---

## Run it

```sh
uv run --env-file .env series-1-agent-class/04-safe-loop/main.py
```

Ask:

```text
📝 you › Use get_current_time with Mars/Olympus. If it fails, explain why.
```

The tool still fails, but the agent loop continues:

```text
tool › get_current_time({"timezone":"Mars/Olympus"})
tool ‹ ZoneInfoNotFoundError: 'No time zone found with key Mars/Olympus'

🤖 model › Mars/Olympus is not a valid IANA timezone.
```

The exception became data the model could read.

---

## Validate before executing

An HTTP request can succeed while the model response is incomplete. Tool
arguments in that response may be partial.

`_require_complete()` runs before output items are retained and before a tool
can run:

```python
response = self.client.responses.create(...)

self._require_complete(response)
turn_items.extend(
    item.model_dump(mode="json", exclude_none=True)
    for item in response.output
)
```

A completed response is accepted. An incomplete or failed response raises
`HarnessError`. The active turn remains local and no tool from the rejected
response executes.

```python
if response.status == "incomplete":
    reason = (
        response.incomplete_details.reason
        if response.incomplete_details
        else "unknown"
    )
    raise HarnessError(
        f"model response incomplete: {reason}; "
        "no tool from this response was executed"
    )
```

The final operational level adds a configurable output limit that makes this
failure easy to reproduce. This level establishes the rule before file, shell,
and browser tools introduce side effects.

---

## A tool error is still a tool result

A completed `function_call` needs one `function_call_output` with the same
`call_id`, whether the Python function succeeds or fails.

```text
function_call(call_123)
function_call_output(call_123, successful value)
```

and:

```text
function_call(call_456)
function_call_output(call_456, error description)
```

`_run_tool()` catches failures caused by the model-selected name, arguments, or
function:

```python
def _run_tool(self, tool_call) -> str:
    try:
        arguments = json.loads(tool_call.arguments)
        tool_function = TOOL_FUNCTIONS.get(tool_call.name)
        if tool_function is None:
            raise LookupError(f"unknown tool: {tool_call.name}")
        return tool_function(**arguments)
    except Exception as error:
        return f"{type(error).__name__}: {error}"
```

The caller puts that string in the matching output item. The next model pass
can retry with different arguments or explain the failure.

This `except` does not cover model API calls or the rest of the agent loop.
Programming errors outside tool dispatch still remain visible.

---

## Bound execution

Level 3 introduced a five-call budget with the loop. This level makes the
failure behavior explicit.

After five executed tools, the next request receives a result without running
Python:

```text
ToolCallLimit: the limit of 5 tool calls has been reached
```

The following model request uses:

```python
tool_choice="none"
```

That request must answer using the results already available. Returning the
limit as a tool result preserves the required call/output pair.

Five is this tutorial's budget, not a generally correct production value.

---

## Commit one complete turn

`self.input_items` contains completed conversation history. `turn_items`
contains the current request, model output, and tool results:

```python
input=self.input_items + turn_items
```

Only the successful answer path commits:

```python
self.input_items.extend(turn_items)
```

An interrupted, incomplete, or failed turn never reaches that statement.
Already-completed tool side effects cannot be undone by discarding conversation
items. Later file and shell lessons call this distinction out when side effects
exist.

---

## Done when

1. Start Level 4.
2. Ask for the current time in Tokyo and confirm the tool succeeds.
3. Ask for `Mars/Olympus` and confirm the tool result contains
   `ZoneInfoNotFoundError`.
4. Confirm the model explains the invalid timezone instead of the terminal
   printing `call failed`.
5. Inspect `main.py` and confirm `_require_complete(response)` appears before
   `_run_tool(tool_call)` can be reached.

---

## What breaks next

Ask for several paragraphs. The terminal remains unchanged until each complete
model response arrives.

[Level 5](../05-stream/LESSON.md) streams text while preserving the completed
turn rules from this level.
