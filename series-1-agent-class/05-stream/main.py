"""Level 5 — stream model text and exclude unfinished turns.

    uv run --env-file .env series-1-agent-class/05-stream/main.py
"""

import json
import os
import sys
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI

MODEL = "gpt-5.6-luna"
SYSTEM_PROMPT = "You are a concise assistant. Answer in a few sentences."
TOOL_CALL_LIMIT = 5

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

Emit = Callable[[dict], None]


class HarnessError(RuntimeError):
    """The model returned output the harness cannot safely continue from."""


class Agent:
    """One model client and one conversation.

    The agent never prints. It reports each step of a turn by calling emit
    with a dict whose "type" is one of: model_started, text, tool,
    tool_result, done. Text arrives as fragments while the model streams.
    """

    def __init__(self, client: OpenAI, *, emit: Emit):
        self.client = client
        self.emit = emit
        self.input_items = []

    @staticmethod
    def _require_complete(response) -> None:
        """Reject output that is unsafe to execute or retain."""
        if response.status == "completed":
            return
        if response.status == "incomplete":
            reason = response.incomplete_details.reason if response.incomplete_details else "unknown"
            raise HarnessError(
                f"model response incomplete: {reason}; no tool from this response was executed"
            )
        if response.error is not None:
            raise HarnessError(
                f"model response failed: {response.error.code}: {response.error.message}"
            )
        raise HarnessError(f"model response ended with status {response.status}")

    def _run_tool(self, tool_call) -> str:
        """Run one requested tool, converting any failure into tool output."""
        try:
            arguments = json.loads(tool_call.arguments)
            tool_function = TOOL_FUNCTIONS.get(tool_call.name)
            if tool_function is None:
                raise LookupError(f"unknown tool: {tool_call.name}")
            return tool_function(**arguments)
        except Exception as error:
            return f"{type(error).__name__}: {error}"

    def _stream_response(
        self,
        model_call: int,
        input_items: list[dict],
        force_answer: bool,
    ):
        """Emit text fragments as they arrive, then return the terminal response."""
        self.emit({"type": "model_started", "model_call": model_call})

        final_response = None
        text_started = False
        with self.client.responses.create(
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            input=input_items,
            tools=TOOLS,
            tool_choice="none" if force_answer else "auto",
            parallel_tool_calls=False,
            reasoning={"effort": "none"},
            stream=True,
        ) as stream:
            for event in stream:
                if event.type in {
                    "response.output_text.delta",
                    "response.refusal.delta",
                }:
                    self.emit({"type": "text", "text": event.delta})
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

    def handle_message(self, said: str) -> None:
        """Run one user request until the model returns an answer."""
        turn_items = [{"role": "user", "content": said}]
        model_calls = 0
        tool_calls = 0
        input_tokens = 0
        output_tokens = 0
        force_answer = False

        while True:
            response, text_was_streamed = self._stream_response(
                model_calls + 1,
                self.input_items + turn_items,
                force_answer,
            )
            model_calls += 1
            if response.usage is not None:
                input_tokens += response.usage.input_tokens
                output_tokens += response.usage.output_tokens
            self._require_complete(response)
            turn_items.extend(
                item.model_dump(mode="json", exclude_none=True)
                for item in response.output
            )

            # response.output may contain messages, function calls, or other
            # item types. Find the function call relevant to this lesson.
            tool_call = next(
                (item for item in response.output if item.type == "function_call"),
                None,
            )

            if tool_call is None:
                # No tool request means the model has finished this turn.
                if not text_was_streamed:
                    self.emit({"type": "text", "text": response.output_text})
                break
            if force_answer:
                raise HarnessError("model requested a tool after tool use was disabled")

            self.emit({"type": "tool", "name": tool_call.name, "arguments": tool_call.arguments})
            if tool_calls >= TOOL_CALL_LIMIT:
                tool_result = (
                    f"ToolCallLimit: the limit of {TOOL_CALL_LIMIT} "
                    "tool calls has been reached"
                )
                force_answer = True
            else:
                tool_result = self._run_tool(tool_call)
                tool_calls += 1
            self.emit({"type": "tool_result", "name": tool_call.name, "output": tool_result})

            turn_items.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call.call_id,
                    "output": tool_result,
                },
            )

        self.input_items.extend(turn_items)
        self.emit(
            {
                "type": "done",
                "model_calls": model_calls,
                "tool_calls": tool_calls,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        )


def display_tool_result(tool_result: str) -> str:
    """Format JSON for the terminal without changing the stored tool result."""
    try:
        value = json.loads(tool_result)
    except json.JSONDecodeError:
        return tool_result
    return json.dumps(value, indent=2)


class Terminal:
    """Print agent events.

    Text arrives in fragments, so the terminal remembers whether a model line
    is open and closes it before printing anything else.
    """

    def __init__(self):
        self.text_open = False

    def emit(self, event: dict) -> None:
        kind = event["type"]
        if kind == "text":
            if not self.text_open:
                print("\n🤖 model › ", end="", flush=True)
                self.text_open = True
            print(event["text"], end="", flush=True)
            return

        if self.text_open:
            print()
            self.text_open = False

        if kind == "model_started":
            print(f"\n[model call {event['model_call']} started]", flush=True)
        elif kind == "tool":
            print(f"\ntool › {event['name']}({event['arguments']})")
        elif kind == "tool_result":
            print(f"tool ‹ {display_tool_result(event['output'])}")
        elif kind == "done":
            print(
                f"    [{event['model_calls']} model call(s) · {event['tool_calls']} tool call(s) · "
                f"{event['input_tokens']} in + {event['output_tokens']} out]\n"
            )


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set. Copy .env.example to .env and put your key in it.")

    terminal = Terminal()
    agent = Agent(OpenAI(), emit=terminal.emit)
    print("Ctrl-D to leave. Ctrl-C interrupts the active turn.\n")

    while True:
        try:
            said = input("📝 you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not said:
            continue

        try:
            agent.handle_message(said)
        except KeyboardInterrupt:
            print("\n[turn interrupted]")
            break
        except HarnessError as error:
            print(f"harness failed: {error}", file=sys.stderr)
        except Exception as error:
            print(f"call failed: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
