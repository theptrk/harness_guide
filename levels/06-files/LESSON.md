# Level 6 — Give it files

## What broke

At the end of Level 5, the model returned:

```text
📝 you › Create profile.md. Record that my name is Patrick and my favorite fruit is strawberries.

🤖 model › I can’t create files directly here, but `profile.md` should contain:

# Profile

- Name: Patrick
- Favorite fruit: Strawberries
```

It produced the right document as answer text, but no file existed.

Level 6 adds four tools:

- `list_files` lists one directory.
- `read_file` reads one UTF-8 text file.
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
levels/06-files/agent_workspace/
```

`agent_workspace` is an ordinary directory beside this level's code. The program
creates it when a file tool first runs. Tool paths are relative to it, so
`profile.md` means `levels/06-files/agent_workspace/profile.md`. Each level has
its own `agent_workspace`.

---

## Run it

```sh
uv run --env-file .env levels/06-files/main.py --new
```

The startup text names the only directory the tools can access:

```text
[workspace: levels/06-files/agent_workspace]
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
tool ‹ {"path": "profile.md", "written": true, "characters": ...}
```

The `content` argument shows exactly what the model asked Python to write. Compare it with the text in your request before continuing.

Press `Ctrl-D` and start a separate conversation:

```sh
uv run --env-file .env levels/06-files/main.py --new
```

First ask without letting it inspect the workspace:

```text
📝 you › Without using tools, what is my name and favorite fruit?
```

The new conversation does not contain the creation request, so the model should say it does not know. Now direct it to the file:

```text
📝 you › Use read_file to read profile.md. What is my name and favorite fruit?
```

The answer should now contain `Patrick` and `strawberries`.

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

The CLI and agent loops are the same as Level 5. Level 6 adds entries to the tool list and function registry used by the clock:

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

Each key in `TOOL_FUNCTIONS` is a name the model can return. Each value is the Python function that name selects. The functions are not called when this dictionary is created; `run_tool()` calls the selected function later.

A write follows this path:

```text
function_call named write_file
→ run_tool() parses its JSON arguments
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

Without the containment check, `..` would move out of the workspace and expose the program's source file. The tool should instead return a `WorkspacePathError`. Level 4's error handling sends that failure back to the model instead of ending the process.

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

---

## File contents become conversation input

The terminal and JSONL file contain the complete write arguments and read results. Those canonical API items are sent to the next model call so it knows what was written or read.

A large `read_file` result therefore consumes input tokens on every later model
call in that conversation. The context-selection chapter in
[Advanced Agent Concepts](../../roadmap-intermediate.md) changes which completed
API items are sent when the history becomes too large.

---

## A profile file is the simplest memory strategy

In LLM chatbots, *memory* means that information from earlier interactions is retained and used in future chats.

`profile.md` provides retention: the facts remain on disk after the first conversation. In the next conversation, `read_file` retrieves those facts and adds them to model input so they can affect its answer.

The retrieval is manual in this level: the user explicitly asks the model to read the file. A later memory system decides when to retrieve stored information without requiring the user to name the file.

---

## Done when

1. Start Level 6:

   ```sh
   uv run --env-file .env levels/06-files/main.py --new
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
   uv run --env-file .env levels/06-files/main.py --new
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

## What breaks next

Ask it to write a Python script that converts `profile.md` to JSON. It can create the script but cannot run it, inspect the output, or correct an error.

Level 7 will add shell access and an approval gate.