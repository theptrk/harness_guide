# Series 1 with an Agent class

This is an alternative implementation of Series 1.

Level 0 introduces `Agent`, which holds one OpenAI client and handles one
message, and `Terminal`, which prints what the agent reports. Level 1 adds an
in-memory conversation to the same class. `main()` checks for the API key,
builds both, and hands the agent the client and the terminal's `emit` method:

```python
terminal = Terminal()
agent = Agent(OpenAI(), emit=terminal.emit)
```

`Agent` never prints, never reads the keyboard, never reads the environment,
and never exits the process. It talks to its host through functions that
`main()` passes in:

- From Level 0, `emit(event)` receives one dict per step of a turn: answer
  text and a `done` summary, and from Level 2 each tool call and tool result.
  `main()` passes `Terminal.emit`, which prints them.
- From Level 6, `approve(command)` is asked before any shell command runs.
  `main()` passes a function that prints the command and reads one line.
- From Level 7, the agent holds a `Browser` and has a `close()` method.

`main()` owns the terminal: the API key check, the prompt, the printing, the
approval question, `Ctrl-C`, `Ctrl-D`, and `agent.close()` on the way out.
The loop reads a line and passes it to the agent:

```python
while True:
    try:
        said = input("📝 you › ").strip()
    except EOFError:
        break
    if said:
        agent.handle_message(said)
```

Two agents in one process each have their own conversation, browser window,
and `emit` function. They share the module constants: the model name, the
system prompt, and the tool schemas.

Levels 1 through 9 keep that boundary. Tool handling, the agent loop, streaming,
files, shell commands, browser tools, and persistence arrive one at a time.
Level 9 hardens the complete persistent agent after its capabilities are in place.

Start with [Level 0](00-model/LESSON.md), then work through the numbered folders
in order.
