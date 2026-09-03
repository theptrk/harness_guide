# Level 8 — Persist conversations

## What Level 8 adds

Level 7 keeps the conversation in `Agent.input_items`. Closing the process loses
that list. This optional level replaces the list with an append-only JSONL file.

Persistence is useful in a real harness, but it is separate from the agent loop.
The model still receives the same list of Responses API items.

Run it:

```sh
uv run --env-file .env series-1-agent-class/08-persistence/main.py --new
```

Omit `--new` to continue the most recently created conversation:

```sh
uv run --env-file .env series-1-agent-class/08-persistence/main.py
```

## The storage module

`history.py` owns the file format. Each line contains a timestamp and one API
item:

```json
{"at":"2026-08-28T12:00:00","item":{"role":"user","content":"Hello"}}
```

`get_input_items()` removes the local timestamp wrapper and returns the item
list accepted by `responses.create(input=...)`.

At startup, `Agent` either creates a file or finds the latest one:

```python
self.chat_file_path = (
    history.new_chat()
    if create_new_chat
    else history.latest_chat() or history.new_chat()
)
```

## Commit only a completed turn

`Agent.handle_message()` reads the committed conversation once:

```python
input_items = history.get_input_items(self.chat_file_path)
turn_items = [{"role": "user", "content": said}]
```

Model outputs and tool results accumulate in `turn_items`. Every model call sees
`input_items + turn_items`, so tools still work before anything is written.

Only a successfully completed turn reaches the file:

```python
history.append_items(self.chat_file_path, turn_items)
```

An interrupted, incomplete, or failed turn is not appended. Tool side effects
cannot be rolled back by this rule; a file edit or shell command may already
have happened.

## Inspect the record

After a conversation, inspect its lines:

```sh
ls -t series-1-agent-class/08-persistence/chats/
cat series-1-agent-class/08-persistence/chats/*.jsonl
```

Each function call is followed by a `function_call_output` with the same
`call_id`. Keeping every API item allows the next process to reconstruct valid
model input without inventing a second conversation format.

## Check it yourself

1. Start with `--new` and tell the agent a distinctive fact.
2. Exit with `Ctrl-D`.
3. Restart without `--new` and ask for that fact.
4. Restart with `--new` and ask again. The new conversation should not contain it.
5. Interrupt a turn with `Ctrl-C`, restart, and confirm the interrupted request
   was not added to the JSONL file.
