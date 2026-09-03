# Level 5 — Give it files

## What broke

At the end of Level 4, the model returned:

```text
📝 you › Create profile.md. Record that my name is Patrick and my favorite fruit is strawberries.

🤖 model › I can’t create files directly here, but `profile.md` should contain:

# Profile

- Name: Patrick
- Favorite fruit: Strawberries
```

It produced the right document as answer text, but no file existed.

Level 5 adds four tools:

- `list_files` lists one directory.
- `read_file` reads a line window from one UTF-8 text file.
- `write_file` creates or replaces one UTF-8 text file.
- `edit_file` replaces one exact block of text.

It also changes the system prompt:

```python
SYSTEM_PROMPT = (
    "You are a concise coding assistant. Use the file tools to inspect and modify "
    "files in your workspace. Do not claim a file changed unless a tool succeeded."
)
```

The prompt tells the model when to use the new capability. The tool result remains the evidence that a file operation happened.

Every operation is confined to:

```text
series-1-agent-class/05-files/agent_workspace/
```

`agent_workspace` is an ordinary directory beside this level's code. The program
creates it when a file tool first runs. Tool paths are relative to it, so
`profile.md` means `series-1-agent-class/05-files/agent_workspace/profile.md`. Each level has
its own `agent_workspace`.

---

## Run it

```sh
uv run --env-file .env series-1-agent-class/05-files/main.py
```

The startup text names the only directory the tools can access:

```text
[workspace: series-1-agent-class/05-files/agent_workspace]
```

Ask:

```text
📝 you › Use write_file to create profile.md with exactly this content:
# Profile

- Name: Patrick
- Favorite fruit: strawberries

After the tool succeeds, answer only: Created profile.md.
```

The tool trace should include:

```text
tool › write_file({"path":"profile.md","content":"# Profile\n\n- Name: Patrick\n- Favorite fruit: strawberries"})
tool ‹ {
  "path": "profile.md",
  "written": true,
  "characters": ...
}
```

The `content` argument shows exactly what the model asked Python to write. Compare it with the text in your request before continuing.

Press `Ctrl-D` and start a separate conversation:

```sh
uv run --env-file .env series-1-agent-class/05-files/main.py
```

First ask without letting it inspect the workspace:

```text
📝 you › Without using tools, what is my name and favorite fruit?
```

The new conversation does not contain the creation request, so the model should say it does not know. Now direct it to the file:

```text
📝 you › Use read_file to read profile.md. What is my name and favorite fruit?
```

The answer should now contain `Patrick` and `strawberries`. The tool call includes
`offset` and `limit` because those fields are required. `profile.md` is shorter
than 200 lines, so `truncated` is false.

Update one fact without replacing the whole document:

```text
📝 you › Use edit_file to change my favorite fruit from strawberries to mangoes.
```

Verify the edit:

```text
📝 you › Use read_file to read profile.md. What is my favorite fruit now?
```

`profile.md` remains in `agent_workspace/` across conversations. The model knows its contents only after a tool call reads it.

---

## From a tool request to the filesystem

The CLI and agent loops are the same as Level 4. `main()` still calls only
`agent.handle_message(said)`. Level 5 adds entries to the tool list and function
registry used by the clock:

Levels 2 through 5 wrote the clock schema inline in a list named `TOOLS`. This
level names that schema `TIME_TOOL` so it can sit next to `file_tools.TOOLS`.

```python
TOOLS = [TIME_TOOL] + file_tools.TOOLS

TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
    "list_files": file_tools.list_files,
    "read_file": file_tools.read_file,
    "write_file": file_tools.write_file,
    "edit_file": file_tools.edit_file,
}
```

Each key in `TOOL_FUNCTIONS` is a name the model can return. Each value is the Python function that name selects. The functions are not called when this dictionary is created; `self._run_tool()` calls the selected function later.

A write follows this path:

```text
function_call named write_file
→ self._run_tool() parses its JSON arguments
→ file_tools.write_file(path, content)
→ workspace.write_file(path, content)
→ agent_workspace/path
```

The adapter is small:

