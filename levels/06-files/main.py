"""Level 6 — give the agent confined file tools.

    uv run --env-file .env levels/06-files/main.py
    uv run --env-file .env levels/06-files/main.py --new
"""

import json
import os
import sys
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from openai import OpenAI, OpenAIError

import file_tools
import history

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = (
    "You are a concise coding assistant. Use the file tools to inspect and modify "
    "files in your workspace. Do not claim a file changed unless a tool succeeded."
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
    history.append_event(
        chat_file_path,
        turn_id,
        "model_call_finished",
        **outcome,
    )


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
):
    """Print text deltas, then return the terminal response."""
    request_options = {}
    if max_output_tokens is not None:
        request_options["max_output_tokens"] = max_output_tokens

    history.append_event(
        chat_file_path,
        turn_id,
        "model_started",
        model_call=model_call,
    )
    print(f"\n[model call {model_call} started]", flush=True)

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
                if not text_started:
                    print("\nmodel › ", end="", flush=True)
                print(event.delta, end="", flush=True)
                text_started = True
            elif event.type in {
                "response.completed",
                "response.incomplete",
                "response.failed",
            }:
                final_response = event.response

    if text_started:
        print()
    if final_response is None:
        raise HarnessError("model stream ended without a terminal response")
    return final_response, text_started


def run_turn(client, chat_file_path, said: str, max_output_tokens: int | None) -> None:
    """Run one user request until the model returns an answer."""
    turn_id = uuid4().hex
    history.append_event(chat_file_path, turn_id, "turn_started")
    history.append_api_item(
        chat_file_path,
        turn_id,
        {"role": "user", "content": said},
    )
    model_calls = 0
    tool_calls = 0
    input_tokens = 0
    output_tokens = 0
    force_answer = False

    try:
        while True:
            input_items = history.get_input_items(
                chat_file_path,
                active_turn_id=turn_id,
            )
            model_calls += 1
            response, text_was_streamed = stream_response(
                client,
                chat_file_path,
                turn_id,
                model_calls,
                input_items,
                force_answer,
                max_output_tokens,
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
                answer = response_text(response)
                if not text_was_streamed:
                    print(f"\nmodel › {answer}")
                break
            if force_answer:
                raise HarnessError("model requested a tool after tool use was disabled")

            print(f"\ntool › {tool_call.name}({tool_call.arguments})")
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
            print(f"tool ‹ {tool_result}")
    except KeyboardInterrupt:
        history.append_event(chat_file_path, turn_id, "turn_interrupted")
        print("\n[turn interrupted]")
        raise
    except OpenAIError as error:
        history.append_event(
            chat_file_path,
            turn_id,
            "turn_failed",
            error_type=type(error).__name__,
            message=str(error),
        )
        sys.exit(f"API failed after retries: {error}")
    except HarnessError as error:
        history.append_event(
            chat_file_path,
            turn_id,
            "turn_failed",
            error_type=type(error).__name__,
            message=str(error),
        )
        sys.exit(f"harness failed: {error}")

    history.append_event(
        chat_file_path,
        turn_id,
        "turn_completed",
        model_calls=model_calls,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    print(
        f"    [{model_calls} model call(s) · {tool_calls} tool call(s)"
        f" · {input_tokens} in + {output_tokens} out]\n"
    )


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

    try:
        max_output_tokens = configured_output_limit()
    except HarnessError as error:
        sys.exit(f"harness failed: {error}")

    client = OpenAI(max_retries=API_RETRIES, timeout=API_TIMEOUT_SECONDS)

    if "--new" in sys.argv:
        chat_file_path = history.new_chat()
    else:
        chat_file_path = history.latest_chat() or history.new_chat()

    input_items = history.get_input_items(chat_file_path)
    print(f"[{chat_file_path.name} · {len(input_items)} input items so far]")
    print("[workspace: levels/06-files/agent_workspace]")
    print("Ctrl-D to leave. Ctrl-C interrupts the active turn.\n")

    while True:
        try:
            said = input("you › ").strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break
        if not said:
            continue

        try:
            run_turn(client, chat_file_path, said, max_output_tokens)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
