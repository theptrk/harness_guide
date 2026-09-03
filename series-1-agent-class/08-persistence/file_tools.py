"""Expose confined workspace operations as model-callable tools."""

import json

import workspace

TOOLS = [
    {
        "type": "function",
        "name": "list_files",
        "description": "List files and directories at one path in the agent workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "A path relative to the workspace. Use . for its root.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
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
    },
    {
        "type": "function",
        "name": "write_file",
        "description": "Create or replace one UTF-8 text file in the agent workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path relative to the workspace.",
                },
                "content": {
                    "type": "string",
                    "description": "The complete content to write.",
                },
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "edit_file",
        "description": "Replace one exact text block in a workspace file. Include enough surrounding text for one match.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The file path relative to the workspace.",
                },
                "old_text": {
                    "type": "string",
                    "description": "The exact text to replace. It must occur once.",
                },
                "new_text": {
                    "type": "string",
                    "description": "The replacement text.",
                },
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def list_files(path: str) -> str:
    """Return a workspace directory listing as JSON."""
    return json.dumps(
        {
            "path": path,
            "entries": workspace.list_files(path),
        }
    )


def read_file(path: str, offset: int, limit: int) -> str:
    """Return a line window from one workspace file as JSON."""
    return json.dumps(workspace.read_file(path, offset, limit))


def write_file(path: str, content: str) -> str:
    """Write one workspace file and report success."""
    workspace.write_file(path, content)
    return json.dumps(
        {
            "path": path,
            "written": True,
            "characters": len(content),
        }
    )


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit one workspace file and report success."""
    workspace.edit_file(path, old_text, new_text)
    return json.dumps(
        {
            "path": path,
            "edited": True,
        }
    )
