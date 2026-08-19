# Series 3 — Production Agent Systems

This series starts with a working harness and addresses the requirements created
by untrusted users, confidential data, concurrent tasks, external side effects,
and failures that outlive one process.

It is an operational series, not a continuation of the beginner level numbers.
The sequence is provisional.

---

## 01 · Define trust and authority

List every actor and boundary: user, model provider, model output, tool,
workspace, browser, connected account, worker, and administrator. Decide which
actions each identity may request and execute.

- Validate model-generated arguments before authorization.
- Keep authorization context in the harness, not in model-provided arguments.
- Separate read, write, execution, network, account, and administrative access.
- Require explicit policy for irreversible and high-impact actions.

## 02 · Sandbox execution

Move file and shell operations off the user's laptop and into an isolated
runtime.

- Run rootless with dropped capabilities, syscall restrictions, and a read-only
  base image.
- Deny network access by default and allow destinations explicitly.
- Enforce CPU, memory, process, disk, output, and wall-clock limits outside the
  child process.
- Inject short-lived task credentials instead of copying the host environment.
- Rebuild and patch runtime images regularly.

## 03 · Protect identity and secrets

Give every request a verified user, organization, assistant, and task identity.
Keep secrets out of prompts, tool results, histories, and logs.

- Store secrets in managed secret storage with rotation and revocation.
- Encrypt account tokens and browser profiles with tenant-scoped keys.
- Request narrow OAuth scopes.
- Keep support and administrative access attributable and audited.
- Support account disconnect, user export, and deletion.

## 04 · Manage durable computers

Provision an isolated computer for an assistant or task and manage its complete
lifecycle independently of one web request.

- Make create, start, stop, snapshot, restore, and destroy idempotent.
- Persist authorized workspace and browser state across process restarts.
- Reconcile abandoned, unhealthy, and orphaned machines.
- Define image upgrades, regions, capacity behavior, and data residency.
- Enforce ownership tags, quotas, idle shutdown, and cost attribution.

## 05 · Run background work

Put long tasks in a durable queue and let workers continue after the initiating
client disconnects.

- Use task IDs, idempotency keys, deduplication, leases, and heartbeats.
- Persist checkpoints before and after external side effects.
- Design for at-least-once delivery and duplicate execution.
- Define retries, dead-letter handling, cancellation, and compensation.
- Sequence progress events so clients can reconnect without gaps.

## 06 · Coordinate concurrent control

Add explicit ownership only when a background agent and a person or another
worker can act on the same resource at the same time.

- Prevent simultaneous browser control.
- Expire stale human handoffs and approvals.
- Bind approval to the exact action and evidence shown.
- Lock or version files and shared records.
- Define ordering for parallel tool calls and concurrent turns.

## 07 · Secure browsers and retrieved content

Treat webpages, search results, email, files, and tool output as untrusted input
that may attempt to redirect the model.

- Restrict URL schemes, redirects, private-network access, downloads, and
  uploads.
- Isolate browser contexts, cookies, profiles, and storage by tenant.
- Keep passwords, passkeys, CAPTCHA responses, and one-time codes out of model
  input.
- Preserve source URLs and evidence around consequential actions.
- Test prompt injection across browser, search, memory, and account tools.

## 08 · Observe and audit

Record enough structured evidence to explain behavior without logging every
confidential payload.

- Trace model calls, served models, latency, tokens, retries, and request IDs.
- Trace tool choice, validated arguments, authorization, duration, outcome, and
  result size.
- Use versioned event schemas and ordered event IDs.
- Keep access-controlled, redacted, tamper-resistant audit records.
- Define metrics, alerts, service objectives, runbooks, and incident response.

## 09 · Control quality, usage, and cost

Treat model, prompt, tool, and policy changes as releases.

- Version evaluation datasets, prompts, models, tools, judges, and runtime
  images.
- Gate rollout on quality, latency, safety, and cost thresholds.
- Enforce request, concurrency, storage, browser, machine, and model-spend
  quotas.
- Add provider rate-limit handling and shared retry budgets.
- Roll out gradually and retain a tested rollback path.

## 10 · Manage data lifecycle and recovery

Define how every durable object is retained, backed up, restored, exported, and
deleted.

- Version conversation, memory, tool, plugin, and checkpoint schemas.
- Make migrations resumable and reversible where possible.
- Encrypt backups and test restoration.
- Define retention and deletion for chats, files, browser state, account data,
  logs, and evaluation traces.
- Exercise regional failure and disaster-recovery procedures.

---

Production work does not end at the final chapter. Providers, dependencies,
threats, regulations, and product behavior continue to change.
