# Level 5 — Stream it

## What broke

Level 3 prints nothing from a model call until the complete response arrives. Ask for several paragraphs and the terminal stays unchanged while the model generates all of them.

Level 5 prints each text fragment as the API sends it. After the stream ends, it retains the complete response item for the next model call.

Level 4's protocol safety remains in force: responses are validated before tools run, tool failures become tool results, tool execution is bounded, and only completed turns reach the in-memory conversation.

The CLI loop in `main()` still passes each terminal message to
`agent.handle_message()`. This level changes how that method receives and records
the model response.

---

## Run it

Start the agent:

```sh
uv run --env-file .env series-1-agent-class/05-stream/main.py
```

It waits for a message.

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

Level 3 calls:

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

The API emits other event types too, including function-call argument deltas. This program does not display those arguments incrementally. It waits for the final event and reads the complete function call from `event.response.output`.

A text delta is a string fragment, not necessarily one token. The run above wrote `"-"`, `" UTC"`, `" is"`, and `" the"` as four separate events.

The loop branches on `event.type`. It emits each text delta as a `text` event and keeps the complete response from the final event:

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
            self.emit({"type": "text", "text": event.delta})
        elif event.type == "response.completed":
            final_response = event.response
```

If a response contains answer text but the stream emitted no text deltas, `handle_message()` emits the complete answer as one `text` event after the stream closes.

---

## The terminal remembers whether a line is open

Level 3 printed events with one function, `print_event()`. Each event was a
whole line. A `text` event is now a fragment. The terminal has to print the
`🤖 model ›` prefix before the first fragment and a newline after the last, so
`print_event()` becomes a class with one attribute:

```python
class Terminal:
    def __init__(self):
        self.text_open = False

    def emit(self, event):
        if event["type"] == "text":
            if not self.text_open:
                print("\n🤖 model › ", end="", flush=True)
                self.text_open = True
            print(event["text"], end="", flush=True)
            return
        if self.text_open:
            print()
            self.text_open = False
        # model_started, tool, tool_result, done
```

`flush=True` makes each fragment visible immediately instead of waiting for
Python's output buffer.

`main()` passes `terminal.emit` to the agent. The agent emits the same `text`
event for a fragment and for a complete answer. It does not know that a
terminal needs a prefix and a newline.

---

## Deltas are display, not conversation input

Text deltas are fragments of one response. They are printed and discarded. Appending each fragment as an assistant message would give the next model call a conversation that never existed.

The terminal stream event contains the complete `Response`. After the stream closes, each output item joins `turn_items`:

```python
turn_items.extend(
    item.model_dump(mode="json", exclude_none=True)
    for item in response.output
)
```

The next model call receives that complete item, not the fragments that appeared in the terminal:

```python
input=self.input_items + turn_items
```

---

## Interrupted turns never reach the in-memory conversation

`handle_message()` starts the active turn with a local list:

```python
turn_items = [{"role": "user", "content": said}]
```

`self.input_items` is the completed conversation. `turn_items` exists only in this call to `handle_message()`. Each model pass receives both lists, so tool requests and results remain available inside the agent loop before the turn is committed.

After a final answer, one call commits the turn:

```python
self.input_items.extend(turn_items)
```

To see that behavior, ask for a response long enough to interrupt:

```text
📝 you › Write the numbers 1 through 200, one per line.
```

Press `Ctrl-C` after some numbers appear. The fragments remain only in that terminal. `self.input_items.extend()` is never reached, so the active conversation remains unchanged.

The SDK can retry some failures before a stream begins. Once output has arrived, this harness does not repeat the model call: doing so could duplicate visible text or tool work.

---

## Done when

1. Start a new conversation:

   ```sh
   uv run --env-file .env series-1-agent-class/05-stream/main.py
   ```

2. Enter `Explain in six short bullet points how UTC offsets work.`
3. Confirm that answer text appears before the usage line.
4. Enter `Write the numbers 1 through 200, one per line.` Press `Ctrl-C` after several numbers appear.
5. Confirm in the code that `self.input_items.extend(turn_items)` is reached only after a final answer. None of the interrupted turn is included in later model input.

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
