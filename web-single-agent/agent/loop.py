"""Run one user turn: model calls, tools, and history. No HTTP."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from openai import OpenAI, OpenAIError

from . import file_tools, history, workspace

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = (
    "You are a concise coding assistant. Use the tools to inspect and modify files "
    "in the agent workspace. Do not claim an action succeeded unless its tool "
    "result says it did."
)
TOOL_CALL_LIMIT = 5
API_RETRIES = 2
API_TIMEOUT_SECONDS = 30.0

TIME_TOOL = {
    "type": "function",
    "name": "get_current_time",
    "description": "Get the current date and time in a specific timezone.",
    "parameters": {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "An IANA timezone name, such as Asia/Tokyo or America/New_York.",
            }
        },
        "required": ["timezone"],
        "additionalProperties": False,
    },
    "strict": True,
}

TOOLS = [TIME_TOOL] + file_tools.TOOLS

Emit = Callable[[dict], None]

_client: OpenAI | None = None


class HarnessError(RuntimeError):
    """A failure that the model cannot correct with another tool call."""


def get_current_time(timezone: str) -> str:
    """Return the current time in an IANA timezone as JSON."""
    now = datetime.now(ZoneInfo(timezone))
    return json.dumps(
        {
            "timezone": timezone,
            "datetime": now.isoformat(timespec="seconds"),
        }
    )


TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
    "list_files": file_tools.list_files,
    "read_file": file_tools.read_file,
    "write_file": file_tools.write_file,
    "edit_file": file_tools.edit_file,
}


def tool_error(error_type: str, message: str) -> str:
    """Return a structured tool error for the model to read."""
    return json.dumps(
        {
            "error": {
                "type": error_type,
                "message": message,
            }
        }
    )


def run_tool(tool_call) -> str:
    """Run one requested tool, converting any failure into tool output."""
    try:
        arguments = json.loads(tool_call.arguments)
        tool_function = TOOL_FUNCTIONS.get(tool_call.name)
        if tool_function is None:
            raise LookupError(f"unknown tool: {tool_call.name}")
        return tool_function(**arguments)
    except Exception as error:
        return tool_error(type(error).__name__, str(error))


def configured_output_limit() -> int | None:
    """Read the optional limit used to reproduce incomplete responses."""
    value = os.getenv("MAX_OUTPUT_TOKENS")
    if value is None:
        return None
    try:
        limit = int(value)
    except ValueError as error:
        raise HarnessError("MAX_OUTPUT_TOKENS must be an integer") from error
    if limit < 1:
        raise HarnessError("MAX_OUTPUT_TOKENS must be greater than zero")
    return limit


def save_response(chat_file_path, turn_id: str, response, model_call: int) -> None:
    """Save canonical output, excluding incomplete items from later model input."""
    append_item = (
        history.append_api_item
        if response.status == "completed"
        else history.append_incomplete_item
    )
    for output_item in response.output:
        append_item(
            chat_file_path,
            turn_id,
            output_item.model_dump(mode="json", exclude_none=True),
        )
    outcome = {
        "model_call": model_call,
        "status": response.status,
    }
    if response.incomplete_details is not None:
        outcome["incomplete_reason"] = response.incomplete_details.reason
    history.append_event(chat_file_path, turn_id, "model_call_finished", **outcome)


def require_complete(response) -> None:
    """Reject output that is unsafe to execute or include in later model input."""
    if response.status == "completed":
        return
    if response.status == "incomplete":
        reason = response.incomplete_details.reason if response.incomplete_details else "unknown"
        raise HarnessError(
            f"model response incomplete: {reason}; no tool from this response was executed"
        )
    if response.error is not None:
        raise HarnessError(f"model response failed: {response.error.code}: {response.error.message}")
    raise HarnessError(f"unexpected model response status: {response.status}")


def response_text(response) -> str:
    """Return normal answer text or the model's refusal text."""
    if response.output_text:
        return response.output_text
    for item in response.output:
        if item.type != "message":
            continue
        for content in item.content:
            if content.type == "refusal":
                return content.refusal
    raise HarnessError("completed model response contained no answer")


def stream_response(
    client,
    chat_file_path,
    turn_id: str,
    model_call: int,
    input_items: list[dict],
    force_answer: bool,
    max_output_tokens: int | None,
    emit: Emit,
):
    """Stream text deltas to emit, then return the terminal response."""
    request_options = {}
    if max_output_tokens is not None:
        request_options["max_output_tokens"] = max_output_tokens

    history.append_event(chat_file_path, turn_id, "model_started", model_call=model_call)
    emit({"type": "model_started", "model_call": model_call})

    final_response = None
    text_started = False
    with client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=input_items,
        tools=TOOLS,
        tool_choice="none" if force_answer else "auto",
        parallel_tool_calls=False,
        reasoning={"effort": "none"},
        stream=True,
        **request_options,
    ) as stream:
        for event in stream:
            if event.type in {
                "response.output_text.delta",
                "response.refusal.delta",
            }:
                emit({"type": "delta", "text": event.delta})
                text_started = True
            elif event.type in {
                "response.completed",
                "response.incomplete",
                "response.failed",
            }:
                final_response = event.response

    if final_response is None:
        raise HarnessError("model stream ended without a terminal response")
    return final_response, text_started


