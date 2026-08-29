# Level 3 — Build the agent loop

Level 2 handles one tool request. A request for several timezones may require
several model and tool calls. Level 3 repeats until the model answers:

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

`run_turn()` owns one user request. `Agent` supplies the client and its
in-memory conversation:

```python
def handle_message(self, said):
    run_turn(self.client, self.input_items, said)
```

## One active turn

The turn begins with the new user item:

```python
turn_items = [{"role": "user", "content": said}]
```

Every pass sends completed conversation items followed by everything that has
happened in this turn:

```python
response = client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    input=input_items + turn_items,
    tools=TOOLS,
    parallel_tool_calls=False,
)
```

The response items join `turn_items`. If one is a `function_call`, the harness
runs it and appends a matching `function_call_output`. The next pass therefore
sees the user request, every tool request, and every result.

When the model finally returns no function call, the complete turn joins the
conversation:

```python
input_items.extend(turn_items)
```

The number of tool calls is not decided in advance. Each response determines
whether another pass is needed.

The loop is still unbounded and assumes valid, complete responses and working
tools. [Level 4](../04-harden/LESSON.md) handles those failures.
