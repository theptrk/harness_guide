# Level 1 — Hold a conversation

Level 0 sends one message and exits. A model does not remember that call. Level
1 keeps the API items in a Python list and sends the full list on every call.

Run it:

```sh
uv run --env-file .env series-1-agent-class/01-conversation/main.py
```

Try:

```text
📝 you › My name is Ada.
📝 you › What is my name?
```

The second answer can use the name because the harness sends both exchanges to
the model. Nothing is loaded from or written to disk. Exiting the process ends
the conversation.

## The item list

`Agent` owns the conversation:

```python
self.input_items = []
```

For a new message, it creates one user item:

```python
user_item = {"role": "user", "content": said}
```

The API receives the completed items followed by the new user item:

```python
response = self.client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    input=self.input_items + [user_item],
    reasoning={"effort": "none"},
)
```

The `+` creates a temporary list. The new request is not committed to the
conversation until the call succeeds.

## Retain the completed exchange

After a successful response, the agent adds the request and every output item:

```python
self.input_items.append(user_item)
self.input_items.extend(
    item.model_dump(mode="json", exclude_none=True)
    for item in response.output
)
```

`response.output` contains SDK objects. `model_dump()` turns each object into a
dictionary that can be sent back through `input` on the next call.

The code retains API items rather than rebuilding a transcript from displayed
text. Later levels add function calls and function results to this same list.

After the commit, `handle_message()` emits the same three events as Level 0:
`response`, `text`, and `done`. `Terminal` prints the answer and the token
counts. With `--raw` it also prints the output items from the `response`
event, and with `--raw_model_dump` the whole object. The agent has no
`print()` in it.

## Failure behavior

If the API call fails or is interrupted, the user item has not been appended.
The next message therefore cannot include a request that never received a
completed response. The exception reaches `main()`, which prints `call failed`
and waits for the next line.

## Context grows

Every new call sends the whole list. Input token usage grows with the
conversation. A production harness eventually needs a context-selection policy,
but that is separate from learning the basic conversation mechanism.

## Check it yourself

1. Tell the agent two facts, then ask it to repeat them.
2. Exit and start the program again. Confirm that it no longer knows them.
3. Temporarily print `self.input_items` after a successful call and inspect the
   user and assistant items.

Next, [Level 2](../02-tool/LESSON.md) adds one function tool.