def run_turn(
    client,
    chat_file_path,
    said: str,
    *,
    emit: Emit,
    max_output_tokens: int | None,
) -> None:
    """Run one user request until the model returns an answer."""
    turn_id = uuid4().hex
    history.append_event(chat_file_path, turn_id, "turn_started")
    history.append_api_item(chat_file_path, turn_id, {"role": "user", "content": said})
    emit({"type": "title", "title": conversation_title(chat_file_path)})
    model_calls = 0
    tool_calls = 0
    input_tokens = 0
    output_tokens = 0
    force_answer = False

    try:
        while True:
            input_items = history.get_input_items(chat_file_path, active_turn_id=turn_id)
            model_calls += 1
            response, text_was_streamed = stream_response(
                client,
                chat_file_path,
                turn_id,
                model_calls,
                input_items,
                force_answer,
                max_output_tokens,
                emit,
            )
            save_response(chat_file_path, turn_id, response, model_calls)
            if response.usage is not None:
                input_tokens += response.usage.input_tokens
                output_tokens += response.usage.output_tokens
            require_complete(response)

            tool_call = next(
                (item for item in response.output if item.type == "function_call"),
                None,
            )
            if tool_call is None:
                if not text_was_streamed:
                    emit({"type": "delta", "text": response_text(response)})
                break
            if force_answer:
                raise HarnessError("model requested a tool after tool use was disabled")

            emit(
                {
                    "type": "tool",
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                }
            )
            if tool_calls >= TOOL_CALL_LIMIT:
                tool_result = tool_error(
                    "ToolCallLimit",
                    f"the limit of {TOOL_CALL_LIMIT} tool calls has been reached",
                )
                force_answer = True
            else:
                tool_result = run_tool(tool_call)
                tool_calls += 1

            history.append_api_item(
                chat_file_path,
                turn_id,
                {
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": tool_result,
                },
            )
            emit({"type": "tool_result", "name": tool_call.name, "output": tool_result})
    except OpenAIError as error:
        history.append_event(
            chat_file_path,
            turn_id,
            "turn_failed",
            error_type=type(error).__name__,
            message=str(error),
        )
        emit({"type": "error", "message": f"API failed after retries: {error}"})
        return
    except HarnessError as error:
        history.append_event(
            chat_file_path,
            turn_id,
            "turn_failed",
            error_type=type(error).__name__,
            message=str(error),
        )
        emit({"type": "error", "message": f"harness failed: {error}"})
        return

    history.append_event(
        chat_file_path,
        turn_id,
        "turn_completed",
        model_calls=model_calls,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    emit(
        {
            "type": "done",
            "model_calls": model_calls,
            "tool_calls": tool_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
    )


def item_text(item: dict) -> str:
    """Return visible text from a stored user or assistant item."""
    content = item.get("content")
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") in {"output_text", "text"}:
            parts.append(block.get("text") or "")
        elif block.get("type") == "refusal":
            parts.append(block.get("refusal") or "")
    return "".join(parts)


def item_row(item: dict) -> dict | None:
    """Turn one stored API item into a UI row, or None if it has nothing to show."""
    if item.get("role") == "user" and item.get("type") in {None, "message"}:
        text = item_text(item)
        return {"kind": "user", "text": text} if text else None
    if item.get("type") == "function_call":
        return {
            "kind": "tool",
            "name": item.get("name", ""),
            "arguments": item.get("arguments", ""),
        }
    if item.get("type") == "function_call_output":
        return {"kind": "tool_result", "output": item.get("output", "")}
    if item.get("type") == "message":
        text = item_text(item)
        return {"kind": "assistant", "text": text} if text else None
    return None


def transcript_entries(path) -> list[dict]:
    """Turn stored history events into UI rows.

    Only a completed turn reaches later model input, so every row carries
    in_model_input. A turn that failed or was interrupted stays visible and
    reports false, because the person typed it and the model will never see it.
    """
    if not path.exists() or path.stat().st_size == 0:
        return []

    events = history.read_events(path)
    completed_turns = {
        event["turn_id"] for event in events if event["kind"] == "turn_completed"
    }

    entries = []
    for event in events:
        if event["kind"] == "turn_failed":
            entries.append(
                {
                    "kind": "turn_failed",
                    "message": event.get("message", ""),
                    "at": event.get("at"),
                }
            )
            continue
        if event["kind"] != "api_item":
            continue
        row = item_row(event["item"])
        if row is None:
            continue
        entries.append(
            {
                **row,
                "at": event.get("at"),
                "in_model_input": event["turn_id"] in completed_turns,
            }
        )
    return entries


def conversation_title(path) -> str:
    """Use the first user message as the chat title."""
    for entry in transcript_entries(path):
        if entry["kind"] == "user" and entry["text"].strip():
            text = " ".join(entry["text"].split())
            return text if len(text) <= 48 else f"{text[:45]}..."
    return "New chat"


def workspace_label() -> str:
    """Return the workspace directory shown in the UI."""
    return str(workspace.ROOT)


def get_client() -> OpenAI:
    """Return the shared OpenAI client."""
    global _client
    if _client is None:
        _client = OpenAI(max_retries=API_RETRIES, timeout=API_TIMEOUT_SECONDS)
    return _client


def current_chat():
    """Return the latest conversation, creating one if needed."""
    return history.latest_chat() or history.new_chat()


def new_chat():
    """Start an empty conversation."""
    return history.new_chat()


def snapshot() -> dict:
    """Return title, workspace, and transcript rows for the current chat."""
    path = current_chat()
    return {
        "title": conversation_title(path),
        "workspace": workspace_label(),
        "messages": transcript_entries(path),
    }


def handle_message(said: str, *, emit: Emit) -> None:
    """Run one user message. The host supplies emit."""
    emit({"type": "workspace", "workspace": workspace_label()})
    try:
        limit = configured_output_limit()
    except HarnessError as error:
        emit({"type": "error", "message": str(error)})
        return
    run_turn(
        get_client(),
        current_chat(),
        said,
        emit=emit,
        max_output_tokens=limit,
    )
