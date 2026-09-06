"""Checks for the legacy function-based series-1.

The main invariant: every `function_call` in a chat file has a matching
`function_call_output`. The Responses API rejects an `input` list holding a
call with no output for the same `call_id`. Levels 2 and 3 append items as they
happen, so a turn that ends between the two writes would leave the chat file
unusable for the rest of the conversation. These tests drive the failure paths
and confirm the record stays readable.
"""

import builtins
import importlib.util
import json
import os
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]
SERIES = ROOT / "series-1"
LEVELS = [
    "00-model",
    "01-conversation",
    "02-tool",
    "03-loop",
    "04-harden",
    "05-stream",
    "06-files",
    "07-shell",
    "08-browser",
]
APPENDING_LEVELS = ["02-tool", "03-loop"]
BUFFERING_LEVELS = ["04-harden", "05-stream", "06-files", "07-shell", "08-browser"]


class StubItem(SimpleNamespace):
    """One response.output item with the attributes main.py reads."""

    def model_dump(self, **_kwargs) -> dict:
        return {key: value for key, value in vars(self).items() if value is not None}


def function_call(call_id: str, name: str, arguments: str) -> StubItem:
    return StubItem(
        type="function_call", call_id=call_id, name=name, arguments=arguments
    )


def message(text: str) -> StubItem:
    return StubItem(type="message", role="assistant", content=text)


def response(output: list[StubItem], output_text: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        output=output,
        output_text=output_text,
        usage=SimpleNamespace(
            input_tokens=1,
            output_tokens=1,
            output_tokens_details=SimpleNamespace(reasoning_tokens=0),
        ),
        status="completed",
    )


class StubClient:
    """Returns queued responses in order, one per responses.create() call."""

    def __init__(self, responses: list[SimpleNamespace]):
        self._responses = list(responses)
        self.calls: list[list[dict]] = []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kwargs) -> SimpleNamespace:
        self.calls.append(kwargs["input"])
        if not self._responses:
            raise AssertionError("stub client ran out of queued responses")
        return self._responses.pop(0)


def load_level(level: str):
    """Import one level's main.py and the history module it uses."""
    directory = str(SERIES / level)
    for name in ("history", "main", "workspace", "file_tools", "shell_tools"):
        sys.modules.pop(name, None)
    sys.path.insert(0, directory)
    try:
        spec = importlib.util.spec_from_file_location(
            "main", SERIES / level / "main.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["main"] = module
        spec.loader.exec_module(module)
        return module, sys.modules["history"]
    finally:
        sys.path.remove(directory)


def read_items(history, path: Path) -> list[dict]:
    return history.get_input_items(path)


def unanswered_calls(items: list[dict]) -> list[str]:
    answered = {
        item["call_id"] for item in items if item.get("type") == "function_call_output"
    }
    return [
        item["call_id"]
        for item in items
        if item.get("type") == "function_call" and item["call_id"] not in answered
    ]


class ToolFailureTests(unittest.TestCase):
    """A tool that raises must not leave its call unanswered on disk."""

    def setUp(self) -> None:
        self.addCleanup(sys.modules.pop, "main", None)
        self.addCleanup(sys.modules.pop, "history", None)

    def _chat_file(self, history) -> Path:
        directory = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        history.CHATS = directory
        return history.new_chat()

    def test_level_3_records_an_output_when_the_tool_raises(self) -> None:
        main, history = load_level("03-loop")
        chat_file = self._chat_file(history)
        client = StubClient(
            [
                response(
                    [function_call("call_1", "get_current_time", '{"timezone":"Nope/Nope"}')]
                )
            ]
        )

        main.run_turn(client, chat_file, "what time is it on Mars")

        items = read_items(history, chat_file)
        self.assertEqual(unanswered_calls(items), [])
        output = next(i for i in items if i.get("type") == "function_call_output")
        self.assertIn("ZoneInfoNotFoundError", output["output"])

    def test_level_3_record_stays_valid_for_the_next_turn(self) -> None:
        main, history = load_level("03-loop")
        chat_file = self._chat_file(history)

        failing = StubClient(
            [
                response(
                    [function_call("call_1", "get_current_time", '{"timezone":"Nope/Nope"}')]
                )
            ]
        )
        main.run_turn(failing, chat_file, "what time is it on Mars")

        recovering = StubClient([response([message("Hello")], output_text="Hello")])
        main.run_turn(recovering, chat_file, "never mind, say hello")

        sent = recovering.calls[0]
        self.assertEqual(unanswered_calls(sent), [])

    def test_level_3_unknown_tool_is_answered(self) -> None:
        main, history = load_level("03-loop")
        chat_file = self._chat_file(history)
        client = StubClient([response([function_call("call_1", "no_such_tool", "{}")])])

        main.run_turn(client, chat_file, "use a tool that does not exist")

        items = read_items(history, chat_file)
        self.assertEqual(unanswered_calls(items), [])


class OneToolCallLimitTests(unittest.TestCase):
    """Level 2 stops after one tool call and must answer the call it refused."""

    def setUp(self) -> None:
        self.addCleanup(sys.modules.pop, "main", None)
        self.addCleanup(sys.modules.pop, "history", None)

    def test_level_2_answers_the_second_call_it_will_not_run(self) -> None:
        main, history = load_level("02-tool")
        directory = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        history.CHATS = directory

        client = StubClient(
            [
                response(
                    [
                        function_call(
                            "call_1", "get_current_time", '{"timezone":"Asia/Tokyo"}'
                        )
                    ]
                ),
                response(
                    [
                        function_call(
                            "call_2",
                            "get_current_time",
                            '{"timezone":"America/New_York"}',
                        )
                    ]
                ),
            ]
        )

        questions = iter(["what time is it in Tokyo and New York"])

        def fake_input(_prompt: str = "") -> str:
            try:
                return next(questions)
            except StopIteration:
                raise EOFError from None

        self.enterContext(_patched(main, "OpenAI", lambda: client))
        self.enterContext(_patched(builtins, "input", fake_input))
        self.enterContext(_patched(sys, "argv", ["main.py", "--new"]))
        self.enterContext(_patched(os.environ, "OPENAI_API_KEY", "test-key", mapping=True))

        main.main()

        chat_file = history.latest_chat()
        items = read_items(history, chat_file)
        self.assertEqual(unanswered_calls(items), [])
        self.assertEqual(
            sum(1 for item in items if item.get("type") == "function_call"), 2
        )


class TruncatedRecordTests(unittest.TestCase):
    """A record cut off mid-turn still reads as valid model input."""

    def setUp(self) -> None:
        self.addCleanup(sys.modules.pop, "main", None)
        self.addCleanup(sys.modules.pop, "history", None)

    def _write(self, path: Path, items: list[dict]) -> None:
        with path.open("w") as file:
            for item in items:
                file.write(json.dumps({"at": "2026-01-01T00:00:00", "item": item}) + "\n")

    def test_appending_levels_drop_an_unanswered_trailing_call(self) -> None:
        for level in APPENDING_LEVELS:
            with self.subTest(level=level):
                _, history = load_level(level)
                directory = Path(
                    self.enterContext(__import__("tempfile").TemporaryDirectory())
                )
                history.CHATS = directory
                chat_file = history.new_chat()
                self._write(
                    chat_file,
                    [
                        {"role": "user", "content": "hi"},
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "get_current_time",
                            "arguments": "{}",
                        },
                    ],
                )

                items = read_items(history, chat_file)
                self.assertEqual(unanswered_calls(items), [])
                self.assertEqual(items, [{"role": "user", "content": "hi"}])

    def test_an_unanswered_call_followed_by_more_turns_is_dropped(self) -> None:
        _, history = load_level("03-loop")
        directory = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        history.CHATS = directory
        chat_file = history.new_chat()
        self._write(
            chat_file,
            [
                {"role": "user", "content": "hi"},
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "get_current_time",
                    "arguments": "{}",
                },
                {"role": "user", "content": "still there?"},
            ],
        )

        items = read_items(history, chat_file)
        self.assertEqual(unanswered_calls(items), [])
        self.assertEqual([item.get("content") for item in items], ["hi", "still there?"])


