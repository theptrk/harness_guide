# Web stage 1 — One local agent

Series 1 ends with a program you talk to in a terminal. `input()` reads a
message, `print()` shows the answer, and one person waits at the keyboard.

This stage runs the same agent loop behind HTTP. That change is not cosmetic. A
web server handles more than one request at a time, and the agent blocks for
seconds at a stretch, so the two cannot share a thread.

Lessons 1 and 2 are built. Lessons 3 through 5 add shell approval, a race
condition worth seeing, and a worker thread the agent owns. This folder has the
time tool and the file tools only.

---

## Run it

```sh
uv run --env-file .env web-single-agent/server.py
```

Open `http://127.0.0.1:8765` and ask for something that needs a tool:

```text
Create notes.txt containing the single word strawberry, then confirm.
```

Text appears while the turn is still running. The tool call and its result
appear as cards between the messages.

---

## Lesson 1 — FastAPI takes the message, the agent runs the turn

`server.py` holds every HTTP concern. `agent/` holds the model loop, the tools,
the workspace, and the history file. The route validates the request and hands
one string across:

```python
@app.post("/api/chat")
async def post_chat(request: ChatRequest) -> StreamingResponse:
    message = request.message.strip()
    ...
```

`agent.handle_message()` decides everything after that. It calls the model, runs
whatever tool the model asked for, appends to history, and stops when the model
answers instead of calling another tool.

The route never inspects a tool call. `agent/loop.py` never builds a response.
Nothing under `agent/` imports FastAPI, which is what lets the same loop run
from a script or a test.

`ChatRequest` is where a malformed request dies:

```python
class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
```

An empty body or a missing `message` gets a 422 from FastAPI before the agent
runs. A message of only spaces gets a 400 from the route.

### The transcript can show what the model cannot see

Level 5 gave every turn an ID and included its items in later model input only
after `turn_completed` was written. In the terminal that rule was invisible. You
saw the error, then you kept typing.

A web page rebuilds the transcript from the history file on every reload, so the
rule becomes visible. `GET /api/chat` returns rows, and each one reports whether
the model will see it again:

```python
completed_turns = {
    event["turn_id"] for event in events if event["kind"] == "turn_completed"
}
...
"in_model_input": event["turn_id"] in completed_turns,
```

Two of the turns below failed with a connection error. Their messages are still
in the file, still on the page, and marked:

```text
Create notes.txt containing the single word strawberry, then confirm.
  excluded from model input
Connection error.
```

Hiding those rows would be worse. The person typed that message, so removing it
makes the page lie about what happened. Showing it without the mark is also
worse, because they would follow up with "do it now" and the model would have no
record of what "it" was.

`turn_failed` events were already in the history file. Reading them is what lets
the transcript say which turns reached the model.

---

## Lesson 2 — Move the turn off the event-loop thread

### What broke

Uvicorn runs FastAPI on one thread. An event loop on that thread reads requests
and writes responses. An `async def` route hands control back to the loop every
time it reaches `await`, which is how one thread serves many requests.

`agent.handle_message()` never awaits. It calls the OpenAI client and waits for
a network response, so the thread stays inside it. Call it straight from an
`async def` route and the event loop is gone for the length of the turn.

Run the demo:

```sh
uv run web-single-agent/demos/held_event_loop.py
```

It starts a small server with two routes that sleep for three seconds, one on
the event-loop thread and one on a worker thread, and times `GET /api/ping`
throughout each. One run printed:

```text
The turn runs on the event-loop thread.
  route  GET /on-event-loop
  ping        2.4 ms
  ping        3.0 ms
  ping     3013.5 ms   <- waited for the whole turn
  ping        1.7 ms
  slowest ping 3013.5 ms, turn took 3.0 s

The turn runs on a worker thread.
  route  GET /on-worker-thread
  ping        1.9 ms
  ping        2.7 ms
  ping        1.7 ms
  ...
  slowest ping 48.7 ms, turn took 3.0 s
```

