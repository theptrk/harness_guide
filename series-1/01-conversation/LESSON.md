# Level 1 — Hold a conversation

## What broke

At the end of Level 0 you ran this:

```sh
uv run --env-file .env series-1/00-model/main.py "My name is Patrick."
uv run --env-file .env series-1/00-model/main.py "What is my name?"
```

It has no idea. The model kept nothing between the two calls, because a model keeps nothing between any two calls — ever. If a conversation is going to exist, you are the one who has to hold it.

---

## Run it

```sh
uv run --env-file .env series-1/01-conversation/main.py --new
```

You get a prompt. Tell it your name, then ask what your name is:

```
[2026-08-17-114420-278577.jsonl · 0 messages so far]
Ctrl-D to leave. Nothing is lost when you do.

📝 you › My name is Patrick.

🤖 model › Hi Patrick, good to meet you.
    [24 in + 8 out  0 reasoning]

📝 you › What is my name?

🤖 model › Your name is Patrick.
    [41 in + 6 out  0 reasoning]
```

Look at the token counts. The second call sent 41 input tokens for a five-word
question, because it sent the whole conversation again. Each new message makes
the conversation longer, so the next call sends more input tokens. Eventually
the conversation becomes too large to send in full; the context-selection
chapter in [Advanced Agent Concepts](../../roadmap-intermediate.md) handles that
by trimming the history.

Press `Ctrl-D`, then continue without `--new`:

```sh
uv run --env-file .env series-1/01-conversation/main.py
```

Ask for your name again. On startup, the code finds the latest chat file and sends its messages with your new question. The model can answer because your program restored the conversation, not because the model remembered it.

This is the path from the file to the request:

```python
chat_file_path = history.latest_chat() or history.new_chat()
messages = history.get_messages(chat_file_path)

response = client.responses.create(
    # ...
    input=messages,
)
```

`latest_chat()` picks the newest conversation file. `get_messages()` reads that file and builds the list sent to the model.

To start a clean one:

```sh
uv run --env-file .env series-1/01-conversation/main.py --new
```

---

## What's in here

```
series-1/01-conversation/
  LESSON.md
  main.py       the prompt loop
  history.py    NEW — the record
  chats/        made when you first run it, gitignored
```

Files under `chats/` are named for when the conversation started: `YYYY-MM-DD-HHMMSS-ffffff.jsonl`. The last six digits are microseconds, so two `--new` runs do not reuse the same file.

`main.py` now repeats the prompt and model call in a `while` loop. The new `history.py` module persists each message and rebuilds the input for the next call.

---

## The shape of it

Every message gets appended to a file the moment it happens — yours before the call, the model's after. One JSON object per line:

```sh
cat series-1/01-conversation/chats/*.jsonl
```

```
{"role": "user", "content": "My name is Patrick.", "at": "2026-08-17T11:44:20.278577"}
{"role": "assistant", "content": "Hi Patrick, good to meet you.", "at": "...", "phase": "final_answer"}
```

`get_messages()` converts those lines into the list sent to the model. It leaves `at` on disk and preserves `phase` on assistant messages.

The file is the record; the list is rebuilt from it for each call. During one run, an in-memory list would behave the same. It would disappear when the program exits, so it could not restore the conversation on restart. Later, `get_messages()` can return a trimmed history without deleting the full record.

The user line is written before the call. If the call fails, or you hit Ctrl-C during it, `drop_last` takes that line back off — otherwise the next restart would send a question that never got an answer.

[`phase`](https://developers.openai.com/api/docs/guides/reasoning#phase-parameter) is `final_answer` or `commentary`. The API uses it to mark the message as the answer versus a mid-turn remark. For this model family, follow-up calls are supposed to send it back on every assistant message. Dropping it can make later turns worse.

---

## Optional checks

**Watch it rewind.** Delete the last two lines of a conversation and it forgets the last exchange, because the file is the only thing that remembers:

1. The program prints the chat filename when it starts. Open that file under `series-1/01-conversation/chats/`.
2. Delete its last two lines: your last message and the assistant's reply.
3. Save the file.

Start the program again and the last thing you talked about never happened.

**Prove the two conversations are separate.** Tell one your name, start a new one, and ask:

> ```sh
> uv run --env-file .env series-1/01-conversation/main.py --new
> ```

It doesn't know. List the chat files, then open the older one and confirm that it still contains the first exchange:

```sh
ls -t series-1/01-conversation/chats/
```

**Count the record.** Have a ten-turn conversation, then:

```sh
wc -l series-1/01-conversation/chats/*.jsonl
```

The last call sent every line that existed before that call. Earlier calls sent the shorter record that existed at the time.

---

## Why start a new conversation?

By default, the program reopens the latest chat file and sends its messages on the next call. Use `--new` before testing unrelated behavior. Otherwise, old questions, instructions, and answers remain in the input and can affect later responses. Starting a new conversation creates an empty chat file; it does not delete the old one.

---

## Done when

1. Start a new conversation:

   ```sh
   uv run --env-file .env series-1/01-conversation/main.py --new
   ```

2. Enter `My name is Patrick.` Wait for the reply, then press `Ctrl-D`.
3. Continue the latest conversation by excluding `--new`:

   ```sh
   uv run --env-file .env series-1/01-conversation/main.py
   ```

4. Enter `What is my name?` Confirm that it answers `Patrick`, then press `Ctrl-D`.
5. Start a new conversation:

   ```sh
   uv run --env-file .env series-1/01-conversation/main.py --new
   ```

6. Confirm that the header says `0 messages so far`.
7. Enter `What is my name?` Confirm that it says it does not know.

---

## What breaks next

Run Level 1 with a new conversation:

```sh
uv run --env-file .env series-1/01-conversation/main.py --new
```

Then ask for the current time:

```text
📝 you › whats the time in tokyo

🤖 model › Tokyo time is **Japan Standard Time (JST, UTC+9)**. I can’t access a live clock, but you can check your device’s world clock for the current exact time.
```

The model identifies the missing capability: it has no live clock. [Level 2](../02-tool/LESSON.md) gives it one.