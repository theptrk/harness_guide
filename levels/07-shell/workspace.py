"""Perform file operations inside one confined workspace directory."""

from pathlib import Path

ROOT = Path(__file__).parent / "agent_workspace"


class WorkspacePathError(ValueError):
    """A requested path resolves outside the agent workspace."""


def resolve_path(path: str) -> Path:
    """Resolve a model-supplied path and reject workspace escapes."""
    if ROOT.is_symlink():
        raise WorkspacePathError("agent_workspace must not be a symbolic link")
    ROOT.mkdir(exist_ok=True)
    resolved_root = ROOT.resolve()
    resolved = (resolved_root / path).resolve()
    if not resolved.is_relative_to(resolved_root):
        raise WorkspacePathError(f"path leaves the agent workspace: {path}")
    return resolved


def list_files(path: str) -> list[str]:
    """List one directory inside the workspace."""
    directory = resolve_path(path)
    if not directory.is_dir():
        raise NotADirectoryError(f"not a directory: {path}")

    entries = []
    for child in sorted(directory.iterdir(), key=lambda item: item.name):
        if child.is_symlink():
            suffix = "@"
        elif child.is_dir():
            suffix = "/"
        else:
            suffix = ""
        entries.append(f"{child.name}{suffix}")
    return entries


def read_file(path: str) -> str:
    """Read one UTF-8 text file inside the workspace."""
    file_path = resolve_path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"not a file: {path}")
    return file_path.read_text()


def write_file(path: str, content: str) -> None:
    """Create or replace one UTF-8 text file inside the workspace."""
    file_path = resolve_path(path)
    if file_path.exists() and file_path.is_dir():
        raise IsADirectoryError(f"cannot write a directory: {path}")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


def edit_file(path: str, old_text: str, new_text: str) -> None:
    """Replace one exact occurrence in a UTF-8 text file."""
    if not old_text:
        raise ValueError("old_text must not be empty")

    content = read_file(path)
    matches = content.count(old_text)
    if matches == 0:
        raise ValueError("old_text was not found")
    if matches > 1:
        raise ValueError(f"old_text matched {matches} places; provide more context")

    resolve_path(path).write_text(content.replace(old_text, new_text, 1))