```python
def write_file(path: str, content: str) -> str:
    workspace.write_file(path, content)
    return json.dumps(
        {
            "path": path,
            "written": True,
            "characters": len(content),
        }
    )
```

`file_tools.py` contains the schemas and converts Python results to JSON strings for `function_call_output`. `workspace.py` contains the calls to `Path.read_text()`, `Path.write_text()`, and `Path.iterdir()`.

All four adapters use the same workspace module, so none can omit the path check. Only that module knows the files are local `Path` objects. A later implementation can replace it without changing the schemas or agent loop.

---

## Resolve the path before using it

Without a containment check, this model-selected call could overwrite a repository file:

```python
write_file("../main.py", "replacement")
```

Tool arguments are model output. A requested path may contain `..`, may be absolute, or may pass through a symbolic link.

All four operations call `resolve_path()`:

```python
ROOT = Path(__file__).parent / "agent_workspace"

def resolve_path(path: str) -> Path:
    if ROOT.is_symlink():
        raise WorkspacePathError("agent_workspace must not be a symbolic link")
    ROOT.mkdir(exist_ok=True)
    resolved_root = ROOT.resolve()
    resolved = (resolved_root / path).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise WorkspacePathError(f"path leaves the agent workspace: {path}")
    return resolved
```

The workspace root itself cannot be a symbolic link. `resolve()` then computes the actual absolute path before the containment check. That handles:

```text
notes/todo.txt       → inside the workspace
../main.py           → outside; rejected
/etc/passwd          → outside; rejected
outside-link/file    → rejected if outside-link points outside
```

Checking the string for `".."` would not handle absolute paths or symbolic links. Checking that the resolved path is relative to the resolved root handles all three.

This is an application-level boundary, not an operating-system sandbox. Code in `workspace.py` still runs with the permissions of your Python process.

`main.py` is one directory above `agent_workspace/`. Try to read it:

```text
📝 you › Use read_file to read ../main.py.
```

Without the containment check, `..` would move out of the workspace and expose
the program's source file. The tool should instead return a
`WorkspacePathError`.

Level 5 also makes expected tool failures recoverable. `_run_tool()` catches a
tool exception and returns its type and message as tool output, so the model can
explain a rejected path instead of ending the turn:

```python
def _run_tool(self, tool_call) -> str:
    try:
        arguments = json.loads(tool_call.arguments)
        tool_function = TOOL_FUNCTIONS.get(tool_call.name)
        if tool_function is None:
            raise LookupError(f"unknown tool: {tool_call.name}")
        return tool_function(**arguments)
    except Exception as error:
        return f"{type(error).__name__}: {error}"
```

---

## Write a file or edit one block

`write_file` receives the complete new content and replaces the file. That is appropriate when creating a short file.

For an existing file, `edit_file` receives:

```json
{
  "path": "profile.md",
  "old_text": "- Favorite fruit: strawberries",
  "new_text": "- Favorite fruit: mangoes"
}
```

`workspace.edit_file()` requires `old_text` to occur exactly once:

```python
matches = content.count(old_text)
if matches == 0:
    raise ValueError("old_text was not found")
if matches > 1:
    raise ValueError(f"old_text matched {matches} places; provide more context")
```

Zero matches usually means the model read an older version or copied the text incorrectly. Multiple matches mean the request does not identify one location. Both become tool errors, so the model can read the file again or provide more surrounding text.

Replacing one exact block requires less model-generated argument text than sending the complete file to `write_file`, and it avoids changing unrelated lines.

> This is a minimal editor. A production version can report the line numbers of ambiguous matches, support an explicit replace-all operation, and reject stale edits with a version check before an atomic write. These features change how files are edited; they do not change how the model requests a tool or how the agent loop handles its result.

`Agent.handle_message()` commits conversation items only after the model returns a final answer. It cannot undo a tool. If `write_file` succeeds and a later model call is interrupted or fails, the file change remains while that turn is absent from chat history. Reversing tool side effects requires a separate transaction or recovery design.

---

## The result is a window, not the file

`read_file` does not return the file. It returns a JSON window of at most 200
lines. That window is what the terminal prints, what the in-memory item list stores, and
what the next model call receives.