Both turns took three seconds. Only one of them stopped answering everything
else.

The demo sleeps instead of calling a model because the event loop cannot tell
the difference. `server.py` keeps the same two routes behind an environment
variable, so you can measure the real agent:

```sh
BLOCK_EVENT_LOOP=1 uv run --env-file .env web-single-agent/server.py
```

Sending `Read notes.txt and tell me the word.` to that server and timing
`/api/ping` during the turn gave one ping of 4161.3 ms. The same message
against the normal server gave twenty pings, the slowest 23.7 ms.

### The agent reports events instead of printing

Series 1 called `print()`. This stage passes in a function:

```python
Emit = Callable[[dict], None]

def handle_message(said: str, *, emit: Emit) -> None:
```

The loop calls it with dictionaries as the turn proceeds:

```python
emit({"type": "delta", "text": event.delta})
emit({"type": "tool", "name": tool_call.name, "arguments": tool_call.arguments})
emit({"type": "tool_result", "name": tool_call.name, "output": tool_result})
```

The agent does not know what happens to them. `server.py` decides that they
become Server-Sent Events frames.

### The worker thread and the queue

`streamed_turn()` starts a thread for the turn and reads its events from a
`queue.Queue`, which is safe to use from two threads at once:

```python
events: queue.Queue[dict | None] = queue.Queue()

def run() -> None:
    try:
        agent.handle_message(message, emit=events.put)
    finally:
        events.put(None)

threading.Thread(target=run, name="agent-turn", daemon=True).start()

while True:
    payload = await asyncio.to_thread(events.get)
    if payload is None:
        break
    yield sse_frame(payload)
```

`events.put` is the `emit` function. `None` marks the end of the turn.

`await asyncio.to_thread(events.get)` matters as much as the worker thread does.
`events.get()` blocks until an event arrives, so calling it directly would put
the event loop back where it started. `asyncio.to_thread` moves that wait
somewhere else and awaits the result, which frees the loop between events.

### The fix that looks like it works

Delete the `async` keyword and the demo passes. FastAPI runs a plain `def` route
on a thread from its own pool, so the blocking call never touches the event
loop.

`async` was not the problem, and the threadpool is a real fix for this lesson.
What it does not give you is a thread you chose, that you can find again, and
that lives as long as the agent. Lesson 5 needs all three, because a Playwright
browser page can only be used from the thread that opened it.

### No lock yet

Two messages sent at once will both start a turn, and both turns will write to
the same history file. That is deliberate. Lesson 4 measures the damage before
lesson 5 fixes it.

---

## Done when

1. Start the server:

   ```sh
   uv run --env-file .env web-single-agent/server.py
   ```

2. Send `Create notes.txt containing the single word strawberry, then confirm.`
3. Confirm that answer text appears before the turn ends, and that
   `write_file` and its result appear as cards.
4. Confirm the file exists:

   ```sh
   cat web-single-agent/agent_workspace/notes.txt
   ```

5. Reload the page. The transcript comes back from
   `web-single-agent/chats/*.jsonl` through `GET /api/chat`.
6. Break a turn on purpose to see an excluded one. Turn off your network, send a
   message, wait for the error, turn it back on and reload. That message is
   faded and labelled `excluded from model input`.
7. Run `uv run web-single-agent/demos/held_event_loop.py` and confirm one ping
   near three seconds in the first case and none in the second.
8. Confirm no file under `web-single-agent/agent/` imports FastAPI:

   ```sh
   rg -l fastapi web-single-agent/agent
   ```

---

## What breaks next

Ask it to run a command:

```text
Run git status in the workspace.
```

There is no shell tool here, so the model answers with instructions instead of
output. Adding one raises a question the terminal answered with `input()`: how
does a person see the exact command and say yes before it runs?

Lesson 3 adds shell approval, and finds a deadlock on the way.
