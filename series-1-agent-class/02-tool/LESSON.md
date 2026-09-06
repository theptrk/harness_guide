# Level 2 — Give it one tool

## What broke

Level 1 can retain a conversation, but it can only produce model text. Asking
for the exact current time requires data that the harness does not provide.

Level 2 keeps the same terminal loop and gives the model one function tool,
`get_current_time`. It allows at most one tool call in a turn.

## Run it

```sh
uv run --env-file .env series-1-agent-class/02-tool/main.py
```

Ask the model to use the tool:

```text
📝 you › Use get_current_time to tell me the current time in Tokyo.

tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {
  "timezone": "Asia/Tokyo",
  "datetime": "..."
}

🤖 model › The current time in Tokyo is ...
    [2 model call(s) · 1 tool call(s) · ...]
```

The timestamp and answer will differ. The event order should not.

The model does not execute Python. The tool definition tells it what it may
request. The harness receives that request, selects the matching Python
function, executes it, and sends the result to the model.

## Describe and register the tool

`TOOLS` gives the model the function name, description, and JSON argument
schema. `TOOL_FUNCTIONS` maps that public name to executable Python:

```python
TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
}
```

`strict: True` constrains the generated argument shape. Python still validates
whether a value such as `Asia/Tokyo` is meaningful.

## Emit observable steps

A turn now has up to two model calls with a tool call between them. The tool
request and result are observable before the final answer. Returning only after
the turn ends would hide those intermediate steps from the host.

`Agent` therefore requires an `emit` callback and calls it once per step:

```python
agent = Agent(OpenAI(), emit=print_event)
```

Each call passes one dict with a `type`:

- `tool`: the model requested a function. Fields `name` and `arguments`.
- `tool_result`: the function returned. Fields `name` and `output`.
- `text`: the answer.
- `done`: the turn is over. Model calls, tool calls, and token counts.

`print_event()` in `main.py` prints each one. `Agent` has no `print()` in it.
A host that is not a terminal passes a different function.

## The first model call

`responses.create()` returns one response object. Its `output` list can contain
different item types. This lesson cares about two outcomes: a model message or
a function call. When the model wants the clock, one item looks like:

```json
{
  "type": "function_call",
  "name": "get_current_time",
  "arguments": "{\"timezone\":\"Asia/Tokyo\"}",
  "call_id": "call_..."
}
```

The harness finds that item by its `type`:

```python
tool_call = next(
    (item for item in response.output if item.type == "function_call"),
    None,
)
```

`tool_call` is therefore the function-call item returned by the model. It holds
the tool's `name`, JSON `arguments`, and the `call_id` used to match its result.
The harness passes the whole request to the agent's `_run_tool()` method:

```python
def _run_tool(self, tool_call) -> str:
    arguments = json.loads(tool_call.arguments)
    tool_function = TOOL_FUNCTIONS.get(tool_call.name)
    if tool_function is None:
        raise RuntimeError(f"unknown tool: {tool_call.name}")
    return tool_function(**arguments)
```

## Send the result back

A tool request is not an answer. The next model call needs the request and a
matching result:

```python
turn_items.append(
    {
        "type": "function_call_output",
        "call_id": tool_call.call_id,
        "output": tool_result,
    }
)
```

Both calls receive `self.input_items + turn_items`. The matching `call_id`
connects the result to the request.

## Check completion

The control flow is fixed: call the model, optionally run one tool, then call
the model once more. After the second response, the harness checks for another
tool request. Level 2 raises an error if it finds one:

```python
next_tool_call = next(
    (item for item in response.output if item.type == "function_call"),
    None,
)

if next_tool_call is not None:
    raise RuntimeError("this lesson allows one tool call ...")
answer = response.output_text
```

The final answer must also contain text:

```python
if not answer:
    raise RuntimeError("model returned no answer")
```

Only after both checks pass is the completed turn committed:

```python
self.input_items.extend(turn_items)
```

A completed round trip contains the user item, function call, function result,
and final model message. All four stay in memory and become input to the next
user message.

## Done when

1. Ask a question that needs no tool. Confirm `done` reports one model call and
   zero tool calls.
2. Ask for the time in Tokyo. Confirm the event order is `tool`,
   `tool_result`, `text`, `done`.
3. Confirm `done` reports two model calls and one tool call.
4. Ask for separate time lookups for Tokyo and New York. If the second response
   requests another tool, confirm the terminal prints `call failed`.

## What breaks next

A turn that needs two tool calls reaches the explicit one-tool check and fails.

[Level 3](../03-loop/LESSON.md) keeps `_run_tool()`, the response-item search,
the counters, and the conversation bookkeeping unchanged. It moves the model
call and tool branch inside `while True`, so another tool request starts another
iteration instead of raising an error.