The model sees this definition:

```python
{
    "type": "function",
    "name": "read_file",
    "description": (
        "Read a UTF-8 text file from the agent workspace. "
        "Returns JSON with path, offset, lines, total_lines, and truncated. "
        "Each entry in lines is one file line, prefixed with its 1-based line number. "
        "If truncated is true, call again with offset set to the next unread line."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The file path relative to the workspace.",
            },
            "offset": {
                "type": "integer",
                "description": "1-based first line to return. Use 1 unless you need a later window.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to return. Use 200 unless you need a smaller window. Hard cap 200.",
            },
        },
        "required": ["path", "offset", "limit"],
        "additionalProperties": False,
    },
    "strict": True,
}
```

`offset` is the 1-based first line. `limit` is how many lines to return, capped
at `READ_LINE_LIMIT` (200) in `workspace.py`. The adapter passes those arguments
through:

```python
def read_file(path: str, offset: int, limit: int) -> str:
    return json.dumps(workspace.read_file(path, offset, limit))
```

The result includes `total_lines` and `truncated`. If `truncated` is true, the
file continues; call again with `offset` set to the next unread line.

`profile.md` is four lines, so the first window is the whole file:

```json
{
  "path": "profile.md",
  "offset": 1,
  "lines": [
    "1|# Profile",
    "2|",
    "3|- Name: Patrick",
    "4|- Favorite fruit: strawberries"
  ],
  "total_lines": 4,
  "truncated": false
}
```

Line numbers belong in the returned text so a later call can set `offset`
without counting. Repeated windows still fill the conversation. The
[context-selection chapter](../../roadmap-intermediate.md) decides which past
items are sent when the history itself is too large.

`edit_file` still reads the complete file in Python so it can require a unique
`old_text`. That full text is not sent to the model.

---

## A profile file is the simplest memory strategy

In LLM chatbots, *memory* means that information from earlier interactions is retained and used in future chats.

`profile.md` provides retention: the facts remain on disk after the first conversation. In the next conversation, `read_file` retrieves those facts and adds them to model input so they can affect its answer.

The retrieval is manual in this level: the user explicitly asks the model to read the file. A later memory system decides when to retrieve stored information without requiring the user to name the file.

---

## Done when

1. Start Level 5:

   ```sh
   uv run --env-file .env series-1-agent-class/05-files/main.py
   ```

2. Enter:

   ```text
   Use write_file to create profile.md with exactly this content:
   # Profile

   - Name: Patrick
   - Favorite fruit: strawberries

   After the tool succeeds, answer only: Created profile.md.
   ```

3. Confirm that the `write_file` call contains the heading and both facts exactly as supplied.
4. Enter `Use list_files to list the workspace root.` Confirm that its result includes `profile.md`.
5. Press `Ctrl-D`, then start a new conversation:

   ```sh
   uv run --env-file .env series-1-agent-class/05-files/main.py
   ```

6. Confirm that the header reports `0 input items so far`.
7. Enter:

   ```text
   Without using tools, what is my name and favorite fruit? If they are not in this conversation, say you do not know.
   ```

8. Confirm that the model says it does not know either fact.
9. Enter `Use read_file to read profile.md. What is my name and favorite fruit?` Confirm that it answers `Patrick` and `strawberries`.
10. Enter `Use edit_file to change my favorite fruit from strawberries to mangoes.`
11. Enter `Use read_file to read profile.md. What is my favorite fruit now?` Confirm that it answers `mangoes`.
12. Enter `Use read_file to read ../main.py.` Confirm that the tool result contains `"type": "WorkspacePathError"` and does not contain the file contents.

---

## Try this

`profile.md` never hits the line cap. Write a file with more than 200 lines,
then read it with `offset` 1 and `limit` 200. The result should have
`"truncated": true` and `"total_lines"` greater than 200. A second read with
`offset` 201 returns the rest.

---

## What breaks next

Ask it to write a Python script that converts `profile.md` to JSON. It can create the script but cannot run it, inspect the output, or correct an error.

Level 6 will add shell access and an approval gate.
