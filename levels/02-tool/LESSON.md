# Level 2 — Give it one tool

## What broke

Level 1 can continue a conversation, but the model still has no clock. Ask:

```text
you › What time is it in Tokyo?
```

It may answer with a plausible time. The text is not evidence that it checked the time.

When I ran it I got this

```
›› Tokyo time is **Japan Standard Time (JST, UTC+9)**. I can’t access a live clock, but you can check your device’s world clock for the current exact time.
```

This level gives the model one way to get the current time. The mechanism has two separate parts:

- A Python function does the work.
- A JSON tool definition tells the model that the function is available.

The model never executes the function. It returns a request to call it. Your code decides whether to run it.

---

## Run it

```sh
uv run --env-file .env levels/02-tool/main.py --new
```

Ask:

```text
you › What time is it in Tokyo?
```

The output includes the requested call and the value returned by Python:

```text
tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {"timezone": "Asia/Tokyo", "datetime": "2026-08-18T07:23:41+09:00"}

››› It is 7:23 AM on August 18 in Tokyo.
    [2 model call(s) · ...]
```

There are two model calls. The first asks to use the tool. Your code runs the function. The second receives the result and writes the answer.

---

## What's in here

```text
levels/02-tool/
  LESSON.md
  main.py       the prompt loop and the time tool
  history.py    the conversation record from Level 1
  chats/        made when you first run it, gitignored
```

`history.py` changes at this level. The chat file now stores every item sent through `input` and every item returned in `response.output`, including function calls and their results. The tool definition, Python function, and one-tool round trip remain in `main.py`.

---

## The function and its description are different things

This function reads the clock:

```python
def get_current_time(timezone: str) -> str:
    now = datetime.now(ZoneInfo(timezone))
    return json.dumps(
        {
            "timezone": timezone,
            "datetime": now.isoformat(timespec="seconds"),
        }
    )
```

Python keeps executable tools in a dictionary keyed by the name exposed to the model:

```python
TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
}
```

The model cannot inspect or invoke that Python function. It sees this tool definition:

```python
TOOLS = [
    {
        "type": "function",
        "name": "get_current_time",
        "description": "Get the current date and time in a specific timezone.",
        "parameters": {
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "An IANA timezone name, such as Asia/Tokyo or America/New_York.",
                }
            },
            "required": ["timezone"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]
```

The definition supplies a name, a description, and an argument schema. `strict: True` requires arguments that match that schema. For “Tokyo,” the model chooses the IANA timezone name `Asia/Tokyo`.

The definition is passed with the input items:

```python
response = client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    input=input_items,
    tools=TOOLS,
    reasoning={"effort": "none"},
)
```

Passing `tools` gives the model another kind of output it may produce. It does not run any Python.

---

## What the first model call returns

When the model wants the time, `response.output` contains a `function_call` item:

```json
{
  "type": "function_call",
  "name": "get_current_time",
  "arguments": "{\"timezone\":\"Asia/Tokyo\"}",
  "call_id": "call_..."
}
```

`arguments` is a JSON string. The code parses it and uses the requested name to select the Python function:

```python
arguments = json.loads(tool_call.arguments)

tool_function = TOOL_FUNCTIONS.get(tool_call.name)
if tool_function is None:
    raise RuntimeError(f"unknown tool: {tool_call.name}")

tool_result = tool_function(**arguments)
```

`.get()` returns `None` for an unknown name, so the code raises an error that names the invalid request instead of exposing a dictionary `KeyError`. The model selected the tool and supplied arguments. Your code selected and ran the corresponding function.

Before running the function, the code writes every item from the response to the conversation file:

```python
for output_item in response.output:
    history.append_item(
        chat_file_path,
        output_item.model_dump(mode="json", exclude_none=True),
    )
```

`response.output` contains OpenAI SDK objects. `model_dump()` converts each one to a JSON-compatible dictionary; `append_item()` writes that dictionary. This records the `function_call`. If the model returned a normal message instead, the same loop records that message.

---

## Sending the result back

The second request needs both the model's function call and the corresponding result. The function call is already on disk. Append the result:

```python
history.append_item(
    chat_file_path,
    {
        "type": "function_call_output",
        "call_id": tool_call.call_id,
        "output": tool_result,
    },
)

input_items = history.get_input_items(chat_file_path)
```

`call_id` connects the result to the request. `get_input_items()` rebuilds the second request from the file; the function call and result are not held only in memory. The model can then answer using the timestamp returned by Python.

After the second model call, the same loop appends its output items. A completed round trip contains, in order:

1. The user message.
2. The model's `function_call`.
3. The `function_call_output` returned by Python.
4. The model's final message.

This level handles at most one tool call per model response. `parallel_tool_calls=False` makes the model request calls one at a time. There is no loop that handles another request after the second model call.

---

## Done when

Ask for the current time in a timezone. The terminal should show:

1. A `get_current_time` request from the model.
2. A timestamp returned by the Python function.
3. A final answer based on that timestamp.

---

## What breaks next

Ask for two current times:

The code handles the first tool request. If the model asks for the second timezone on its next response, the code does not run that request. Handling an unknown number of tool calls requires a loop around the model call, tool execution, and tool result.

```text
you › What time is it in Tokyo and New York?

tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {"timezone": "Asia/Tokyo", "datetime": "2026-08-18T08:33:07+09:00"}

[stopped: model requested another get_current_time call]
    [2 model call(s) · 406 in + 44 out]
```

That is [Level 3](../03-loop/LESSON.md).