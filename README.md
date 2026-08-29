# Infinite Teammates

Building an AI agent harness from first principles, one level at a time.

[**Series 1 — Build an Agent Harness**](roadmap.md) is the implemented
introduction. Levels 0–8 build a model call into a local agent with persistence,
tools, an agent loop, files, shell commands, and a browser.

**[DRAFT]** [**Series 2 — Advanced Agent Concepts**](roadmap-intermediate.md) plans the
follow-on concepts: hosted tools, context selection, evaluation, model
capability, tool interfaces, memory, account connections, plugins, multiple
assistants, and provider adapters.

**[DRAFT]** [**Series 3 — Production Agent Systems**](roadmap-production.md) covers
sandboxing, durable computers, background work, identity, secrets, concurrency,
browser security, observability, quotas, deployment, and recovery.

The Series 1 lessons are the guide. Start here:

| Level | | |
|---|---|---|
| 0 | [Call a model](series-1/00-model/LESSON.md) | one file, one dependency |
| 1 | [Hold a conversation](series-1/01-conversation/LESSON.md) | …because it forgot your name |
| 2 | [Give it one tool](series-1/02-tool/LESSON.md) | …because it has no clock |
| 3 | [Build the agent loop](series-1/03-loop/LESSON.md) | …because one tool call was not enough |
| 4 | [Harden the loop](series-1/04-harden/LESSON.md) | …because tools and model calls fail |
| 5 | [Stream it](series-1/05-stream/LESSON.md) | …because the terminal stays blank while the model works |
| 6 | [Give it files](series-1/06-files/LESSON.md) | …because answer text cannot change a file |
| 7 | [Run a command](series-1/07-shell/LESSON.md) | …because it cannot run the code it writes |
| 8 | [Use a browser](series-1/08-browser/LESSON.md) | …because browser work otherwise requires shell automation |

[`series-1-agent-class/`](series-1-agent-class/README.md) contains the same
levels with an `Agent` class owning the model client and selected chat.

## How to use this

Clone the repo and work through the levels in order. **You are not writing these files from scratch** — the code is here, it runs, and each level is short enough to read top to bottom in one sitting.

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
uv run --env-file .env series-1/00-model/main.py "why is the sky blue"
```

Alternatively, set `export UV_ENV_FILE=.env` once and you can drop the flag from every command.

Level 8 adds a separate one-time Chromium install:

```sh
uv run playwright install chromium
```

## How this is laid out

Each level is a folder under `series-1/`. You can run any level without the
ones after it. Adjacent folders are complete copies, so a diff is the code
that level added:

```sh
diff -ru series-1/00-model series-1/01-conversation
```

Built and tested with Python 3.13, `openai` 3.2.0, and Playwright 1.62.0.
