"""Level 4 — contain failures inside a bounded agent loop.

    uv run --env-file .env levels/04-harden/main.py
    uv run --env-file .env levels/04-harden/main.py --new
"""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI, OpenAIError

import history

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."
TOOL_CALL_LIMIT = 5
API_RETRIES = 2
API_TIMEOUT_SECONDS = 30.0

TOOLS = [
    {
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
]


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


def save_response(chat_file_path, response) -> None:
    """Save output, but exclude incomplete output from the next API input."""
    include_in_input = response.status == "completed"
    for output_item in response.output:
        history.append_item(
            chat_file_path,
            output_item.model_dump(mode="json", exclude_none=True),
            include_in_input=include_in_input,
        )


def require_complete(response) -> None:
    """Reject output that is unsafe to execute or replay."""
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
    print(f"[{chat_file_path.name} · {len(input_items)} replayable items so far]")
    print("Ctrl-D to leave. Every API item is saved.\n")

    while True:
        try:
            said = input("you › ").strip()
        except EOFError:
            print()
            break
        if not said:
            continue

        history.append_item(
            chat_file_path,
            {"role": "user", "content": said},
        )
        only_user_item_written = True
        model_calls = 0
        tool_calls = 0
        input_tokens = 0
        output_tokens = 0
        force_answer = False

        try:
            while True:
                input_items = history.get_input_items(chat_file_path)
                request_options = {}
                if max_output_tokens is not None:
                    request_options["max_output_tokens"] = max_output_tokens

                response = client.responses.create(
                    model=MODEL,
                    instructions=SYSTEM_PROMPT,
                    input=input_items,
                    tools=TOOLS,
                    tool_choice="none" if force_answer else "auto",
                    parallel_tool_calls=False,
                    reasoning={"effort": "none"},
                    **request_options,
                )
                save_response(chat_file_path, response)
                only_user_item_written = False
                model_calls += 1
                input_tokens += response.usage.input_tokens
                output_tokens += response.usage.output_tokens
                require_complete(response)

                tool_call = next(
                    (item for item in response.output if item.type == "function_call"),
                    None,
                )
                if tool_call is None:
                    answer = response_text(response)
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
                print(f"tool ‹ {tool_result}")

                history.append_item(
                    chat_file_path,
                    {
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": tool_result,
                    },
                )
        except KeyboardInterrupt:
            if only_user_item_written:
                history.drop_last_item(chat_file_path)
            print()
            break
        except OpenAIError as error:
            if only_user_item_written:
                history.drop_last_item(chat_file_path)
            sys.exit(f"API failed after retries: {error}")
        except HarnessError as error:
            sys.exit(f"harness failed: {error}")

        print(f"\n››› {answer}")
        print(
            f"    [{model_calls} model call(s) · {tool_calls} tool call(s)"
            f" · {input_tokens} in + {output_tokens} out]\n"
        )


if __name__ == "__main__":
    main()
