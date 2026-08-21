# Level 2 — Give it one tool

## What broke

Level 1 can continue a conversation, but the model still has no clock. Ask:

```text
📝 you › What time is it in Tokyo?
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
uv run --env-file .env series-1/02-tool/main.py --new
```

Ask:

```text
📝 you › Use get_current_time to tell me the current time in Tokyo.
```

The output includes the requested call and the value returned by Python:

```text
tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {"timezone": "Asia/Tokyo", "datetime": "2026-08-18T07:23:41+09:00"}

🤖 model › It is 7:23 AM on August 18 in Tokyo.
    [2 model call(s) · ...]
```

There are two model calls. The first asks to use the tool. Your code runs the function. The second receives the result and writes the answer.

---

## What's in here

```text
series-1/02-tool/
  LESSON.md
  main.py       the prompt loop and the time tool
  history.py    the conversation record, now storing API items
  chats/        made when you first run it, gitignored
```

`history.py` changes at this level. The chat file now stores every item sent through `input` and every item returned in `response.output`, including function calls and their results. The tool definition, Python function, and one-tool round trip remain in `main.py`.

Level 1 stored message fields at the top level of each JSONL line. Level 2 stores any API item under `item`:

```json
{"at": "...", "item": {"role": "user", "content": "Use get_current_time..."}}
{"at": "...", "item": {"type": "function_call", "name": "get_current_time", "call_id": "call_..."}}
{"at": "...", "item": {"type": "function_call_output", "call_id": "call_...", "output": "..."}}
```

The wrapper belongs to this program. `get_input_items()` removes it before calling the API.

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

The definition supplies a name, a description, and an argument schema. That JSON is the only documentation the model receives. `strict: True` requires arguments that match that schema. For “Tokyo,” the model chooses the IANA timezone name `Asia/Tokyo`.

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

A `function_call` describes what the model wants Python to run; it is not the answer. If the item says its status is `completed`, that means the model finished generating the request. The Python function has not run yet.

After Python runs the function, the next model request must include two items:

1. The original `function_call`.
2. A `function_call_output` with the same `call_id` and the function's result.

The function call is already on disk. Append its result:

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

The matching `call_id` connects this output to the model's request:

```text
function_call(call_...)
function_call_output(call_...)
```

`get_input_items()` rebuilds the second request from the file, including both items. The model can then answer using the timestamp returned by Python.

After the second model call, the same loop appends its output items. A completed round trip contains, in order:

1. The user message.
2. The model's `function_call`.
3. The `function_call_output` returned by Python.
4. The model's final message.

This level handles at most one tool call per model response. `parallel_tool_calls=False` makes the model request calls one at a time. There is no loop that handles another request after the second model call.

---

## Done when

1. Start a new conversation:

   ```sh
   uv run --env-file .env series-1/02-tool/main.py --new
   ```

2. Enter `Use get_current_time to tell me the current time in Tokyo.`
3. Confirm that the terminal shows, in order:
   - `tool › get_current_time({"timezone":"Asia/Tokyo"})`
   - A `tool ‹` result containing an ISO timestamp.
   - A final answer giving the Tokyo time.
   - A usage line reporting `2 model call(s)`.

---

## What breaks next

Ask for two current times:

The code handles the first tool request. If the model asks for the second timezone on its next response, the code does not run that request. Handling an unknown number of tool calls requires a loop around the model call, tool execution, and tool result.

```text
📝 you › Use get_current_time once for each city. What time is it in Tokyo and New York?

tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {"timezone": "Asia/Tokyo", "datetime": "2026-08-18T08:33:07+09:00"}

[stopped: model requested another get_current_time call]
    [2 model call(s) · 406 in + 44 out]
```

That is [Level 3](../03-loop/LESSON.md).