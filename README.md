# Infinite Teammates

Building an agent from first principles, one level at a time — up to something that opens a browser, asks you to sign in when it hits a login wall, and picks the task back up.

[**roadmap.md**](roadmap.md) is the plan: all twenty levels, what breaks at each one, and what's still undecided.

The lessons are the guide. Start here:

| Level | | |
|---|---|---|
| 0 | [Call a model](levels/00-model/LESSON.md) | one file, one dependency |
| 1 | [Hold a conversation](levels/01-conversation/LESSON.md) | …because it forgot your name |
| 2 | [Give it one tool](levels/02-tool/LESSON.md) | …because it has no clock |
| 3 | [Build the agent loop](levels/03-loop/LESSON.md) | …because one tool call was not enough |
| 4 | [Harden the loop](levels/04-harden/LESSON.md) | …because tools and model calls fail |
| 5 | [Stream it](levels/05-stream/LESSON.md) | …because completed responses arrive too late |

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

`uv` installs the dependencies on the first run, so there's nothing else to do:

```sh
uv run --env-file .env levels/00-model/main.py "why is the sky blue"
```

Alternatively, set `export UV_ENV_FILE=.env` once and you can drop the flag from every command.

## How this is laid out

One folder per level, each runnable on its own. Comparing two folders shows exactly what a feature cost:

```sh
diff -ru levels/00-model levels/01-conversation
```

Built and tested with Python 3.13 and `openai` 3.2.0.
