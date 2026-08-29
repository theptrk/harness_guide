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

When the model wants the clock, `response.output` contains a function call:

```json
{
  "type": "function_call",
  "name": "get_current_time",
  "arguments": "{\"timezone\":\"Asia/Tokyo\"}",
  "call_id": "call_..."
}
```

The harness parses the arguments and executes the registered function:

```python
arguments = json.loads(tool_call.arguments)
tool_function = TOOL_FUNCTIONS.get(tool_call.name)
tool_result = tool_function(**arguments)
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
connects the result to the request. After the second response, the completed
turn is committed with:

```python
self.input_items.extend(turn_items)
```

A completed round trip contains the user item, function call, function result,
and final model message. All four stay in memory and become input to the next
user message.

This level handles at most one tool call. Ask for the time in Tokyo and New York
to expose that limitation. [Level 3](../03-loop/LESSON.md) replaces the fixed
sequence with an agent loop.
