# Web agent plan

Two stages, teaching one thing. How to run agent work on threads without
corrupting shared state.

Lessons 1 and 2 are built in `web-single-agent/`. Lessons 3 through 9 are not.
The code in `web/` is the prototype both stages replace.

## Where this ends up

One person opens the app and starts three agents on three different tasks. Agent
A is editing files. Agent B is waiting for them to approve `git push`. Agent C is
reading a page in its own browser window. They watch A for a minute, switch to
C, then close the laptop lid and come back. B is still waiting. A and C finished
while nobody was looking.

That is the target. Getting there needs per-agent state, per-agent threads, and
event delivery that does not depend on a browser tab staying open.

Stage one builds one agent and gets the thread rules right. One agent is easier
to reason about, and every mistake in stage one is a mistake you would make
nine times over with nine agents.

## The two stages

```text
web-single-agent/       one agent, streaming, approval, one browser
web-concurrent-agents/  many agents, each with its own state and thread
```

Each folder runs on its own, the same way each folder under `series-1/` does.
`diff -r web-single-agent web-concurrent-agents` shows what concurrent agents
cost.

Lessons 1 through 5 build the first folder. Lessons 6 through 9 build the second.

## Two terms up front

Everything else gets defined in the lesson that needs it.

**Process.** `uv run --env-file .env server.py` starts one Python process. It has
one block of memory, and every thread inside it can read and write that memory.

**Thread.** A thread runs one chain of Python calls at a time. When a call waits
on a network response, a subprocess, or a person, the thread sits inside that
call until the wait ends. Python starts the process with one thread. Code makes
more with `threading.Thread` or `ThreadPoolExecutor`.

## How each lesson works

Every lesson that involves threads starts with a script the reader runs. The
script prints evidence of the bug. It does not ask the reader to open a second
tab at the right moment or click a button inside a five-second window. A
demonstration that needs good timing teaches nothing when the timing is off.

Scripts live in `demos/` in each stage folder and each runs with one command
from the repository root:

```sh
uv run web-single-agent/demos/held_event_loop.py
```

## Stage one: web-single-agent

### Lesson 1: one message, one turn

**What to build.** A `POST /api/chat` route that hands the message text to one
function in the agent package and returns the finished answer. The agent calls
the model, runs the tools the model asks for, and stops when the model answers.

No streaming yet. The response arrives all at once.

**Why this matters.** FastAPI validates the request and writes the response. The
agent package decides which tools to run. Neither one does the other's job, so a
CLI or a test can drive the same agent without FastAPI.

**Done when**

- The route passes one message to the agent package and returns the answer.
- The agent makes several model calls and file tool calls in one turn.
- Nothing in the agent package imports FastAPI.

**Built as.** `collected_turn()` in `web-single-agent/server.py`, behind
`BLOCK_EVENT_LOOP=1`. Lesson 2 replaced it as the default, and keeping it
reachable is what lets the reader measure the difference against the real agent
rather than against a sleep.

### Lesson 2: stream the turn

**The bug the reader sees.** `demos/held_event_loop.py` runs a three second
blocking call two ways and times `GET /api/ping` every 200ms throughout each.
On the event-loop thread one ping took 3013.5 ms. On a worker thread the slowest
of fifteen pings took 48.7 ms. Both turns took three seconds. The numbers are
the lesson.

The demo sleeps rather than calling a model, so it needs no API key and always
reproduces. `BLOCK_EVENT_LOOP=1` on the real server confirms it with a real
turn, which measured one ping of 4161.3 ms against a slowest of 23.7 ms.

The event loop is the code inside Uvicorn that reads requests and writes
responses. It runs on one thread. An `async def` route hands control back to it
at every `await`. A call that blocks instead of awaiting keeps that thread, so
nothing else gets served, including the SSE chunks this lesson is trying to
send.

**What to build.** The agent reports progress by calling an `emit` function the
host passes in:

```python
emit({"type": "delta", "text": "Hello"})
emit({"type": "tool", "name": "read_file", "arguments": "..."})
```

Run the turn on a separate thread. That thread puts dictionaries on a
`queue.Queue`, which is safe to hand between threads. The route reads the queue
and writes one Server-Sent Events response.

**The fix that looks like it works.** Drop the `async` keyword. FastAPI runs a
plain `def` route on a thread from its own pool, the ping times stay flat, and
the demo passes. Keep this in the lesson, because a reader will find it and
conclude `async` was the problem.

It was not. Blocking the event loop was the problem, and a threadpool thread
does solve that. What it does not give you is a thread you picked, that you can
find again, and that lives as long as the agent. Lesson 5 needs all three.

**Done when**

- Text appears in the browser before the turn ends.
- Tool calls and results arrive in order.
- `demos/held_event_loop.py` shows flat ping times during a turn.

**Built as.** `streamed_turn()` in `web-single-agent/server.py`. Taking events
off the queue with `await asyncio.to_thread(events.get)` belongs to this lesson
too. A bare `events.get()` blocks, so it would hold the event loop between
events and undo the worker thread.

### Lesson 3: approval that waits

