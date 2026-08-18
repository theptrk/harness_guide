# Level 3 — Build the agent loop

## What broke

Level 2 handles one tool request. Asking for two timezones produced:

```text
you › What time is it in Tokyo and New York?

tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {"timezone": "Asia/Tokyo", "datetime": "2026-08-18T08:33:07+09:00"}

[stopped: model requested another get_current_time call]
```

The second model response contains another `function_call`. Level 2 checks for a function call only in the first response, so it stops.

Level 3 repeats the same sequence until the response contains no function call:

1. Call the model.
2. Persist `response.output`.
3. If it requested a tool, run the tool and persist the result.
4. Start again with the updated record.
5. Stop when the model returns a message instead.

That repeated sequence is the agent loop.

---

## Run it

```sh
uv run --env-file .env levels/03-loop/main.py --new
```

Ask for three current times:

```text
you › What time is it in Tokyo, New York, and London?
```

This run produced:

```text
tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {"timezone": "Asia/Tokyo", "datetime": "2026-08-18T08:54:14+09:00"}

tool › get_current_time({"timezone":"America/New_York"})
tool ‹ {"timezone": "America/New_York", "datetime": "2026-08-17T19:54:15-04:00"}

tool › get_current_time({"timezone":"Europe/London"})
tool ‹ {"timezone": "Europe/London", "datetime": "2026-08-18T00:54:17+01:00"}

››› - **Tokyo:** 8:54 AM, August 18
- **New York:** 7:54 PM, August 17
- **London:** 12:54 AM, August 18
    [4 model call(s) · 1078 in + 111 out]
```

Three model calls request tools. The fourth returns the answer.

---

## Two loops

`main.py` now contains two `while True` loops with different stop conditions.

The outer loop belongs to the conversation. It waits for another user message and stops at `Ctrl-D`:

```python
while True:
    said = input("you › ").strip()
    # ...
```

The inner loop belongs to one user request. It stops when the model returns no `function_call`:

```python
while True:
    input_items = history.get_input_items(chat_file_path)
    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=input_items,
        tools=TOOLS,
        parallel_tool_calls=False,
        reasoning={"effort": "none"},
    )

    for output_item in response.output:
        history.append_item(
            chat_file_path,
            output_item.model_dump(mode="json", exclude_none=True),
        )

    tool_call = next(
        (item for item in response.output if item.type == "function_call"),
        None,
    )
    if tool_call is None:
        answer = response.output_text
        break

    # Run the requested tool and append its result.
```

The inner loop does not decide in advance how many tool calls the request needs. Each model response decides whether there is another pass. The tool registry and name lookup are unchanged from Level 2; the loop is the new mechanism.

---

## Each pass uses the file

After a tool runs, its result is appended to the JSONL record:

```python
history.append_item(
    chat_file_path,
    {
        "type": "function_call_output",
        "call_id": tool_call.call_id,
        "output": tool_result,
    },
)
```

The next pass starts by calling `get_input_items()` again. The model receives the user request, every previous function call, and every result. Nothing in the agent loop carries a separate conversation list between passes.

---

## Done when

Ask for the current time in three timezones once. The program should:

1. Execute `get_current_time` three times with three model-selected timezone arguments.
2. Make one final model call after the third result.
3. Return one answer containing all three times.

---

## What breaks next

The loop assumes every requested tool exists, every argument is valid, every function succeeds, and the model eventually stops requesting tools. None of those assumptions is enforced.

[Level 4](../04-harden/LESSON.md) handles those failures.
