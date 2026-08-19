# Infinite Teammates — Intermediate companion

This file names the deeper software concept behind each level in
[roadmap.md](roadmap.md). It is not another implementation path.

The beginner lessons show a mechanism directly. This companion connects that
mechanism to ideas that appear in larger agent systems and other kinds of
software.

Levels 0–8 exist. Levels 9–19 are still planned.

---

## Part I — The loop

### 00 · Representation layers

The HTTP response, the SDK object, and helper properties are three views of the
same result. Knowing which layer supplied a value makes it easier to change
libraries, languages, or providers without treating convenience APIs as protocol
fields.

### 01 · Event log and projection

The conversation file is the durable record. The list sent to the model is a
projection built from that record. This separation allows several views of the
same history: full, trimmed, summarized, filtered, or rendered for a person.

### 02 · Declarative capabilities

A tool has an executable implementation and a description the model can reason
about. The schema is a declarative interface: it says which capability exists
without giving the model direct access to the function.

### 03 · State machines

The agent loop can be described as states and transitions: waiting for a model,
waiting for a tool, accepting a result, and finishing with an answer. The
`while` loop is one implementation of that state machine.

### 04 · Protocol invariants

A function call and its output are a pair connected by `call_id`. A partial
response is not interchangeable with a complete one. These are protocol
invariants: conditions that must remain true regardless of how the surrounding
program is organized.

### 05 · Incremental display and canonical state

Stream deltas are useful for immediate display, while the terminal response is
the complete object used for later model input. One operation can therefore
produce an incremental view and a canonical result without confusing the two.

---

## Part II — The computer

### 06 · Adapters and capability boundaries

The model-facing file tools do not manipulate `Path` objects directly. They call
a workspace adapter. That boundary separates what the agent can request from
where and how the operation is implemented.

### 07 · Delegated execution

The model proposes a command, the harness asks a person, and the operating
system executes only after approval. Capability, authorization, and execution
belong to different actors even though they appear in one tool call.

---

## Part III — The handoff

### 08 · Multiple representations of a page

A browser page can be represented as a DOM, accessibility tree, screenshot, or
set of interaction targets. Each representation preserves different
information. Browser agents work by choosing and combining those views.

### 09 · Cooperative control

Human takeover turns ownership into explicit state. The agent can be running,
waiting, controlled by a person, or ready to resume. Human-in-the-loop software
works better when waiting is a normal state rather than an exception.

---

## Part IV — Reliability

### 10 · Context as a selected view

The conversation record and the model context are not the same thing. Trimming
and summarization define a selected, sometimes lossy view of a larger record.
Context management is therefore a policy about relevance, not only token count.

### 11 · Empirical evaluation

Model behavior is nondeterministic, so examples are observations rather than
proofs. A scored test set turns prompt and model choices into hypotheses that
can be compared across repeated runs.

---

## Part V — Making it yours

### 12 · Retrieval as a tool

Long-term memory can use the same mechanism as time, files, and shell access:
the model requests relevant information through a tool. Storage, retrieval, and
the decision to retrieve remain separate concerns.

### 13 · Delegated authority

OAuth lets a program act with a limited portion of a user's authority without
receiving the user's password. Scopes, access tokens, refresh tokens, and
revocation describe how that delegation changes over time.

### 14 · Discovery and composition

A plugin system moves tool assembly from a hardcoded list to discovery.
Integrations become components that describe their own tools and account
requirements, while the core builds one combined capability set.

---

## The fleet

### 15 · Defense in depth

Application checks and operating-system isolation are different boundaries.
The workspace adapter limits normal file operations; a sandbox limits what
happens when application logic is wrong or untrusted code runs.

### 16 · Compute as a managed resource

A cloud computer has a lifecycle independent of one process: provision, start,
stop, persist, restore, and destroy. The agent uses compute through that
lifecycle rather than assuming the current laptop always exists.

### 17 · Namespaces and identity

Separate assistants require more than different prompts. Their histories,
memories, tools, accounts, workspaces, and machines need a consistent identity
that follows every operation.

### 18 · Durable workflows

Background work separates a task from the request that started it. Checkpoints,
leases, progress events, cancellation, and replay let another process continue
the same logical job.

### 19 · Feedback systems

A service is observed and adjusted while it runs. Usage, failures, evaluations,
user reports, and operational limits become feedback that changes models,
prompts, tools, and policies over time.
