# Level 0 — Call a model

You create one `Agent`, send it a question, and print what comes back. One file,
one dependency. `main()` builds the OpenAI client and a `Terminal`. `Agent`
makes the request and calls `terminal.emit` with what came back. `Terminal`
prints.

This is the only level with nothing before it, so there's no "here's what broke" to open with. Everything after this one starts with something that doesn't work.

---

You need `uv` installed and a key in `.env` — that's the [Setup section of the README](../../README.md#setup). Level 8 adds a one-time Chromium install.

---

## Run it

The call returns one object. Two ways to read it:

- The JSON. What came over the wire. Every field in it is in the HTTP API. `--raw` prints this.
- Helper properties the OpenAI Python SDK adds on the parsed object. They are not in the JSON. `response.output_text` is one.

Start with `--raw`:

```sh
uv run --env-file .env series-1-agent-class/00-model/main.py --raw "why is the sky blue"
```

`--env-file .env` loads `OPENAI_API_KEY` from `.env`. Without it, the program
prints:

```text
OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.
```

To avoid repeating the flag, set the environment-file path once:

```sh
export UV_ENV_FILE=.env
```

Then `uv run series-1-agent-class/00-model/main.py --raw "why is the sky blue"` is equivalent.

The agent holds one OpenAI client and one `emit` function. It makes one
request and reports it in three `emit` calls:

```python
class Agent:
    def __init__(self, client, *, emit):
        self.client = client
        self.emit = emit

    def handle_message(self, question):
        response = self.client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,  # applies to every question
            input=question,              # user input
            reasoning={"effort": "none"},
        )
        self.emit({"type": "response", "response": response})
        self.emit({"type": "text", "text": response.output_text})
        self.emit({"type": "done", "input_tokens": ..., "output_tokens": ..., ...})
```

Each `emit` call passes one dict with a `type`: `response` carries the whole
response object, `text` carries the answer, `done` carries the token counts,
`status`, and `model`.

`main()` reads the command-line arguments, creates `Terminal(raw=raw)`, creates
`Agent(OpenAI(), emit=terminal.emit)`, and calls
`agent.handle_message(question)`. It does not make the model request. The
agent does not print. `Terminal.emit()` prints each event it receives.

That `--raw` flag makes the terminal print the output text twice:

```python
# once as the entire json model response
if kind == "response" and self.raw:
    print(event["response"].model_dump_json(indent=2))

# once as the answer the agent read out of it with ".output_text"
elif kind == "text":
    print(f"🤖 model › {event['text']}")
```

A truncated sample of the JSON:

```json
{
  ...
  "created_at": 1786995481.0,
  "instructions": "You are a concise assistant. Answer in a few sentences.",
  "model": "gpt-5.6-luna",
  "status": "completed",
  "output": [
    {
      "id": "msg_088b100b6ca1b13c006a83631aa1b8819b91a85f84570bd549",
      "type": "message",
      "role": "assistant",
      "phase": "final_answer",
      "status": "completed",
      "content": [
        {
          "annotations": [],
          "text": "Sunlight contains many colors...",
          "type": "output_text"
        }
      ]
    }
  ],
  ...
  "completed_at": 1786995483.0,
  "usage": {
    "input_tokens": 27,
    "input_tokens_details": {...},
    "output_tokens": 52,
    "output_tokens_details": { "reasoning_tokens": 0 },
    "total_tokens": 79
  },
  ...
}
```

