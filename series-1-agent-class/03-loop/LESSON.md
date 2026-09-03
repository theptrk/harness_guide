# Level 3 — Build the agent loop

Level 2 handles one tool request with a fixed sequence. A request for several
timezones may require several model and tool calls. Level 3 puts the same model
call, response inspection, and tool execution inside `while True`:

1. Call the model with the conversation and active turn.
2. Add the complete response items to the active turn.
3. If the response requests a tool, run it and add its result.
4. Repeat; stop when there is no function call.

```sh
uv run --env-file .env series-1-agent-class/03-loop/main.py
```

Try asking for the current time in Tokyo, New York, and London.

## Two loops

`main()` owns the terminal session. It creates one `Agent`, reads messages, and
stops at `Ctrl-D`:

```python
agent = Agent()

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

That is the central new mechanism: Level 2 raises an error when the second
model response requests another tool; Level 3 lets that request start another
iteration.

The loop allows up to five tool executions. If the model requests a sixth, the
harness returns a `ToolCallLimit` result and disables tools for the final model
call. This keeps a mistaken model from looping forever while still letting it
explain why it stopped. Level 3 still assumes working tools; later levels harden
tool execution. [Level 4](../04-stream/LESSON.md) first streams the model's
answer.
