# Level 2 — Give it one tool

Level 1 can converse, but it has no live clock. This level gives the model one
function tool, `get_current_time`.

```sh
uv run --env-file .env series-1-agent-class/02-tool/main.py
```

Ask:

```text
📝 you › Use get_current_time to tell me the current time in Tokyo.
```

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
connects the result to the request. After the second response, the harness
checks for another tool request. Level 2 deliberately raises an error if it
finds one:

```python
next_tool_call = next(
    (item for item in response.output if item.type == "function_call"),
    None,
)

if next_tool_call is not None:
    raise RuntimeError("this lesson allows one tool call ...")
answer = response.output_text
```

Otherwise, the completed turn is committed with:

```python
self.input_items.extend(turn_items)
```

A completed round trip contains the user item, function call, function result,
and final model message. All four stay in memory and become input to the next
user message.

The control flow is therefore a fixed sequence: call the model, optionally run
one tool, then call the model once more. Ask for the time in Tokyo and New York
to see the explicit one-tool error.

[Level 3](../03-loop/LESSON.md) keeps `_run_tool()`, the response-item search,
the counters, and the conversation bookkeeping unchanged. It moves the model
call and tool branch inside `while True`, so another tool request starts another
iteration instead of raising an error.