**The bug the reader sees.** `demos/approval_deadlock.py` posts a message that
triggers a shell command, reads the stream until the approval event arrives,
then posts the decision. The decision POST never returns. The script prints
`sent decision, waiting for response...` and then nothing.

This is a deadlock, and it is worth naming. The thread holding the event loop is
waiting for a decision. The decision can only arrive over HTTP. HTTP can only be
read by the thread that is waiting.

**What to build.** The shell tool cannot call `input()`. Instead:

1. The agent thread emits an approval event carrying an `approval_id` and the
   exact command.
2. The agent thread waits on a `threading.Event` with a timeout.
3. The browser posts the decision to `/api/approvals/{approval_id}`.
4. The route records the decision and sets the event.
5. The shell tool continues, or returns a denied result.

The `approval_id` matters because `{"approved": true}` on its own does not say
what was approved. An ID ties one decision to one command, and lets the server
reject an ID it does not know, an ID already decided, and an ID past its
deadline.

The timeout matters because a person can walk away. A thread waiting forever is
a thread that never releases the agent.

**Done when**

- The browser shows the command before it runs.
- Yes runs it, no returns a denied tool result to the model.
- An unknown `approval_id` returns 404, a reused one returns 409.
- A pending approval past its deadline resolves as denied.
- `demos/approval_deadlock.py` completes instead of hanging.

### Lesson 4: two turns, one set of variables

**The bug the reader sees.** `demos/approval_mixup.py` starts two turns at once,
each asking for a shell command, then posts a single approval.

Both turns run. The prototype keeps one `threading.Event` and one `approved`
flag for the whole process:

```python
approval = {"event": threading.Event(), "approved": False}
```

Turn A clears the event and waits. Turn B clears it and waits. One click sets it
once, and both turns wake up reading the same `True`. The person approved one
command and two ran. Worse, one of them is a command they were never shown,
because the browser only displays the most recent prompt.

There is a second version of the same bug in the prototype. When an SSE stream
ends, its cleanup calls `approval["event"].set()`, which releases every waiting
turn in the process.

**What this is called.** A race condition. The result depends on the order two
threads happen to reach the same variables, and neither thread owns them. The
demo makes it repeat every run by starting both turns before either can finish.

**Why threads still help.** A reader who has heard of the GIL will ask why any
of this buys anything, since only one thread runs Python bytecode at a time.
Because these threads spend almost none of their time running bytecode. They
wait on an HTTP response from the model, on a subprocess, on Chromium in another
process, and on a person clicking yes. A thread that is waiting is not holding
the GIL.

**What to build.** Nothing yet. This lesson exists so the reader knows what
lesson 5 is fixing. Do not add a global lock here.

**Done when**

- `demos/approval_mixup.py` reliably shows one decision releasing two commands.
- The reader can say which variables were shared and which thread wrote them.

### Lesson 5: one agent owns one thread

**What breaks.** Two problems, one mechanism.

Lesson 4 showed the first one. This agent has one history file, one workspace,
one browser page, and one pending approval. Two turns touching them at once
corrupt each other.

The second only appears with the browser. Synchronous Playwright drives an event
loop created on the thread that started it, so a page can only be used from that
thread. A thread per turn opens Chromium on thread A, then the next turn lands
on thread B and touches a page belonging to A. Two turns that never overlap
still break. So does the threadpool from lesson 2, because nothing guarantees
which thread it picks.

**What to build.** One `SingleAgentWorker` owning a
`ThreadPoolExecutor(max_workers=1)` that lives until shutdown.

```text
Python process
|
+- main thread
|  `- Uvicorn event loop
|
`- agent worker thread
   |- turn 1
   |- turn 2
   `- turn 3
