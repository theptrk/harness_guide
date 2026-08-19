# Infinite Teammates — Production companion

This file collects implementation and operational work intentionally omitted
from the beginner lessons. It assumes the mechanism in [roadmap.md](roadmap.md)
already works.

These are not requirements for completing a lesson. They become relevant when
the agent handles untrusted input, confidential data, concurrent work, multiple
users, or tasks that must survive process and machine failures.

Levels 0–8 exist. Notes for Levels 9–19 are provisional.

---

## Part I — The loop

### 00 · Call a model

- Validate configuration and pin model versions when reproducibility matters.
- Reuse long-lived clients and connection pools.
- Keep credentials in managed secret storage and out of logs and child
  processes.
- Record provider request IDs, served model, status, latency, token usage, and
  errors.
- Add deadlines, cancellation, rate-limit handling, and usage budgets.

### 01 · Hold a conversation

- Give conversations, turns, messages, and events stable IDs and schema
  versions.
- Use locking or transactional storage when several processes can write.
- Commit a user request and terminal outcome as one recoverable turn.
- Define ownership, encryption, retention, export, redaction, and deletion.
- Detect malformed records and isolate damage instead of losing the whole
  conversation.
- Index by conversation and owner rather than relying on the latest filename.

### 02 · Give it one tool

- Generate or validate tool schemas from typed implementations.
- Apply semantic validation after JSON shape validation.
- Inject identity and authorization in the harness rather than accepting them
  from model arguments.
- Bound argument and result sizes.
- Give side-effecting operations idempotency keys.
- Trace tool choice, validated arguments, duration, result size, and failure
  without logging confidential payloads by default.

### 03 · Build the agent loop

- Represent turns as persisted states so another process can resume them.
- Bound model calls, tool calls, elapsed time, output size, and spend.
- Propagate cancellation through model streams and tools.
- Define scheduling and result ordering before enabling parallel tool calls.
- Separate transport retries from new model passes.
- Require idempotent or compensatable side effects before automatic resume.

### 04 · Harden the loop

- Use exponential backoff with jitter, provider retry hints, total deadlines,
  and shared retry budgets.
- Distinguish overload, authentication, authorization, invalid input, conflict,
  timeout, cancellation, and internal defects.
- Put deadlines and cancellation inside network, database, subprocess, and
  browser tools.
- Add dependency concurrency limits and circuit breakers.
- Quarantine failed turns without silently returning them to model input.
- Measure attempts, latency, error classes, incomplete reasons, and forced
  answers.

### 05 · Stream it

- Use a versioned event envelope and monotonically ordered event IDs.
- Bound buffers and define behavior for slow or disconnected consumers.
- Treat completion, failure, cancellation, and disconnect as different terminal
  states.
- Decide which partial output may be displayed before safety checks finish.
- Preserve the provider's terminal response as canonical model input.
- Add persisted progress and reconnect/replay at Level 18, when background work
  needs it.

---

## Part II — The computer

### 06 · Give it files

- Enforce file-size, workspace-size, file-count, and path-depth quotas.
- Write through temporary files and atomically rename completed content.
- Add file versions or content hashes so stale edits fail.
- Define encoding, newline, binary-file, permission, and executable-bit
  behavior.
- Test symlinks, hard links, path races, case-insensitive filesystems, and
  platform-specific paths.
- Give each user or assistant an independently authorized workspace.

### 07 · Run a command

- Prefer argument vectors with `shell=False`; use shell syntax only when the
  requested feature requires it.
- Build child environments from an allowlist and inject short-lived secrets
  explicitly.
- Bound stdout and stderr while the process runs.
- Use process groups so cancellation and timeout stop descendants.
- Enforce CPU, memory, process-count, disk, and wall-clock limits outside the
  child process.
- Bind approvals to an exact command, workspace, requester, action ID, and
  expiry.
- Record access-controlled, redacted, tamper-resistant action audit events.
- Move execution into the Level 15 sandbox before unattended or multi-user use.

---

## Part III — The handoff

### 08 · Give it a browser

- Isolate browser contexts, cookies, profiles, downloads, and storage by user.
- Treat page text, accessibility data, screenshots, and downloads as untrusted
  model input.
- Restrict URL schemes, private-network access, redirects, popups, downloads,
  and uploads.
- Use stable locator strategies and preserve evidence around consequential
  actions.
- Set navigation, action, and total-task deadlines.
- Bound page text and image data before adding them to model context.

### 09 · Human takeover

- Represent control as a durable lease with agent, human, waiting, resumed,
  expired, and cancelled states.
