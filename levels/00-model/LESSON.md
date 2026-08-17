# Level 0 — Call a model

You send a question to a model and print what comes back. One file, one dependency, no framework.

This is the only level with nothing before it, so there's no "here's what broke" to open with. Everything after this one starts with something that doesn't work.

---

You need `uv` installed and a key in `.env` — that's the [Setup section of the README](../../README.md#setup), and it's the only setup in the whole course.

---

## Run it

Start with `--raw`, which prints the whole response object before anything is pulled out of it:

```sh
uv run --env-file .env levels/00-model/main.py --raw "why is the sky blue"
```

Specifically the code runs:

```python
if raw:
    print(response.model_dump_json(indent=2))
```

That JSON is what actually came back over the wire. Note the message lives in the first object inside the "output" list.

Heres a truncated sample of the JSON:

```json
{
  "id": "resp_088b100b6ca1b13c006a8363196528819b8164cb32fcd8be0a",
  "created_at": 1786995481.0,
  ... 
  "instructions": "You are a concise assistant. Answer in a few sentences.",
  "model": "gpt-5.6-sol",
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

Read it against the reference — [the Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create) `create` [docs](https://developers.openai.com/api/reference/python/resources/responses/methods/create) — and find these three:


| Path                                        | What it's for                                                    |
| ------------------------------------------- | ---------------------------------------------------------------- |
| `output[0].content[0].text`                 | the answer                                                       |
| `usage.input_tokens`, `usage.output_tokens` | what you were billed for                                         |
| `model`                                     | which model actually served it, not always the one you asked for |


```json
{
  ... 
  "model": "gpt-5.6-sol",
  "output": [
    {
      ... 
      "content": [
        {
          ... 
          "text": "The sky is blue because...",
    }
  ],
  ...
  "usage": {
    "input_tokens": 27,
  },
}
```

Those paths work in both places. The JSON above and the Python object are the same shape, field for field, so `response.usage.input_tokens` in the code is reading the field you just found in the payload. There is exactly one exception to that, and it's the answer itself.

**The answer is four levels deep.** `output` is a list of items. The first item is a message, its `content` is a list of blocks, and the block with `"type": "output_text"` holds the text. If you called this API with `curl`, that path is what you would have to walk yourself.

`main.py` doesn't walk it — it says `response.output_text`. **That is not a field in the response.** It's a convenience property that the Python library adds on top of the parsed object, and it exists only in that library: not in the JSON, not in the HTTP API, not necessarily in the SDK for another language. Search your raw output for a top-level `output_text` and you won't find one.

It's worth reading, because it's short. In `openai-python` **v3.2.0** it's [a `for` loop in](https://github.com/openai/openai-python/blob/v3.2.0/src/openai/types/responses/response.py#L481-L493) `response.py` — over `output`, keeping message items, keeping their `output_text` blocks, joining the strings.

Read it at the version you have rather than trusting the link, since this is library code and it can change under you:

```sh
uv run python -c "import inspect; from openai.types.responses import Response; print(inspect.getsource(Response.output_text.fget))"
```

Two things to take from it. It **concatenates** — several message items become one string. And it **filters** — anything that isn't a text block is skipped without a word. Today `output` holds exactly one message, so neither matters. From Level 2 it holds other kinds of item too, and `output_text` will quietly hand you the text while ignoring them.

The `model` row matters more than it looks, too. The sample above asked for `gpt-5.6` and was served `gpt-5.6-sol` — so if you price the model you asked for, your cost line is wrong.

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

gpt-5.6 can spend output tokens thinking before it writes the answer. Those tokens are `usage.output_tokens_details.reasoning_tokens`. They are billed as output. They are not in the text you print. The default is to think (`medium`). This course sets `reasoning={"effort": "none"}` so the token line is about the answer you see. A later level that needs the thinking changes that one argument.

---



## Try these

**Make the cost line true.** Look up the price for `gpt-5.6` at [https://platform.openai.com/docs/pricing](https://platform.openai.com/docs/pricing) and put the two numbers into `PRICE_IN` and `PRICE_OUT` at the top of `main.py`. They're per million tokens. Then run it again and see what a question actually costs you.

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