class BufferedTurnTests(unittest.TestCase):
    """Levels 4 and later never write a partial turn, so they need no repair."""

    def test_buffering_levels_commit_whole_turns(self) -> None:
        for level in BUFFERING_LEVELS:
            source = (SERIES / level / "main.py").read_text()
            history_source = (SERIES / level / "history.py").read_text()
            with self.subTest(level=level):
                self.assertIn("history.append_items(chat_file_path, turn_items)", source)
                self.assertNotIn("def append_item(", history_source)
                self.assertNotIn("without_unanswered_calls", history_source)


class LessonStructureTests(unittest.TestCase):
    """The lesson arc holds: each level starts from what the last one could not do."""

    def test_level_folders_match(self) -> None:
        actual = sorted(
            path.name
            for path in SERIES.iterdir()
            if path.is_dir() and re.match(r"^\d\d-", path.name)
        )
        self.assertEqual(actual, LEVELS)

    def test_level_numbers_match_folders(self) -> None:
        for level in LEVELS:
            number = int(level[:2])
            with self.subTest(level=level):
                lesson = (SERIES / level / "LESSON.md").read_text()
                source = (SERIES / level / "main.py").read_text()
                self.assertTrue(lesson.startswith(f"# Level {number} —"))
                self.assertTrue(source.startswith(f'"""Level {number} —'))

    def test_each_later_lesson_starts_from_a_failure(self) -> None:
        for level in LEVELS[1:]:
            with self.subTest(level=level):
                lesson = (SERIES / level / "LESSON.md").read_text()
                self.assertIn("## What broke", lesson)

    def test_lessons_have_observable_completion_checks(self) -> None:
        for level in LEVELS:
            with self.subTest(level=level):
                lesson = (SERIES / level / "LESSON.md").read_text()
                self.assertIn("## Done when", lesson)

    def test_local_markdown_links_resolve(self) -> None:
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for path in SERIES.glob("**/*.md"):
            for target in link_pattern.findall(path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                relative_target = target.split("#", 1)[0]
                if not relative_target:
                    continue
                resolved = (path.parent / relative_target).resolve()
                with self.subTest(path=path.relative_to(ROOT), target=target):
                    self.assertTrue(resolved.exists(), f"{path}: broken link {target}")

    def test_readme_marks_the_canonical_path(self) -> None:
        readme = (SERIES / "README.md").read_text()
        self.assertIn("series-1-agent-class", readme)


class _patched:
    """Minimal context manager for temporarily replacing an attribute."""

    def __init__(self, target, name: str, value, mapping: bool = False):
        self.target = target
        self.name = name
        self.value = value
        self.mapping = mapping

    def __enter__(self):
        if self.mapping:
            self.had = self.name in self.target
            self.old = self.target.get(self.name)
            self.target[self.name] = self.value
        else:
            self.had = hasattr(self.target, self.name)
            self.old = getattr(self.target, self.name, None)
            setattr(self.target, self.name, self.value)
        return self.value

    def __exit__(self, *_exc):
        if self.mapping:
            if self.had:
                self.target[self.name] = self.old
            else:
                self.target.pop(self.name, None)
        elif self.had:
            setattr(self.target, self.name, self.old)
        else:
            delattr(self.target, self.name)
        return False


if __name__ == "__main__":
    unittest.main()