```

Every turn and every Playwright call goes to that one thread. `max_workers=1`
also means a second turn cannot start while the first runs, so the worker
rejects it with 409 instead of queueing behind it.

**One turn at a time is permanent.** This is not a limit to apologize for in the
UI and remove later. In the finished multi-agent app, each agent still runs one
turn at a time, because its turns share its history, its workspace, and its
browser page. Stage two removes the limit that spans the whole process, not this
one.

**Done when**

- `demos/thread_identity.py` prints the same thread name for turn 1 and turn 2,
  and the same name again for browser calls inside both.
- The browser page survives across turns.
- A second turn gets 409 while the first runs.
- Shutdown closes Chromium and the executor.

## Stage two: web-concurrent-agents

### Lesson 6: give every resource an owner

**What breaks.** Running two agents by starting two `SingleAgentWorker`s does
nothing useful while the history path, the workspace root, the browser handle,
and the approval state are module globals. Two threads, one set of variables,
which is lesson 4 again at a larger size.

**What to build.** An `AgentRuntime` that owns one history store, one workspace,
one browser session, one tool table bound to that workspace and browser, one
worker thread, and its own pending approvals. Module state becomes constructor
arguments:

```text
HistoryStore(path)
Workspace(root)
BrowserSession()
AgentRuntime(history, workspace, browser)
```

Two runtimes still cannot run at the same time after this lesson. That comes
next. This lesson only moves state out of module globals.

**Done when**

- Two runtimes write `notes.txt` and get two different files.
- Two runtimes keep separate histories.
- Two runtimes own separate Chromium instances.
- Closing one runtime leaves the other working.

### Lesson 7: work that survives a closed tab

**The bug the reader sees.** `demos/reconnect.py` starts a turn, drops the SSE
connection mid-turn, reconnects, and prints what it got. Events emitted during
the gap are gone. If the turn was waiting for approval, the prototype's stream
cleanup denied it on the way out.

The person who spawns three agents will do this constantly. Switching to another
agent, closing a tab, sleeping the laptop. If a dropped socket kills a turn,
parallel agents are not usable.

**What to build.** Move the event queue out of the request handler. Each
`AgentRuntime` keeps a numbered, bounded log of the events it emitted, and the
SSE route reads from it:

```text
GET /api/agents/{agent_id}/events?after=142
```

A reconnect asks for everything after the last sequence number it saw. A turn
keeps running with nobody reading.

Pending approvals belong to the runtime, not to the connection. A dropped
connection does not deny them. Only a decision or the deadline from lesson 3
resolves them.

**Done when**

- `demos/reconnect.py` loses no events across a disconnect.
- A turn started, then abandoned, finishes and its events are readable after.
- A pending approval survives a disconnect and is still answerable.
- The event log is bounded and drops oldest first.

### Lesson 8: many agents at once

**What to build.** An `AgentManager` holding a map from `agent_id` to
`AgentRuntime`, and routes that name the agent:

```text
POST   /api/agents
GET    /api/agents
GET    /api/agents/{agent_id}
POST   /api/agents/{agent_id}/turns
GET    /api/agents/{agent_id}/events
POST   /api/agents/{agent_id}/approvals/{approval_id}
DELETE /api/agents/{agent_id}
```

```text
Python process
|
+- Uvicorn event loop
|
+- agent A worker thread
+- agent B worker thread
`- agent C worker thread
```

Different agents run at the same time. One agent's turns stay sequential, for
the reasons in lesson 5.

The UI needs a list of agents with per-agent status, and a way to switch between
transcripts. An agent that is running while you look at a different one is the
whole point, so its row has to show that it is running, and its unread events
have to be there when you switch back.

**Why the limit moves.** The prototype's global lock stopped the entire process
because all the state was global. Once each agent owns its state, the only thing
that has to serialize is one agent's own turns. Agent A has no reason to wait
for agent B.

**Done when**

- Two agents stream turns at the same time.
- One agent cannot start two overlapping turns.
- An approval ID from agent A does nothing to agent B.
- The agent list shows which agents are running.
- Switching agents shows that agent's full transcript.
- Deleting an agent closes its browser and stops its worker.

### Lesson 9: limits and cleanup

**What breaks.** Ten agents means ten Chromium instances. Chromium costs far
more memory than the thread driving it, so the ceiling is browsers, not threads.
Nothing so far stops a reader from creating agents until the machine swaps.

**What to build**

- A cap on active runtimes, with a clear error at the cap instead of a slow
  machine.
- A cap on queued turns per runtime.
- Lazy browser start, so an agent that never browses never launches Chromium.
- Idle browser shutdown, keeping the agent alive.
- Idle runtime shutdown, keeping its history on disk.

An agent stored on disk needs no thread. Loading it on demand is what makes the
cap on active runtimes reasonable.

**Done when**

- Creating one agent past the cap returns a clear error.
- An agent that never browses starts no Chromium process.
- An idle agent releases its browser and worker.
- A resumed agent reads its history from disk.
- Idle cleanup never touches a running agent.

## Code boundaries, both stages

`server.py` holds routes, request validation, agent events turned into SSE
frames, approval POSTs turned into decisions, and static files.

The agent package holds the model and tool loop, the tools, history and
workspace access, browser ownership, and worker and runtime lifecycle.

The agent loop takes `emit` and `approve` as arguments. It does not import
FastAPI and does not know its events end up as SSE.

## Tests both stages share

- A normal answer streams more than one text event.
- Tool calls and their results arrive in order.
- Approval runs or denies the exact command that was shown.
- A dropped SSE client loses no events and denies no approvals.
- Browser calls for one agent all report the same thread.
- History, workspace, browser, and approvals are isolated by `agent_id`.
- Shutdown closes every Chromium instance and every executor.

## Not in this plan

No durable job store, no multiple Uvicorn processes, no distributed queue, no
recovery after the process dies, no multi-user authorization.

The event log and approval events live in one process's memory. Two Uvicorn
workers would each get their own `AgentManager` and neither would see the
other's agents. Surviving a process restart needs the event log and pending
approvals on disk, which is a separate piece of work.

Surviving a closed browser tab is in scope. That is lesson 7.

## Cleanup before lesson 1

`web/agent/loop.py` defines `get_client`, `current_chat`, `new_chat`,
`snapshot`, `shutdown`, and `handle_message` twice, and declares `_client`
twice. The second definitions win. Delete the duplicates when copying this code
into `web-single-agent/`.