Read it against the [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create) `create` [docs](https://developers.openai.com/api/reference/python/resources/responses/methods/create). Find these in that JSON:


| In the JSON                                     | What it's for                                                                                  |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `.output[0].type`                               | which kind of item this is. `message` on this call.                                            |
| `.output[0].content[0].text`                    | the answer                                                                                     |
| `.usage.input_tokens`, `.usage.output_tokens`   | how many tokens the request used                                                               |
| `.usage.output_tokens_details.reasoning_tokens` | tokens spent thinking before the visible answer. Included in `output_tokens`. Not in the text. |
| `model`                                         | which model served the request                                                                 |


In the JSON, `reasoning_tokens` is nested under
`usage.output_tokens_details`. Its count is already included in
`usage.output_tokens`; do not add the two numbers together. The default
reasoning effort is `medium`. The sample shows `0` reasoning tokens because
`main.py` sets `reasoning={"effort": "none"}`.

`output` is a list of items. Each item has a `type`. This call returned one `message`. The item types this series uses:

- `message`. Assistant text. Fields include `role`, `content`, `status`, and `phase`. A turn can return more than one assistant message. `phase` marks each one as `commentary` (a mid-turn update, such as what it will do next) or `final_answer` (the answer for this turn). When you put that message on a later `input` list, you send `phase` with it.
- `function_call`. The model wants a function run. Fields include `name`, `arguments`, and `call_id`.
- `function_call_output`. Your function result. Same `call_id`, plus `output`. This type is something you put on `input`. It does not arrive in `output`.

`input` on this call is a string. The same argument also accepts a list of those items. Later levels send the list. They do not invent a second conversation format.

The [Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses) documents more item types than these. This series does not use them.

`response.output_text` is a helper. Search the JSON for a top-level `output_text`. It is not there. The SDK walks `output`, keeps `message` items, keeps blocks whose type is `output_text`, and joins the strings. It skips `function_call` items. If `output` has no message text, the helper returns an empty string. That walk is `output[0].content[0].text` on the payload above.

In `openai-python` **v3.2.0** it's [this loop in](https://github.com/openai/openai-python/blob/v3.2.0/src/openai/types/responses/response.py#L481-L493) `response.py`. Read it at the version you have; library code moves:

```sh
uv run python -c "import inspect; from openai.types.responses import Response; print(inspect.getsource(Response.output_text.fget))"
```

Now run it without the flag:

```sh
uv run --env-file .env series-1-agent-class/00-model/main.py "why is the sky blue"
```

The model's answer prints first. The usage line follows:

```text
🤖 model › Sunlight contains many colors...
[27 input + 52 output tokens  0 reasoning tokens  status=completed]
```

Same call. The difference is only how much of the response you chose to look at.

---

## What's in here

```
series-1-agent-class/00-model/
  LESSON.md    this file
  main.py      Agent, Terminal, and the command-line entry point
```

The core of the code is this call:

```python
response = self.client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    input=question,
    reasoning={"effort": "none"},
)
```

`MODEL` and `SYSTEM_PROMPT` are defined earlier in `main.py`. `question` is the
message passed to `Agent.handle_message()`.

---

## What this level adds

**`Agent` makes the request and reports it. `Terminal` prints.** `main()`
checks the environment, parses argv, and builds both. There is no `print()`
inside `Agent`. It calls `emit` with one dict per event, and `emit` is
whatever function `main()` passed in. Here that is `Terminal.emit`. A host
that is not a terminal passes a different function. Every later level creates
the agent the same way and adds arguments beside `emit`:

```python
agent = Agent(OpenAI(), emit=terminal.emit)
```

**The key lives in the environment, not the code.** `main()` calls `OpenAI()`,
which reads `OPENAI_API_KEY` on its own, and passes the client to `Agent`. You
never pass the key in, never assign it to a variable, never let it near a file
you might commit.

**You send two pieces of text, and they have different jobs.** `instructions`
is the system prompt — it applies to every question you'll ever ask. `input` is
this one question. The evaluation chapter in
[Advanced Agent Concepts](../../roadmap-intermediate.md) changes the first one
and measures what happens.

**Tokens are the unit of model input and output.** Not characters, not words. The response tells you how many went in and how many came out. Those counts matter later when a conversation approaches the model's context limit.

---

## Try these

**See what an alias does.** In `main.py`, change `MODEL` to `"gpt-5.6"`, run with `--raw`, and look at `model`. You should see `gpt-5.6-sol`. Then put it back.

**Change the system prompt.** In `main.py`, set `SYSTEM_PROMPT` to `"Answer in exactly one word."` and ask the same question. Then try `"You are a pirate."` The system prompt is the largest single influence you have on behaviour, and it's one string.

---

## Done when

1. Run:
  ```sh
   uv run --env-file .env series-1-agent-class/00-model/main.py --raw "Why is the sky blue?"
  ```
2. Confirm that the terminal shows:
  - A raw response containing `output`, `usage`, `model`, and `status`.
  - A `🤖 model ›` line containing the answer.
  - A final line with nonzero input and output token counts, `0 reasoning`, and `status=completed`.

---

## What breaks next

Try holding a conversation:

```sh
uv run --env-file .env series-1-agent-class/00-model/main.py "My name is Patrick."
uv run --env-file .env series-1-agent-class/00-model/main.py "What is my name?"
```

It has no idea. Two separate calls, and the model kept nothing between them.

```text
$ uv run --env-file .env series-1-agent-class/00-model/main.py "What is my name?"
I don’t know your name—you haven’t shared it with me.
```

That's [Level 1](../01-conversation/LESSON.md).
