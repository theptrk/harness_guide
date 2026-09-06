# Series 1 — Build an Agent Harness

This series builds a local AI agent from a single model call through a tool-using
agent loop with files, shell commands, and a browser.

All eleven levels are implemented. Each level has a runnable folder under
`series-1-agent-class/` and a lesson that explains what changed from the
previous level.

The follow-on series are:

- [Advanced Agent Concepts](roadmap-intermediate.md)
- [Production Agent Systems](roadmap-production.md)

---

## What you finish with

The final program is a synchronous command-line agent. It:

- persists separate conversations;
- lets a model request tools;
- repeats model and tool calls until one request is complete;
- returns tool failures to the model for correction;
- streams answer text;
- reads and changes files in a confined workspace;
- runs shell commands after approval;
- operates one persistent Chromium page;
- asks you to complete a CAPTCHA in the visible browser, then continues from the
  same page.

This is a complete introduction to an agent harness. It is not a production
service. Sandboxing, durable cloud execution, queues, multi-user isolation, and
operational controls belong to the production series.

---

## Part I — Build a safe loop

### 00 · Call a model

Give an `Agent` one model client. Send one question and one set of instructions
through the Responses API. The host prints the returned answer and usage.

- **Learn** — API keys, model input, system instructions, SDK helpers, and raw
  response structure. The agent owns model behavior; the host owns terminal
  behavior.
- **Done when** — One command prints a model answer and usage data.

### 01 · Hold a conversation

Keep completed Responses API items in an in-memory list. Send that list followed
by the new user item on each model call.

- **Learn** — Models do not retain conversation state between calls. The
  agent owns the conversation input. Persistence is a separate concern.
- **Done when** — The agent recalls an earlier message during one process and
  forgets it after restart.

### 02 · Give it one tool

Describe `get_current_time(timezone)` with a JSON schema. When the model returns
a `function_call`, select the Python function by name, execute it, and send a
matching `function_call_output` back. Report turn steps to the host through
`emit`.

- **Learn** — The model requests an action; the harness decides whether and how
  to execute it.
- **Done when** — One request produces a tool call, Python result, and final
  answer.

### 03 · Build the agent loop

Put one user request in `Agent.handle_message()`. Repeat model calls and tool
execution until the model returns an answer instead of another tool request.
Bound the number of executed tools.

- **Learn** — The CLI loop waits for user messages. The agent loop completes one
  user request.
- **Done when** — One request triggers several sequential tool calls before the
  final answer.

### 04 · Make the loop safe

Reject incomplete model responses before executing their output. Return tool
exceptions and exhausted tool budgets as matching tool results. Commit only a
completed turn to conversation history.

- **Learn** — Tool failures are data the model may correct. Harness failures stop
  the turn. A successful HTTP request may still contain an incomplete model
  response that is unsafe to execute.
- **Done when** — Invalid arguments become tool results, runaway tool use stops,
  and incomplete output is never executed.

### 05 · Stream it

Print answer deltas as they arrive while preserving only the completed response
item as later model input. Discard interrupted turns.

- **Learn** — Display events and canonical API input serve different purposes.
- **Done when** — Text appears incrementally, and interrupting a turn does not
  corrupt the next request.

---

## Part II — Give it a computer

### 06 · Give it files

Add `list_files`, `read_file`, `write_file`, and `edit_file`. Resolve every path
inside `agent_workspace/` before touching the filesystem. `read_file` returns a
line window, not the complete file.

- **Learn** — Model-selected paths are untrusted input. Tool adapters keep the
  model-facing interface separate from filesystem implementation.
- **Done when** — The agent creates, reads, and edits a file while paths outside
  the workspace are rejected.

### 07 · Run a command

Add `run_command`. Show the exact shell command and require explicit approval
before `subprocess.run()` executes it from the workspace.

- **Learn** — Capability, authorization, and execution belong to different
  actors even when they appear in one tool call.
- **Done when** — An approved command returns stdout, stderr, and exit code; a
  denied command does not run.

### 08 · Use a browser

Wrap Playwright with `open_page`, `read_page`, `type_text`, and `click`. Keep one
visible Chromium `Page` alive across tool calls and user turns. Convert selected
DOM content and interactive-element attributes into JSON tool results.

- **Learn** — A live browser object cannot be sent to the model. The harness
  provides a smaller model-facing representation and explicit browser actions.
- **Done when** — The agent opens a local page, reads its interactive elements,
  clicks a button, and reports the resulting value.

---

## Part III — Persist and operate it

### 09 · Persist conversations

Replace the in-memory conversation list with an append-only JSONL file. The host
selects the file; the agent reads and appends canonical API items.

- **Learn** — Conversation input and durable storage are separate
  representations with an explicit conversion.
- **Done when** — Restarting resumes the latest chat, while `--new` starts an
  empty conversation.

### 10 · Add operational policy

Configure SDK retries and request timeouts, allow an optional output limit,
extract refusal content, and decide how the terminal exits after API or harness
failures.

- **Learn** — Protocol safety is required for correct tool execution.
  Operational policy decides how a particular host handles service failures.
- **Done when** — Normal requests still work, refusals are displayed, and
  incomplete output caused by a low output limit exits without executing it.

---

## Where to continue

[Advanced Agent Concepts](roadmap-intermediate.md) starts after this harness
works. It covers hosted tools, context selection, evaluation, model capability,
tool interfaces, memory, account connections, plugin discovery, multiple
assistants, and provider boundaries.

[Production Agent Systems](roadmap-production.md) covers the work required when
the agent handles untrusted users, confidential data, concurrent tasks, durable
execution, or real operational risk.

---

*Series 1 complete · Levels 0–10 built*
