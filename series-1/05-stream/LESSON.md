# Level 5 — Stream it

## What broke

Level 4 prints nothing from a model call until the complete response arrives. Ask for several paragraphs and the terminal stays unchanged while the model generates all of them.

Level 5 prints each text fragment as the API sends it. After the stream ends, it stores the complete response item for the next model call.

Level 4 can exclude an incomplete output item, but it cannot exclude every API item from that failed request. Level 5 gives each request a `turn_id` and includes its API items in later model input only after the turn completes.

The CLI loop in `main()` still reads one terminal message and passes it to `run_turn()`. This level changes how `run_turn()` receives and records the model response.

---

## Run it

Start the agent:

```sh
uv run --env-file .env series-1/05-stream/main.py --new
```

It prints the new chat filename and waits:

```text
[2026-08-18-122432-278577.jsonl · 0 input items so far]
```

Ask for enough text to see it arrive:

```text
📝 you › Explain in six short bullet points how UTC offsets work.
```

One run returned:

```text
[model call 1 started]

🤖 model › - UTC is the global reference time, with an offset of **+00:00**.
- An offset tells you how far local time differs from UTC.
- Positive offsets are ahead of UTC, such as **UTC+02:00**.
- Negative offsets are behind UTC, such as **UTC−05:00**.
- Add the offset to UTC to calculate local time.
- Offsets may change because of daylight saving time or regional rules.
    [1 model call(s) · 0 tool call(s) · 172 in + 96 out]
```

This transcript cannot show timing. During the run, the terminal displays each fragment before the complete response exists.

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
event.delta == "-"
```

A final stream event contains the complete response at `event.response`:

```python
event.type == "response.completed"
final_response = event.response
```

This level handles these values of `event.type`:

- `response.output_text.delta` — another fragment of answer text.
- `response.refusal.delta` — another fragment of refusal text.
- `response.completed` — the final event containing the completed `Response` at `event.response`.
- `response.incomplete` and `response.failed` — final events containing non-completed responses at `event.response`.

The API emits other event types too, including function-call argument deltas. This program does not display those arguments incrementally. It waits for the final event and reads the complete function call from `event.response.output`.

A text delta is a string fragment, not necessarily one token. The run above wrote `"-"`, `" UTC"`, `" is"`, and `" the"` as four separate events.

The loop branches on `event.type`. It prints each text delta and keeps the complete response from the final event:

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
            print(event.delta, end="", flush=True)
        elif event.type in {
            "response.completed",
            "response.incomplete",
            "response.failed",
        }:
            final_response = event.response
```

`flush=True` makes the fragment visible immediately instead of waiting for Python's output buffer.

If a completed response contains answer text but the stream emitted no text deltas, `run_turn()` prints the complete answer after the stream closes.

---

## Deltas are display, not conversation input

Text deltas are fragments of one response. They are printed and discarded. Appending each fragment as an assistant message would give the next model call a conversation that never existed.

The terminal stream event contains the complete `Response`. After the stream closes, `save_response()` stores each complete output item as one `api_item`:

```json
{
  "kind": "api_item",
  "item": {
    "type": "message",
    "role": "assistant",
    "content": [
      {
        "type": "output_text",
        "text": "- UTC is the global reference time..."
      }
    ]
  }
}
```

The next model call receives that complete item, not the fragments that appeared in the terminal. `history.get_input_items()` removes the event wrapper only after checking the event type and turn:

```python
if event["kind"] != "api_item":
    continue
if event["turn_id"] in completed_turns or event["turn_id"] == active_turn_id:
    items.append(event["item"])
```

---

## Only completed turns become later API input

Every user request gets a local `turn_id`. All API items and status events produced for that request carry the same ID.

Level 4 excluded incomplete model output, but earlier API items from the same failed request could still enter later model input. Level 5 uses the turn ID to include or exclude the entire request.

The last event of a successful turn is:

```json
{
  "kind": "turn_completed",
  "turn_id": "...",
  "model_calls": 1,
  "tool_calls": 0,
  "input_tokens": 172,
  "output_tokens": 96
}
```

`get_input_items()` includes API items from completed turns. It also accepts the active turn's ID while the agent loop is running, because each tool result must be available to the next model call before the turn is finished.

If the process is interrupted or fails, there is no `turn_completed` event. None of that turn's API items are sent on the next run.

If interruption happens before a terminal response event, the log contains `model_started` but no `model_call_finished`. A later `turn_interrupted` event marks the turn as interrupted.

This also handles a process that stops before it can append `turn_interrupted`: the missing completion event is enough to exclude the turn.

To see that behavior, ask for a response long enough to interrupt:

```text
📝 you › Write the numbers 1 through 200, one per line.
```

Press `Ctrl-C` after some numbers appear. The harness appends:

```json
{"kind": "turn_interrupted", "turn_id": "..."}
```

The fragments printed before the interruption remain only in that terminal. Restarting `main.py` excludes every API item from the unfinished turn.

The SDK can retry some failures before a stream begins. Once output has arrived, this harness does not repeat the model call: doing so could duplicate visible text or tool work.

---

## Done when

1. Start a new conversation:

   ```sh
   uv run --env-file .env series-1/05-stream/main.py --new
   ```

2. Enter `Explain in six short bullet points how UTC offsets work.`
3. Confirm that answer text appears before the usage line.
4. Press `Ctrl-D`, then start another new conversation:

   ```sh
   uv run --env-file .env series-1/05-stream/main.py --new
   ```

5. Enter `Write the numbers 1 through 200, one per line.` Press `Ctrl-C` after several numbers appear.
6. Restart without `--new`:

   ```sh
   uv run --env-file .env series-1/05-stream/main.py
   ```

7. Confirm that the startup header reports `0 input items so far`. None of the interrupted turn is included in later model input.

---

## What breaks next

Ask it to create a file:

````text
📝 you › Create profile.md. Record that my name is Patrick and my favorite fruit is strawberries.

🤖 model › I can’t create files directly here, but `profile.md` should contain:

```markdown
# Profile

- Name: Patrick
- Favorite fruit: Strawberries
```
````

That is the complete response from one run. No `profile.md` file was created. You still have to copy the text into an editor.

[Level 6](../06-files/LESSON.md) adds confined file tools.
