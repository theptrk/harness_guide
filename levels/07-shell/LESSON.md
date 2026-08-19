# Level 7 — Run a command

## What broke

Level 6 can create a Python script:

```text
you › Create hello.py with a print statement, then run it.
```

It can call `write_file`, but its tool list has no command runner. No Python
process starts, and the model receives no exit code, stdout, or stderr.

Level 7 adds one tool that runs a shell command and returns those values to the
model.

---

## Run it

```sh
uv run --env-file .env levels/07-shell/main.py --new
```

Create a small script:

```text
you › Use write_file to create hello.py with exactly:
print("hello from level 7")
```

The tool trace includes:

```text
tool › write_file({"path":"hello.py","content":"print(\"hello from level 7\")"})
tool ‹ {"path": "hello.py", "written": true, "characters": 27}
```

Now run it:

```text
you › Use run_command to run exactly: python hello.py
```

Before Python runs, the harness shows the exact command:

```text
[approval required]
Command: python hello.py
Run it? Type yes to continue [y/N]:
```

Type `yes`. The tool result contains:

```json
{
  "command": "python hello.py",
  "approved": true,
  "exit_code": 0,
  "stdout": "hello from level 7\n",
  "stderr": "",
  "timed_out": false,
  "error": null
}
```

The model receives that JSON and can report what the program printed.

The agent can now complete a basic coding loop:

```text
write a file → run it → inspect the result
```

The file tools provide the program; `run_command` executes it. Together they let
the agent create and run code inside the workspace.

---



## The new tool

The model sees one new definition:

```python
RUN_COMMAND_TOOL = {
    "type": "function",
    "name": "run_command",
    "description": (
        "Run one shell command from the agent workspace after the person approves it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact shell command to run.",
            }
        },
        "required": ["command"],
        "additionalProperties": False,
    },
    "strict": True,
}
```

`main.py` adds that definition and its Python function to the existing
registries:

```python
TOOLS = [TIME_TOOL] + file_tools.TOOLS + [shell_tools.RUN_COMMAND_TOOL]

TOOL_FUNCTIONS = {
    # ...
    "run_command": shell_tools.run_command,
}
```

The agent loop does not change. It already knows how to execute a selected
function and send its string result back as `function_call_output`.

---



## Python runs the command

After approval, `run_command()` calls:

```python
completed = subprocess.run(
    command,
    shell=True,
    cwd=workspace.resolve_path("."),
    env=environment,
    capture_output=True,
    text=True,
    timeout=COMMAND_TIMEOUT_SECONDS,
    check=False,
)
```

`cwd` makes relative paths start in:

```text
levels/07-shell/agent_workspace/
```

`capture_output=True` gives the harness `stdout` and `stderr`. `check=False`
keeps a nonzero exit code as ordinary tool data instead of raising an exception.
The model can inspect that result on its next pass.

The child environment removes `OPENAI_API_KEY` and `UV_ENV_FILE`. The command
does not need the model API key.

The timeout is 30 seconds. It bounds how long the harness waits; it does not
guarantee that every descendant of an approved shell command has stopped.

---



## The person still executes it

The model requests `run_command`. It does not call `subprocess.run()` itself.
The harness asks before every command:

```text
model requests command
→ harness shows exact command
→ person approves or denies
→ Python runs only an approved command
→ result goes back to the model
```

Only `y` and `yes`, ignoring case and surrounding spaces, approve. Pressing
Enter or typing anything else denies.

A denial is returned as tool data:

```json
{
  "command": "python hello.py",
  "approved": false,
  "exit_code": null,
  "stdout": "",
  "stderr": "",
  "timed_out": false,
  "error": "Denied by user"
}
```

The model can explain that the command did not run. The system prompt tells it
not to request the same denied command again unless you explicitly ask.

Approval is not sandboxing. The command starts in `agent_workspace`, but
`shell=True` gives an approved command the permissions of your Python process.
Level 15 adds an operating-system boundary.

---



## Done when

1. Start a new Level 7 conversation:
  ```sh
   uv run --env-file .env levels/07-shell/main.py --new
  ```
2. Use `write_file` to create `hello.py` containing
  `print("hello from level 7")`.
3. Enter `Use run_command to run exactly: python hello.py`.
4. Type `yes`. Confirm that the result has exit code `0`, empty `stderr`, and
  `hello from level 7` in `stdout`.
5. Request the same command again and press Enter at the approval prompt.
6. Confirm that the second result has `"approved": false`, a null exit code,
  and no output.

---



## What the next level improves

Start a new Level 7 conversation:

```sh
uv run --env-file .env levels/07-shell/main.py --new
```

Enter this as one request:

```text
Use write_file to create random-button.html with exactly:

<!doctype html>
<button id="value" onclick="this.textContent = Math.random()">Click me</button>

Then open the rendered page in a browser, click the button once, and report the
exact number displayed on the button. Do not infer a value from the source.
```

You may get an answer like this:

```text
model › Created `random-button.html` exactly as requested. I can’t open a rendered browser page or click the button in this environment, so I can’t report the generated number.
```

Level 7 can technically complete this task through `run_command` if it had the reasoning capability and could plan the multi step process to write and run a browser automation script to do it. The shell provides the underlying capability, not a browser interface. A more capable or more deliberate model may recognize that route; another model may stop because no browser tool was named.

Level 8 gives the model three browser tools: `open_page`, `read_page`, and
`click`. You install Chromium once. All three tools operate on the same page and
return its rendered state without requiring the model to write a browser script.