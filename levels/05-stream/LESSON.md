# Level 5 — Stream it

## What broke

Level 4 waits for each model response to finish before it prints anything from that response. A slow model call leaves the terminal unchanged until the full message or function call arrives.

Level 5 requests a stream. Text arrives in small deltas and is printed immediately:

```text
[model call 2 started]

model › It’s 4:57 PM on August 18, 2026 in Tokyo.
```

The completed line looks ordinary. While it is generated, its fragments appear one at a time.

---

## Run it

```sh
uv run --env-file .env levels/05-stream/main.py --new
```

Ask:

```text
you › What time is it in Tokyo?
```

One run produced:

```text
[model call 1 started]

tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {"timezone": "Asia/Tokyo", "datetime": "2026-08-18T16:57:17+09:00"}

[model call 2 started]

model › It’s 4:57 PM on August 18, 2026 in Tokyo.
    [2 model call(s) · 1 tool call(s) · 400 in + 45 out]
```

The first response contains a function call, so it has no answer text to stream. The second response emits the final answer as text deltas.

---

## A streamed response is a sequence of events

Level 4 calls:

```python
response = client.responses.create(...)
```

Level 5 adds `stream=True`. Instead of returning one `Response`, the call returns an iterator of events. Each event has a `type` property that identifies the data it contains.

A text event contains a fragment at `event.delta`:

```python
event.type == "response.output_text.delta"
event.delta == "It"
```

A final stream event contains the complete response at `event.response`:

```python
event.type == "response.completed"
response = event.response
```

This level handles these values of `event.type`:

- `response.output_text.delta` — another fragment of answer text.
- `response.refusal.delta` — another fragment of refusal text.
- `response.completed` — the final event containing the completed `Response` at `event.response`.
- `response.incomplete` and `response.failed` — final events containing non-completed responses at `event.response`.

A delta is a string fragment, not necessarily one token. This run wrote `"It"`, `"’s"`, `" **"`, and `"4"` as four separate events.

The loop branches on `event.type`. It records and prints each delta, or saves the complete response from the final event:

```python
with client.responses.create(
    # ...
    stream=True,
) as stream:
    for event in stream:
        if event.type in {
            "response.output_text.delta",
            "response.refusal.delta",
        }:
            history.append_event(
                chat_file_path,
                turn_id,
                "text_delta",
                model_call=model_call,
                delta=event.delta,
                start=not text_started,
            )
            print(event.delta, end="", flush=True)
        elif event.type in {
            "response.completed",
            "response.incomplete",
            "response.failed",
        }:
            response = event.response
```

`flush=True` makes the fragment visible immediately instead of waiting for Python's output buffer.

---

## The JSONL file stores display events and API items

Every event is appended to the current chat file in `levels/05-stream/chats/`. For assistant text, that file stores the same text in two forms.

For a completed turn, `history.get_input_items()` applies this filter:

```text
JSONL file:
- text_delta        → not sent to the model
- model_started     → not sent to the model
- turn_completed    → not sent to the model
- api_item          → sent to the model
```

An `api_item` is sent only when `include_in_input` is `true` and its turn completed. The other entries exist for display and recovery.

While text is streaming, each fragment is stored as a `text_delta` display event. These are the relevant fields from one line:

```json
{
  "kind": "text_delta",
  "delta": " Tokyo",
  "start": false
}
```

After the final stream event arrives, the complete message is stored in the same file as one `api_item`. These are the relevant fields from that line:

```json
{
  "kind": "api_item",
  "item": {
    "type": "message",
    "role": "assistant",
    "content": [
      {
        "type": "output_text",
        "text": "It’s 4:57 PM on August 18, 2026 in Tokyo."
      }
    ]
  },
  "include_in_input": true
}
```

The answer text is duplicated deliberately:

- `view.py` reads the `text_delta` events to reconstruct the displayed progress. It ignores the completed assistant `api_item`.
- `history.get_input_items()` reads the completed `api_item` to build the next model request. It ignores every `text_delta`.

Only the completed `api_item` is sent to the model. Reconstructing that item from deltas would lose fields supplied by the API, including the message ID, status, and phase.

Function calls and function outputs have no displayed text deltas in this program. They are stored once as API items, and `view.py` renders those items directly.

---

## A turn is replayable only after it completes

Every user request gets a local `turn_id`. All API items, deltas, and status events produced for that request carry the same ID.

The last event of a successful turn is:

```json
{
  "kind": "turn_completed",
  "turn_id": "...",
  "model_calls": 2,
  "tool_calls": 1,
  "input_tokens": 400,
  "output_tokens": 45
}
```

`get_input_items()` includes API items from completed turns. It also accepts the active turn's ID while the agent loop is running, because each tool result must be available to the next model call before the turn is finished.

If the process is interrupted or fails, there is no `turn_completed` event. Its partial deltas remain available for inspection, but none of that turn's API items are sent on the next run.

This also handles a process that stops before it can append `turn_interrupted`: the missing completion event is enough to exclude the turn.

---

## Watch and replay the chat file

`main.py` prints the chat filename when it starts:

```text
[2026-08-18-005715.jsonl · 0 replayable items so far]
```

In another terminal, use that name with `view.py`:

```sh
uv run levels/05-stream/view.py --follow \
  levels/05-stream/chats/2026-08-18-005715.jsonl
```

`--follow` reads existing events, waits for appended lines, and renders each new event. Enter a request in the first terminal. The second terminal should show the same user message, model-call status, tool calls, text, and usage totals.

After the run, omit `--follow` to replay the existing chat file and exit:

```sh
uv run levels/05-stream/view.py \
  levels/05-stream/chats/2026-08-18-005715.jsonl
```

The viewer does not call the model or execute tools. Its only input is the JSONL file.

---

## Interrupt a turn

Press `Ctrl-C` while a model response is streaming. The harness appends:

```json
{"kind": "turn_interrupted", "turn_id": "..."}
```

Any deltas received before the interruption remain in the file. `view.py` replays them followed by `[turn interrupted]`. Restarting `main.py` excludes every API item from that unfinished turn.

The SDK can retry some failures before a stream begins. Once output has arrived, this harness does not repeat the model call: doing so could duplicate visible text or tool work.

---

## Done when

1. Watch answer text appear before the response is complete.
2. Follow the chat file from a second terminal and see the same progress.
3. Replay the file after the process exits without calling the API.
4. Interrupt an active response, then restart and confirm that the interrupted turn is not counted as replayable input.

---

## What breaks next

The agent can report its progress, but it still cannot read or change a file.

[Level 6](../06-files/LESSON.md) adds file tools confined to an agent workspace.
