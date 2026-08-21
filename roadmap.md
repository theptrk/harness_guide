# Series 1 — Build an Agent Harness

This series builds a local AI agent from a single model call through a tool-using
agent loop with files, shell commands, and a browser.

All nine levels are implemented. Each level has a runnable folder under
`series-1/` and a lesson that explains what changed from the previous level.

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

## Part I — Build the loop

### 00 · Call a model

Send one question and one set of instructions through the Responses API. Print
the answer and inspect the raw response, served model, and token counts.

- **Learn** — API keys, model input, system instructions, SDK helpers, and raw
  response structure.
- **Done when** — One command prints a model answer and usage data.

### 01 · Hold a conversation

Write each user and assistant message to a JSONL chat file. Rebuild the complete
input list from that file before every model call.

- **Learn** — Models do not retain conversation state between calls. The
  harness owns persistence and decides what history to send.
- **Done when** — Restarting resumes the latest chat, while `--new` starts an
  empty conversation.

### 02 · Give it one tool

Describe `get_current_time(timezone)` with a JSON schema. When the model returns
a `function_call`, select the Python function by name, execute it, and send a
`function_call_output` back.

- **Learn** — The model requests an action; the harness decides whether and how
  to execute it.
- **Done when** — One request produces a tool call, Python result, and final
  answer.

### 03 · Build the agent loop

Put one user request in `run_turn()`. Repeat model calls and tool execution until
the model returns an answer instead of another tool request.

- **Learn** — The CLI loop waits for user messages. The agent loop completes one
  user request.
- **Done when** — One request triggers several sequential tool calls before the
  final answer.

### 04 · Harden the loop

Return tool exceptions as structured tool results, cap tool calls, configure API
timeouts and retries, and reject incomplete model responses before executing
their output.

- **Learn** — Tool failures are data the model may correct. Harness failures stop
  execution. A successful HTTP request may still contain an incomplete model
  response.
- **Done when** — Invalid arguments become tool results, runaway tool use stops,
  and incomplete output is never executed.

### 05 · Stream it

Print answer deltas as they arrive while preserving only the completed response
item as later model input. Record turn IDs so interrupted turns are excluded.

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
- **Done when** — The agent searches Google for a fixed historical fact,
  requests help if Google presents a CAPTCHA, resumes after you complete it, and
  reports an answer with a source URL.

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

*Series 1 complete · Levels 0–8 built*
