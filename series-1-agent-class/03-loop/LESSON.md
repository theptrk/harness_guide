# Level 3 — Build the agent loop

## What broke

Level 2 handles one tool request with a fixed sequence. The terminal input loop
is already in place and stays unchanged. A request for several timezones may
require several model and tool calls. Level 2 raises an error when the second
model response requests another tool.

Level 3 adds a second `while True` inside `Agent.handle_message()`. It repeats:

1. Call the model with the conversation and active turn.
2. Add the complete response items to the active turn.
3. If the response requests a tool, run it and add its result.
4. Repeat; stop when there is no function call.

## Run it

```sh
uv run --env-file .env series-1-agent-class/03-loop/main.py
```

Ask:

```text
📝 you › Call get_current_time separately for Tokyo, New York, and London, then summarize.

tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ { ... }
tool › get_current_time({"timezone":"America/New_York"})
tool ‹ { ... }
tool › get_current_time({"timezone":"Europe/London"})
tool ‹ { ... }

🤖 model › ...
    [4 model call(s) · 3 tool call(s) · ...]
```

The timestamps, answer, and token counts will differ. Each requested tool call
should have a result before the final answer.

## Two loops

`main()` owns the terminal session. It creates one `Agent` with a function
that prints events, reads messages, and stops at `Ctrl-D`:

```python
agent = Agent(OpenAI(), emit=print_event)

while True:
    said = input("📝 you › ").strip()
    agent.handle_message(said)
```

`Agent.handle_message()` owns one user request and operates on the agent's
client and in-memory conversation:

```python
def handle_message(self, said):
    turn_items = [{"role": "user", "content": said}]
    # Keep calling the model until it returns an answer.
```

## One active turn

The turn begins with the new user item:

```python
turn_items = [{"role": "user", "content": said}]
```

Every pass sends completed conversation items followed by everything that has
happened in this turn:

```python
response = self.client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    input=self.input_items + turn_items,
    tools=TOOLS,
    parallel_tool_calls=False,
)
```

The response items join `turn_items`. The same search from Level 2 finds the
first `function_call` item, or `None` when there is not one:

```python
tool_call = next(
    (item for item in response.output if item.type == "function_call"),
    None,
)
```

If there is no tool call, the model has answered and the loop ends:

```python
if tool_call is None:
    answer = response.output_text
    break
```

Otherwise, the unchanged `_run_tool()` method executes it and the harness adds
a matching `function_call_output`. The next iteration sees the user request,
every prior tool request, and every result:

```python
tool_result = self._run_tool(tool_call)
turn_items.append(
    {
        "type": "function_call_output",
        "call_id": tool_call.call_id,
        "output": tool_result,
    }
)
```

When the model finally returns no function call, the complete turn joins the
conversation:

```python
self.input_items.extend(turn_items)
```

Level 2 raises an error when the second response requests another tool. Level 3
lets that request start another iteration.

## Bound the loop

An unbounded agent loop may keep requesting tools. `TOOL_CALL_LIMIT` sets the
maximum number of Python tool executions in one turn:

```python
TOOL_CALL_LIMIT = 5
```

After five tools execute, the next function request is not executed. The
harness still appends a matching result:

```python
if tool_calls >= TOOL_CALL_LIMIT:
    tool_result = (
        f"ToolCallLimit: the limit of {TOOL_CALL_LIMIT} "
        "tool calls has been reached"
    )
    force_answer = True
```

`force_answer` records that the next model call must finish without another
tool. That call sets:

```python
tool_choice="none" if force_answer else "auto"
```

`tool_choice="none"` disables function calls for that request. The model
receives the `ToolCallLimit` result and must answer from the items already in
the turn. The `done` event counts five executed tool calls; the rejected sixth
request was not executed.

## Done when

1. Ask a question that needs no tool. Confirm the agent exits its inner loop
   after one model call.
2. Ask for separate time lookups in three timezones. Confirm three
   `tool`/`tool_result` pairs precede one answer.
3. Ask for separate lookups in six timezones. Confirm only five tools execute,
   the sixth result starts with `ToolCallLimit`, and the model then answers.
4. Confirm the terminal remains available for another user message after each
   completed agent loop.

## What breaks next

Run Level 3 and ask:

```text
📝 you › Use get_current_time with Mars/Olympus. If it fails, explain why.
```

`ZoneInfo` raises before the harness can append a `function_call_output`. The
model cannot inspect or explain the tool failure.

[Level 4](../04-safe-loop/LESSON.md) validates model responses, converts tool
exceptions into results, and commits only completed turns.