- Secure the screen and input channel.
- Keep passwords, passkeys, and one-time codes out of model-visible records.
- Bind confirmation to the exact action and evidence shown.
- Expire approval when the page, target, or consequences change.
- Prevent simultaneous agent and human control.
- Audit ownership changes and final decisions.

---

## Part IV — Reliability

### 10 · Trim history

- Use the target model tokenizer and reserve space for tools, retrieval, and
  output.
- Version summaries and record source ranges, models, prompts, and token counts.
- Protect current objectives, unresolved work, pinned facts, and safety
  constraints from compaction.
- Keep immutable source events and make compaction transactional.
- Evaluate whether summaries retain decisions, names, dates, and open tasks.
- Measure quality, latency, cache behavior, and cost rather than token reduction
  alone.

### 11 · Build a scored test set

- Version datasets, prompts, models, tools, judges, and execution environments.
- Repeat nondeterministic cases and report uncertainty.
- Calibrate model judges against human labels.
- Separate development, regression, and held-out cases.
- Prevent test answers from entering prompts, memory, and retrieval indexes.
- Store traces for failed cases and compare quality, latency, tokens, tool calls,
  and cost.
- Gate rollouts on explicit regression limits.

---

## Part V — Making it yours

### 12 · Long-term memory

- Store owner, provenance, source conversation, confidence, and expiry with each
  memory.
- Support view, correction, export, and deletion.
- Require consent for sensitive categories.
- Isolate and encrypt tenant data and indexes.
- Defend against memory poisoning and prompt injection in retrieved text.
- Resolve duplicates and contradictions without overwriting history silently.
- Evaluate saving and retrieval separately.

### 13 · Connect Gmail

- Use authorization code flow with PKCE, state validation, and exact redirect
  URIs.
- Request narrow scopes.
- Encrypt refresh tokens and handle rotation and revocation.
- Keep account identity separate from model-provided email addresses.
- Handle quotas, pagination, retries, stale cursors, and partial outages.
- Verify webhook signatures and deduplicate notifications.
- Redact message content from telemetry.

### 14 · Build a plugin system

- Give each plugin a versioned manifest for tools, schemas, scopes, secrets, and
  compatibility.
- Detect tool-name and schema conflicts at startup.
- Isolate dependencies and failures by plugin.
- Require explicit installation and permission review.
- Pin or sign packages and inspect dependency provenance.
- Add health checks, timeouts, concurrency limits, and circuit breakers per
  plugin.

---

## The fleet

### 15 · Sandbox it

- Run rootless with user namespaces, dropped capabilities, syscall filtering,
  and read-only base images.
- Deny network access by default and allow destinations explicitly.
- Enforce CPU, memory, process-count, disk, and time limits.
- Inject short-lived task secrets instead of copying the host environment.
- Scan and sign images and pin dependencies.
- Test escape boundaries and patch base images.

### 16 · Give each assistant a cloud computer

- Make provision, start, stop, snapshot, restore, and destroy operations
  idempotent.
- Encrypt disks and snapshots with tenant-scoped keys.
- Use machine identity and short-lived credentials.
- Reconcile desired state with unhealthy, abandoned, and orphaned machines.
- Define regions, data residency, capacity behavior, and image upgrades.
- Test restoration and provider outages.
- Enforce quotas, idle shutdown, ownership tags, and cost attribution.

### 17 · Separate assistants

- Enforce tenant and assistant identity in every storage and authorization key.
- Isolate histories, memories, accounts, workspaces, machines, caches, and logs.
- Make delegation explicit, scoped, attributable, and cancellable.
- Define ownership transfer, sharing, export, and deletion.
- Apply quotas and rate limits by user, assistant, and organization.

### 18 · Run background work

- Use durable queues with idempotency keys, deduplication, leases, heartbeats,
  retry schedules, and dead-letter handling.
- Persist checkpoints before and after external side effects.
- Define cancellation and compensation for partially completed actions.
- Sequence progress events for gap-free reconnect and replay.
- Design handlers for at-least-once delivery rather than claiming exactly-once
  execution.
- Retry completion and failure notifications.

### 19 · Operate it for other people

- Add authentication, organization boundaries, roles, and audited support
  access.
- Define service objectives, metrics, traces, alerting, incident response, and
  runbooks.
- Back up state and test restoration and disaster recovery.
- Centralize secret management, rotation, revocation, and emergency access.
- Enforce rate, concurrency, storage, model-spend, browser, and machine quotas.
- Add abuse prevention, privacy controls, retention policy, legal review, and
  vulnerability response.
- Roll out prompts, models, tools, policies, and images gradually with evaluation
  gates and rollback.

Production controls require continuing maintenance as providers, dependencies,
threats, and product behavior change.
