# [DRAFT] Series 2 — Advanced Agent Concepts

This series begins with the completed local harness from
[Series 1](roadmap.md). The first chapters add hosted search, select model
context, and measure changes on that harness. Later chapters add memory, account
connections, and separate assistants once those measurements exist.

These chapters are planned, not implemented.

---

## Part I — Search, context, and measurement

### 01 · Hosted tools and web search

The browser can search Google, but search-engine pages are unstable and may
return CAPTCHAs. Add the Responses API's hosted web-search tool and keep the
browser for interactive pages.

- **Concept** — A function tool executes in the local harness. A hosted tool
executes at the model provider. The same `tools` parameter can cross different
execution, privacy, and failure boundaries.
- **Done when** — A public-information question returns cited sources without
opening Chromium.



### 02 · Context selection

A conversation eventually exceeds the model's input limit. Build the model input
from recent messages, pinned information, and summaries while preserving the
complete event record.

- **Concept** — Stored history and model context are different views. Context is
selected for a particular call.
- **Done when** — A long task crosses the configured threshold, summarizes old
material, and continues without losing its objective.



### 03 · Evaluation

Model behavior changes across runs, models, prompts, and tool descriptions. Add
a fixed task set, automated checks where possible, model judges where necessary,
and comparison reports.

- **Concept** — One successful example is an observation, not evidence of a
reliable improvement.
- **Done when** — A prompt or model change has measured effects on success rate,
latency, token use, tool calls, and cost.

---



## Part II — Models and tool interfaces



### 04 · Model capability and reasoning budgets

Repeat the same tool task with different models and reasoning settings. Measure
whether the model discovers multi-step plans, recovers from errors, and uses the
capabilities already present in the harness.

- **Concept** — Harness capability determines what is possible. Model capability
affects whether the model can discover and execute the required sequence.
- **Done when** — Model and reasoning choices are justified by evaluation
results rather than one impressive or disappointing run.



### 05 · Tool-interface design

Compare a general shell tool with dedicated file, browser, and search tools.
Study how names, descriptions, argument shapes, return values, and plan length
change model behavior.

- **Concept** — A tool can expose an existing underlying capability while making
it easier for the model to discover, constrain, and verify.
- **Done when** — A tool-interface change improves measured reliability without
silently expanding authority.

---



## Part III — Memory, accounts, and assistants



### 06 · Long-term memory and retrieval

Search conversations that are not in the current context and maintain a small
set of durable facts that should remain easy to retrieve.

- **Concept** — Storage, retrieval, and the policy deciding what to save or load
are separate mechanisms.
- **Done when** — The agent answers a question using a relevant decision from an
older conversation and shows where it found it.



### 07 · OAuth and account connections

Connect one account through OAuth, then expose a small set of account-specific
tools. Gmail is a concrete example, not a required account for the series.

- **Concept** — OAuth delegates limited authority without giving the model a
password. Scopes, access tokens, refresh tokens, expiry, and revocation define
that authority.
- **Done when** — One connected account still works after its first access token
expires.



### 08 · Tool and plugin discovery

Replace the hardcoded tool assembly in `main.py` with components that declare
their names, schemas, implementations, configuration, and account requirements.

- **Concept** — Discovery lets the harness assemble capabilities from installed
components instead of editing one central registry.
- **Done when** — Adding another integration requires changes only inside its own
component.



### 09 · Multiple assistants

Give separate assistants their own instructions, histories, memories, tools,
accounts, and workspaces. Route each conversation to one assistant identity.

- **Concept** — Isolation requires consistent identity across every stored object
and tool execution, not merely different system prompts.
- **Done when** — Unrelated assistants cannot retrieve or act on one another's
context.

---



## Part IV — Humans and other APIs



### 10 · Human collaboration

Study tasks that require private input, judgment, or physical action. Separate
ordinary conversation from systems where a background agent and a person may
control the same resource concurrently.

- **Concept** — The synchronous CLI already supports an informal handoff because
the model stops and the browser remains open. Explicit ownership state matters
only when execution can continue concurrently or asynchronously.
- **Done when** — The implementation adds coordination only where a demonstrated
concurrency or durability problem requires it.



### 11 · Provider adapters and portable events

Compare OpenAI function calls, hosted tools, and another provider's tool
protocol. Define a small internal event model only after the differences are
visible.

- **Concept** — SDK objects are provider-specific representations. A portable
adapter should preserve information rather than pretending the protocols are
identical.
- **Done when** — One harness can use two providers without losing tool-call,
streaming, refusal, or usage information.

---



## Where to continue

[Production Agent Systems](roadmap-production.md) begins when these mechanisms
must operate safely for other users, survive failures, and run without constant
supervision.