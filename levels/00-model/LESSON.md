# Level 0 — Call a model

You send a question to a model and print what comes back. One file, one dependency, no framework.

This is the only level with nothing before it, so there's no "here's what broke" to open with. Everything after this one starts with something that doesn't work.

---

You need `uv` installed and a key in `.env` — that's the [Setup section of the README](../../README.md#setup), and it's the only setup in the whole course.

---

## Run it

The call returns one object. Two ways to read it:

- The JSON. What came over the wire. Every field in it is in the HTTP API. `--raw` prints this.
- Helper properties the OpenAI Python SDK adds on the parsed object. They are not in the JSON. `response.output_text` is one.

Start with `--raw`:

```sh
uv run --env-file .env levels/00-model/main.py --raw "why is the sky blue"
```

That flag runs:

```python
if raw:
    print(response.model_dump_json(indent=2))
```

A truncated sample:

```json
{
  "id": "resp_088b100b6ca1b13c006a8363196528819b8164cb32fcd8be0a",
  "created_at": 1786995481.0,
  ... 
  "instructions": "You are a concise assistant. Answer in a few sentences.",
  "model": "gpt-5.6-luna",
  "object": "response",
  "output": [
    {
      "id": "msg_088b100b6ca1b13c006a83631aa1b8819b91a85f84570bd549",
      "content": [
        {
          "annotations": [],
          "text": "Sunlight contains many colors. As it passes through Earth’s atmosphere, tiny air molecules scatter shorter wavelengths—especially blue—more strongly than longer red wavelengths. This scattered blue light reaches our eyes from all directions, making the sky appear blue.",
          "type": "output_text",
          "logprobs": []
        }
      ],
      "role": "assistant",
      "status": "completed",
      "type": "message",
      "phase": "final_answer"
    }
  ],
  ...
  "completed_at": 1786995483.0,
  "usage": {
    "input_tokens": 27,
    "input_tokens_details": {
      "cache_write_tokens": 0,
      "cached_tokens": 0
    },
    "output_tokens": 52,
    "output_tokens_details": {
      "reasoning_tokens": 0
    },
    "total_tokens": 79
  },
  ...
}
```

Read it against the [Responses API `create` docs](https://developers.openai.com/api/reference/python/resources/responses/methods/create). Find these in that JSON:

| In the JSON | What it's for |
| --- | --- |
| `output[0].content[0].text` | the answer |
| `usage.input_tokens`, `usage.output_tokens` | what you were billed for |
| `usage.output_tokens_details.reasoning_tokens` | tokens spent thinking before the visible answer. Billed as output. Not in the text. |
| `model` | which model served the request. Price this string. |

`reasoning_tokens` is inside `output_tokens`. The default is to think (`medium`). The sample shows `0` because `main.py` sets `reasoning={"effort": "none"}`. A later level that needs the thinking changes that one argument.

`response.usage.input_tokens`, `response.usage.output_tokens_details.reasoning_tokens`, and `response.model` are JSON fields, accessed as attributes.

`response.output_text` is a helper. Search the JSON for a top-level `output_text` — it isn't there. The SDK walks `output`, keeps message items, keeps blocks whose type is `output_text`, and joins the strings. That walk is `output[0].content[0].text` on the payload above.

In `openai-python` **v3.2.0** it's [this loop in `response.py`](https://github.com/openai/openai-python/blob/v3.2.0/src/openai/types/responses/response.py#L481-L493). Read it at the version you have; library code moves:

```sh
uv run python -c "import inspect; from openai.types.responses import Response; print(inspect.getsource(Response.output_text.fget))"
```

It concatenates, and it skips anything that isn't a text block. Today `output` holds one message, so neither matters. From Level 2 it holds other kinds of item too, and `output_text` will hand you the text while ignoring them.

The `model` row is the one you price. `main.py` asks for `gpt-5.6-luna` by name. `gpt-5.6` is an alias that currently points at Sol, which costs more. Aliases move. The code names the model you meant.

`phase` on the message is `final_answer` here. Level 1 has to send that field back; ignoring it is a silent quality bug on this model family.

Now run it without the flag:

```sh
uv run --env-file .env levels/00-model/main.py "why is the sky blue"
```

A few sentences about Rayleigh scattering, then:

```
[27 in + 52 out tokens  0 reasoning  $0.000000  status=completed]
```

Same call. The difference is only how much of the response you chose to look at.

The `--env-file .env` is what loads your key. Forget it and you get:

```
OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.
```

If you'd rather not type the flag every time, set it once in your shell:

```sh
export UV_ENV_FILE=.env
```

Then `uv run levels/00-model/main.py "..."` is enough.

---



## What's in here

```
levels/00-model/
  LESSON.md    this file
  main.py      the whole program
```

The core of the code is this call

```python
    # Reads OPENAI_API_KEY from the environment. The key is never in this file.
    client = OpenAI()

    response = client.responses.create(
        model="some-model-like-gpt5.6",
        instructions="You are an AI bot called InfinityBot",  # applies to every question
        input="Why is the sky blue",              # this question
        reasoning={"effort": "none"},
    )
```

---



## The three things worth taking from this

**The key lives in the environment, not the code.** `OpenAI()` reads `OPENAI_API_KEY` on its own. You never pass it in, never assign it to a variable, never let it near a file you might commit.

**You send two pieces of text, and they have different jobs.** `instructions` is the system prompt — it applies to every question you'll ever ask. `input` is this one question. Level 11 is about changing the first one and measuring what happens.

**Tokens are the unit of everything.** Not characters, not words. The response tells you how many went in and how many came out, and that number is what you're billed on and what fills up the context window later. Every cost and capacity problem in this course is a token problem.

---



## Try these

**Make the cost line true.** Look up the price for `gpt-5.6-luna` at [https://platform.openai.com/docs/pricing](https://platform.openai.com/docs/pricing) and put the two numbers into `PRICE_IN` and `PRICE_OUT` at the top of `main.py`. They're per million tokens. Then run it again and see what a question actually costs you.

**See what an alias does.** Set `MODEL` to `"gpt-5.6"`, run with `--raw`, and look at `model`. You should see `gpt-5.6-sol`. Then put it back.

**Change the system prompt.** Set `SYSTEM_PROMPT` to `"Answer in exactly one word."` and ask the same question. Then try `"You are a pirate."` The system prompt is the largest single influence you have on behaviour, and it's one string.

---



## Done when

You can print an answer, the token counts, and a cost that isn't zero — because you looked the price up.

---



## What breaks next

Try holding a conversation:

```sh
uv run --env-file .env levels/00-model/main.py "My name is Patrick."
uv run --env-file .env levels/00-model/main.py "What is my name?"
```

It has no idea. Two separate calls, and the model kept nothing between them.

```bash
uv run levels/00-model/main.py "What is my name?"
> I don’t know your name—you haven’t shared it with me.
```

That's [Level 1](../01-conversation/LESSON.md).