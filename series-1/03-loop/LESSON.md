# Level 3 — Build the agent loop

## What broke

Level 2 handles one tool request. Asking for two timezones produced:

```text
📝 you › Use get_current_time once for each city. What time is it in Tokyo and New York?

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
uv run --env-file .env series-1/03-loop/main.py --new
```

Ask for three current times:

```text
📝 you › Use get_current_time once for each city. What time is it in Tokyo, New York, and London?
```

This run produced:

```text
tool › get_current_time({"timezone":"Asia/Tokyo"})
tool ‹ {"timezone": "Asia/Tokyo", "datetime": "2026-08-18T08:54:14+09:00"}

tool › get_current_time({"timezone":"America/New_York"})
tool ‹ {"timezone": "America/New_York", "datetime": "2026-08-17T19:54:15-04:00"}

tool › get_current_time({"timezone":"Europe/London"})
tool ‹ {"timezone": "Europe/London", "datetime": "2026-08-18T00:54:17+01:00"}

🤖 model › - **Tokyo:** 8:54 AM, August 18
- **New York:** 7:54 PM, August 17
- **London:** 12:54 AM, August 18
    [4 model call(s) · 1078 in + 111 out]
```

Three model calls request tools. The fourth returns the answer.

---

## One CLI loop, one agent loop

The two loops have different owners and stop conditions.

`main()` owns the CLI session loop. It waits for terminal input and stops at `Ctrl-D`:

```python
while True:
    said = input("📝 you › ").strip()
    run_turn(client, chat_file_path, said)
```

The conversation does not depend on this loop. Its JSONL file remains after the process exits.

`run_turn()` owns one user request. It appends that request, then its agent loop continues until the model returns no `function_call`:

```python
def run_turn(client, chat_file_path, said):
    history.append_item(
        chat_file_path,
        {"role": "user", "content": said},
    )

    while True:
        input_items = history.get_input_items(chat_file_path)
        response = client.responses.create(
            # ...
            input=input_items,
            tools=TOOLS,
        )

        # Persist response.output.

        tool_call = next(
            (item for item in response.output if item.type == "function_call"),
            None,
        )
        if tool_call is None:
            answer = response.output_text
            break

        # Run the requested tool and append its result.
```

The agent loop does not decide in advance how many tool calls the request needs. Each model response decides whether there is another pass. The tool registry and name lookup are unchanged from Level 2; the loop is the new mechanism.

`run_turn()` names the boundary; it does not make the code interface-independent. It still prints tool activity and the answer. A later interface can expose that coupling as a concrete problem.

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

Reading the file every pass is what makes an unanswered call expensive. A `function_call` with no `function_call_output` for the same `call_id` is invalid model input, and the file is the input. One bad pair does not fail one request; it fails every request against that conversation from then on.

The loop appends the output even when the tool raised:

```python
except Exception as error:
    failure = error
    tool_result = f"{type(error).__name__}: {error}"

history.append_item(chat_file_path, {...})
if failure is not None:
    raise failure
```

`run_turn()` still gives up on the request. The model does not see the error and does not get to correct it. All this does is leave the record in a state the next question can be asked from. Level 4 is where the error goes back to the model.

---

## Done when

1. Start a new conversation:

   ```sh
   uv run --env-file .env series-1/03-loop/main.py --new
   ```

2. Enter `Use get_current_time once for each city. What time is it in Tokyo, New York, and London?`
3. Confirm that the terminal shows:
   - Three `tool › get_current_time` lines, one for each city.
   - Three matching `tool ‹` timestamps.
   - One final answer containing all three cities.
   - A usage line reporting `4 model call(s)`.
4. Enter `Use get_current_time with the timezone Mars/Olympus.` The turn ends with `call failed`.
5. Ask for the time in Tokyo again. It answers, and the earlier failure is still in the record.
6. Interrupt a turn with Ctrl-C while a tool line is on screen, then ask another question.
   It answers. `get_input_items()` left the unanswered call out of the request.

---

## What breaks next

The loop assumes every response is complete, every requested tool exists, every argument is valid, every function succeeds, and the model eventually stops requesting tools. None of those assumptions is enforced.

[Level 4](../04-harden/LESSON.md) handles those failures.
