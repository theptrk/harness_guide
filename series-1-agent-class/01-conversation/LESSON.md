# Level 1 — Hold a conversation

## What broke

Level 0 sends one question and exits. A second call does not include the first
question or answer, so the model cannot refer to that exchange.

Level 1 keeps one process running. The agent holds completed Responses API
items in memory and sends them with each new user item.

## Run it

```sh
uv run --env-file .env series-1-agent-class/01-conversation/main.py
```

Enter two messages in the same process:

```text
📝 you › My name is Ada.
🤖 model › Nice to meet you, Ada.

📝 you › What is my name?
🤖 model › Your name is Ada.
```

The wording may differ. The second answer can use the name because its request
contains the first user item and the model's first output items.

## Keep the API items

`Agent` owns the conversation:

```python
self.input_items = []
```

Each message starts as a Responses API user item:

```python
user_item = {"role": "user", "content": said}
```

The request sends completed items followed by that new item:

```python
response = self.client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    input=self.input_items + [user_item],
    reasoning={"effort": "none"},
)
```

After the call succeeds, the agent retains the user item and every item in
`response.output`:

```python
self.input_items.append(user_item)
self.input_items.extend(
    item.model_dump(mode="json", exclude_none=True)
    for item in response.output
)
```

`response.output` contains SDK objects. `model_dump()` turns each object into a
dictionary accepted by `input` on the next call. The agent retains the API
items, including fields such as message `phase`; it does not rebuild history
from `response.output_text` or terminal text.

The `+` in `self.input_items + [user_item]` creates a temporary request list.
If the API call fails, the user item is not committed. A successful call
commits the completed exchange.

`main()` adds the terminal `while True` loop. It prints the returned answer and
usage. `Agent` still does not read input or print output.

Every request sends the full in-memory item list, so input token usage grows
with the conversation.

## Done when

1. Tell the agent two facts in one process.
2. Ask it to repeat both facts.
3. Run with `--raw` and confirm that each response contains API output items.
4. Confirm that later input-token counts are larger as the item list grows.
5. Exit, restart, and confirm that the new process does not know the facts.

## What breaks next

Ask for the exact current time in Tokyo. The model has no live clock and the
harness cannot run a function to get one.

[Level 2](../02-tool/LESSON.md) adds one function tool.
