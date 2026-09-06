# Series 2 ideas

Things the class-based Series 1 leaves out on purpose. They surfaced while
making `Agent` own its state (PR #1). None of them matter while one person runs
one agent in a terminal, so none are in that series. Three already have a home
in `web-plan.md`. One does not.

## Already planned

**One turn at a time per agent.** `handle_message` is not reentrant. Two turns
on one agent interleave writes to its chat file and share its browser page.
The terminal never hits this because `input()` blocks until the turn ends.
`web-plan.md` lesson 4 shows the bug. Lesson 5 fixes it with one worker thread
per agent, `ThreadPoolExecutor(max_workers=1)`, and returns 409 to a second
turn.

**Playwright is bound to one thread.** `browser_tools._playwright()` keeps one
module-level driver. Playwright's sync API creates its event loop on the thread
that starts it, and a page can only be used from that thread. Lesson 5 handles
this by sending every turn and every browser call to the agent's one worker
thread. If a design ever needs one driver per thread instead, `_driver` becomes
a `threading.local()`.

**Where `emit` points.** `Agent` takes `emit` in its constructor, so the agent
writes to one sink for its whole life. Lesson 7 builds that sink: a per-agent
numbered event log that the SSE route reads with `?after=N`. A turn keeps
running with nobody reading, and a reconnect replays what it missed.
`web-single-agent` passes `emit` per call instead, which ties events to one
HTTP response. Switching the class to that form is a two-line change if a
lesson wants it.

## Not planned yet

**Cancelling a turn.** In the terminal, Ctrl-C makes Python raise
`KeyboardInterrupt` on the main thread at whatever line is running. It unwinds
`handle_message`, `history.append_items` is never reached, and `main()` prints
`[turn interrupted]`. The agent has no code for this. It works because the
agent runs on the main thread and the host can raise into it.

A web host cannot. The turn runs on a worker thread, and Python has no safe way
to raise an exception in another thread. A stop button needs the agent to check
for itself. The smallest version:

```python
class TurnCancelled(Exception):
    """The host asked the agent to stop. Nothing from this turn is committed."""

def __init__(..., should_stop=lambda: False):
    self.should_stop = should_stop

# in _stream_response, inside `for event in stream`:
if self.should_stop():
    raise TurnCancelled  # leaving the with block closes the stream

# in handle_message, after each tool result is appended:
if self.should_stop():
    raise TurnCancelled
```

The terminal passes nothing and keeps Ctrl-C. The web host passes
`stop_event.is_set`, and `POST /api/agents/{id}/stop` sets the event.
`TurnCancelled` leaves `handle_message` the same way `KeyboardInterrupt` does,
so the commit-at-end rule already covers it.

A tool that is running when the flag flips finishes first. A shell command has
the 30-second timeout from `shell_tools`. Killing the subprocess on cancel is a
further step and belongs with the sandboxing work in `roadmap-production.md`.

Natural home: after lesson 7, where `AgentRuntime` already owns pending
approvals. A stop request is the same kind of per-agent state.

## Small

**Two static helpers in level 10.** `Agent._require_complete` and
`Agent._response_text` never read `self`. They can move to module level next
to `configured_output_limit`.
