# Level 0 — Call a model

You send a question to a model and print what comes back. One file, one dependency, no framework.

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
uv run --env-file .env series-1/00-model/main.py --raw "why is the sky blue"
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

Then `uv run series-1/00-model/main.py --raw "why is the sky blue"` is equivalent.

We use the OpenAI SDK

```python
client = OpenAI()

response = client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,  # applies to every question
    input=question,              # user input
    reasoning={"effort": "none"},
)
```

That `--raw` flag makes the command print the output text twice:

```python
# once as the entire json model response
if raw:
    print(response.model_dump_json(indent=2))

# once using the sdk helper property ".output_text"
print(response.output_text)
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
      "content": [
        {
          "annotations": [],
          "text": "Sunlight contains many colors...",
          "type": "output_text",
        }
      ],
      "status": "completed",
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
| `.output[0].content[0].text`                    | the answer                                                                                     |
| `.usage.input_tokens`, `.usage.output_tokens`   | how many tokens the request used                                                               |
| `.usage.output_tokens_details.reasoning_tokens` | tokens spent thinking before the visible answer. Included in `output_tokens`. Not in the text. |
| `model`                                         | which model served the request                                                                 |


In the JSON, `reasoning_tokens` is nested under
`usage.output_tokens_details`. Its count is already included in
`usage.output_tokens`; do not add the two numbers together. The default
reasoning effort is `medium`. The sample shows `0` reasoning tokens because
`main.py` sets `reasoning={"effort": "none"}`.

`response.output_text` is a helper. Search the JSON for a top-level `output_text` — it isn't there. The SDK walks `output`, keeps message items, keeps blocks whose type is `output_text`, and joins the strings. That walk is `output[0].content[0].text` on the payload above.

In `openai-python` **v3.2.0** it's [this loop in](https://github.com/openai/openai-python/blob/v3.2.0/src/openai/types/responses/response.py#L481-L493) `response.py`. Read it at the version you have; library code moves:

```sh
uv run python -c "import inspect; from openai.types.responses import Response; print(inspect.getsource(Response.output_text.fget))"
```

`response.output` can contain `message` items and `function_call` items. A message item's `content` list can contain `output_text` blocks. The `output_text` helper collects those blocks and skips the function-call items. If a response contains a tool request but no message text, the helper returns an empty string.

`phase` on the message is `final_answer` here. Level 1 has to send that field back; ignoring it is a silent quality bug on this model family.

Now run it without the flag:

```sh
uv run --env-file .env series-1/00-model/main.py "why is the sky blue"
```

The model's answer prints first. The usage line follows:

```
[27 input + 52 output tokens  0 reasoning tokens  status=completed]
```

Same call. The difference is only how much of the response you chose to look at.

---

## What's in here

```
series-1/00-model/
  LESSON.md    this file
  main.py      the whole program
```

The core of the code is this call:

```python
response = client.responses.create(
    model=MODEL,
    instructions=SYSTEM_PROMPT,
    input=question,
    reasoning={"effort": "none"},
)
```

`MODEL`, `SYSTEM_PROMPT`, and `question` are defined earlier in `main.py`. `question` comes from the command-line argument.

---

## The three things worth taking from this

**The key lives in the environment, not the code.** `OpenAI()` reads `OPENAI_API_KEY` on its own. You never pass it in, never assign it to a variable, never let it near a file you might commit.

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
   uv run --env-file .env series-1/00-model/main.py --raw "Why is the sky blue?"
  ```
2. Confirm that the terminal shows:
  - A raw response containing `output`, `usage`, `model`, and `status`.
  - The answer text after the raw response.
  - A final line with nonzero input and output token counts, `0 reasoning`, and `status=completed`.

---

## What breaks next

Try holding a conversation:

```sh
uv run --env-file .env series-1/00-model/main.py "My name is Patrick."
uv run --env-file .env series-1/00-model/main.py "What is my name?"
```

It has no idea. Two separate calls, and the model kept nothing between them.

```text
$ uv run --env-file .env series-1/00-model/main.py "What is my name?"
I don’t know your name—you haven’t shared it with me.
```

That's [Level 1](../01-conversation/LESSON.md).