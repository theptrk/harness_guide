# Level 1 — Hold a conversation

## What broke

At the end of Level 0 you ran this:

```sh
uv run --env-file .env levels/00-model/main.py "My name is Patrick."
uv run --env-file .env levels/00-model/main.py "What is my name?"
```

It has no idea. The model kept nothing between the two calls, because a model keeps nothing between any two calls — ever. If a conversation is going to exist, you are the one who has to hold it.

---

## Run it

```sh
uv run --env-file .env levels/01-conversation/main.py
```

You get a prompt. Tell it your name, then ask what your name is:

```
[2026-08-17-114420.jsonl · 0 messages so far]
Ctrl-D to leave. Nothing is lost when you do.

you › My name is Patrick.

››› Hi Patrick, good to meet you.
    [24 in + 8 out]

you › What is my name?

››› Your name is Patrick.
    [41 in + 6 out]
```

Look at the token counts. The second call sent 41 input tokens for a five-word question, because it sent the whole conversation again. It always will. That number only goes up, which is the entire subject of Level 10.

Press `Ctrl-D`, run the same command again, and ask again. It still knows.

To start a clean one:

```sh
uv run --env-file .env levels/01-conversation/main.py --new
```

---

## What's in here

```
levels/01-conversation/
  LESSON.md
  main.py       the prompt loop
  history.py    NEW — the record
  chats/        made when you first run it, gitignored
```

`main.py` grew a `while` loop. The interesting file is `history.py`, which is new.

---

## The shape of it

Every message gets appended to a file the moment it happens — yours before the call, the model's after. One JSON object per line:

```sh
cat levels/01-conversation/chats/*.jsonl
```

```
{"role": "user", "content": "My name is Patrick.", "at": "2026-08-17T11:44:20.278577"}
{"role": "assistant", "content": "Hi Patrick, good to meet you.", "at": "...", "phase": "final_answer"}
```

Then, when it's time to call the model, the list of messages is **built from that file**:

```python
input=history.messages(chat)
```

Not from a variable you've been carrying around. That's the whole design, and today it buys you nothing — an in-memory list would behave identically. Level 10 is where it pays: you start sending the model a shortened version of the conversation, and if the list *is* the conversation, shortening it destroys the only copy.

Note what `messages()` does and doesn't do. It reads the file and returns a list. `at` stays on disk. `phase` is copied onto assistant messages when the file has it. At Level 10 this function will start from the newest summary and read forward instead. Nothing that calls it will change.

The user line is written before the call. If the call fails, or you hit Ctrl-C during it, `drop_last` takes that line back off — otherwise the next restart would send a question that never got an answer.

`phase` is `final_answer` or `commentary`. The API uses it to mark the message as the answer versus a mid-turn remark. For this model family, follow-up calls are supposed to send it back on every assistant message. Dropping it can make later turns worse.

---

## Try these

**Watch it rewind.** Delete the last two lines of a conversation and it forgets the last exchange, because the file is the only thing that remembers:

```sh
CHAT=$(ls -t levels/01-conversation/chats/*.jsonl | head -1)
sed -i '' -e '$d' "$CHAT" && sed -i '' -e '$d' "$CHAT"
```

(Two passes on purpose — a single `sed -e '$d' -e '$d'` only deletes one line, since both commands run against the same last line.)

Start the program again and the last thing you talked about never happened.

**Prove the two conversations are separate.** Tell one your name, start a new one, and ask:

```sh
uv run --env-file .env levels/01-conversation/main.py --new
```

It doesn't know. The old file still does:

```sh
ls -t levels/01-conversation/chats/
```

**Count what it's costing you.** Have a ten-turn conversation, then:

```sh
wc -l levels/01-conversation/chats/*.jsonl
```

Every one of those lines was sent on the last call, and on every call before it.

---

## Why bother with a boundary

You could have one endless conversation. Don't. The next four levels are experiments — Level 4 asks you to break your own tools on purpose and watch it recover. Without `--new`, all of that wreckage rides along in the context of everything you do afterward, and you'll spend an evening debugging behaviour that's coming from a test you ran two levels ago.

---

## What the API will offer you, and why we're not taking it

The Responses API can hold the conversation server-side. You send a `previous_response_id` and it stitches the history together for you, and Level 1 becomes about four lines long.

We're not using it. The point of this level is understanding what's being stitched. Once you've built it, using the built-in version later is a decision rather than a default — and by Level 10 you'll need the record to be yours anyway.

---

## Done when

Three things are true:

1. You quit mid-conversation, restart, and it picks up where you left off.
2. You start a new conversation and it doesn't know your name, while the old file still does.
3. You delete the last two lines of a file and that conversation rewinds.

---

## What breaks next

Ask it something it can't know:

```
you › What time is it in Tokyo?
you › What's 47281 × 9912?
```

Both answers arrive with total confidence. Both are wrong. It has no clock and it isn't doing arithmetic — it's producing text that looks like an answer.

That's [Level 2](../02-tool/LESSON.md).
