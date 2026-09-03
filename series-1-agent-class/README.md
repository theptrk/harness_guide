# Series 1 with an Agent class

This is an alternative implementation of Series 1.

Level 0 introduces `Agent`, which owns one OpenAI client and handles one
message. Level 1 adds an in-memory conversation to the same class:

```python
agent = Agent()
```

The terminal loop remains visible in `main()` and knows only how to read a line
and pass it to the agent:

```python
while True:
    try:
        said = input("📝 you › ").strip()
    except EOFError:
        break
    if said:
        agent.handle_message(said)
```

Levels 1 through 9 keep that boundary. Tool handling, the agent loop, streaming,
files, shell commands, browser tools, and persistence arrive one at a time.
Level 9 hardens the complete persistent agent after its capabilities are in place.

Start with [Level 0](00-model/LESSON.md), then work through the numbered folders
in order.
