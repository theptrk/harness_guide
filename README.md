# Infinite Teammates

Building an AI agent harness from first principles, one level at a time.

[**Series 1 — Build an Agent Harness**](series-1-agent-class/README.md) is the
implemented introduction and the default path. Its 11 levels build a model call
into a local agent with conversation state, tools, streaming, files, shell
commands, a browser, persistence, and operational failure policy.

**[DRAFT]** [**Series 2 — Advanced Agent Concepts**](roadmap-intermediate.md) plans the
follow-on concepts: hosted tools, context selection, evaluation, model
capability, tool interfaces, memory, account connections, plugins, multiple
assistants, and provider adapters.

**[DRAFT]** [**Series 3 — Production Agent Systems**](roadmap-production.md) covers
sandboxing, durable computers, background work, identity, secrets, concurrency,
browser security, observability, quotas, deployment, and recovery.

Start Series 1 here:

| Level | Lesson | Adds |
|---|---|---|
| 00 | [Model](series-1-agent-class/00-model/LESSON.md) | one model call |
| 01 | [Conversation](series-1-agent-class/01-conversation/LESSON.md) | in-memory conversation state |
| 02 | [One tool](series-1-agent-class/02-tool/LESSON.md) | one function call and result |
| 03 | [Loop](series-1-agent-class/03-loop/LESSON.md) | repeated model and tool calls |
| 04 | [Safe loop](series-1-agent-class/04-safe-loop/LESSON.md) | response validation and bounded execution |
| 05 | [Stream](series-1-agent-class/05-stream/LESSON.md) | incremental answer display |
| 06 | [Files](series-1-agent-class/06-files/LESSON.md) | confined file tools |
| 07 | [Shell](series-1-agent-class/07-shell/LESSON.md) | approved shell commands |
| 08 | [Browser](series-1-agent-class/08-browser/LESSON.md) | browser tools |
| 09 | [Persistence](series-1-agent-class/09-persistence/LESSON.md) | append-only conversation history |
| 10 | [Operational policy](series-1-agent-class/10-operational/LESSON.md) | retries, timeouts, output bounds, and failure handling |

[`series-1/`](series-1/README.md) is the legacy function-based implementation.
It is kept for reference and is not the default Series 1 path. Its README lists
where the two differ.

## How to use this

Clone the repo and work through the levels in order. The code is complete and
each level can run independently.

Your job at each level is:

1. Read the lesson. It opens with the thing that broke at the end of the level before.
2. Run the code and watch it do what the lesson says it does.
3. Do the exercises at the bottom.

If you'd rather build it yourself, the lessons work for that too — read the level folder as the reference answer rather than the starting point.

## Setup

Done once.

```sh
git clone <repo-url> infinite-teammates
cd infinite-teammates
curl -LsSf https://astral.sh/uv/install.sh | sh   # if you don't have uv
cp .env.example .env                              # then put your key in it
```

`uv` installs the Python dependencies on the first run:

```sh
uv run --env-file .env series-1-agent-class/00-model/main.py
```

Alternatively, set `export UV_ENV_FILE=.env` once and you can drop the flag from every command.

Level 8 adds a separate one-time Chromium install:

```sh
uv run playwright install chromium
```

## How this is laid out

Each level is a folder under `series-1-agent-class/`. You can run any level
without the ones before it. Adjacent folders are complete copies. Compare them
to see the code added by the next level:

```sh
diff -ru -x chats -x agent_workspace \
  series-1-agent-class/00-model \
  series-1-agent-class/01-conversation
```

Built and tested with Python 3.13, `openai` 3.2.0, and Playwright 1.62.0.
