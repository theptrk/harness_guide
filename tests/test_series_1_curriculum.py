"""Structural checks for the canonical Series 1 curriculum."""

import ast
import importlib.util
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]
SERIES = ROOT / "series-1-agent-class"
LEVELS = [
    "00-model",
    "01-conversation",
    "02-tool",
    "03-loop",
    "04-safe-loop",
    "05-stream",
    "06-files",
    "07-shell",
    "08-browser",
    "09-persistence",
    "10-operational",
]


def load_level_main(level: str):
    path = SERIES / level / "main.py"
    module_name = f"curriculum_{level.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class CurriculumStructureTests(unittest.TestCase):
    def test_level_order_and_required_files(self) -> None:
        actual = sorted(
            path.name
            for path in SERIES.iterdir()
            if path.is_dir() and re.match(r"^\d\d-", path.name)
        )
        self.assertEqual(actual, LEVELS)
        for level in LEVELS:
            with self.subTest(level=level):
                self.assertTrue((SERIES / level / "main.py").is_file())
                self.assertTrue((SERIES / level / "LESSON.md").is_file())

    def test_python_snapshots_parse(self) -> None:
        for path in SERIES.glob("**/*.py"):
            with self.subTest(path=path.relative_to(ROOT)):
                ast.parse(path.read_text(), filename=str(path))

    def test_every_snapshot_imports_without_side_effects(self) -> None:
        script = """
import importlib.util
import sys
from pathlib import Path

path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(path.parent))
spec = importlib.util.spec_from_file_location("snapshot_main", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
"""
        environment = os.environ.copy()
        environment.pop("OPENAI_API_KEY", None)

        for level in LEVELS:
            path = SERIES / level / "main.py"
            completed = subprocess.run(
                [sys.executable, "-c", script, str(path)],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            with self.subTest(level=level):
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stdout, "")
                self.assertEqual(completed.stderr, "")

    def test_level_numbers_match_folders(self) -> None:
        for level in LEVELS:
            number = int(level[:2])
            lesson = (SERIES / level / "LESSON.md").read_text()
            source = (SERIES / level / "main.py").read_text()
            with self.subTest(level=level):
                self.assertTrue(lesson.startswith(f"# Level {number} —"))
                self.assertTrue(source.startswith(f'"""Level {number} —'))

    def test_lessons_have_observable_completion_checks(self) -> None:
        for level in LEVELS:
            lesson = (SERIES / level / "LESSON.md").read_text()
            with self.subTest(level=level):
                self.assertIn("## Done when", lesson)

    def test_each_later_lesson_starts_from_a_failure(self) -> None:
        for level in LEVELS[1:]:
            lesson = (SERIES / level / "LESSON.md").read_text()
            with self.subTest(level=level):
                self.assertIn("## What broke", lesson)

    def test_nonfinal_lessons_motivate_the_next_level(self) -> None:
        for level in LEVELS[:-1]:
            lesson = (SERIES / level / "LESSON.md").read_text()
            with self.subTest(level=level):
                self.assertIn("## What breaks next", lesson)

    def test_local_markdown_links_resolve(self) -> None:
        link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
        for path in [
            ROOT / "README.md",
            ROOT / "roadmap.md",
            *SERIES.glob("**/*.md"),
        ]:
            for target in link_pattern.findall(path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                relative_target = target.split("#", 1)[0]
                if not relative_target:
                    continue
                resolved = (path.parent / relative_target).resolve()
                with self.subTest(path=path.relative_to(ROOT), target=target):
                    self.assertTrue(resolved.exists(), f"{path}: broken link {target}")

    def test_commands_do_not_reference_renamed_levels(self) -> None:
        stale = [
            "series-1-agent-class/04-stream",
            "series-1-agent-class/05-files",
            "series-1-agent-class/06-shell",
            "series-1-agent-class/07-browser",
            "series-1-agent-class/08-persistence",
            "series-1-agent-class/09-harden",
            "LEVEL8_HEADLESS",
        ]
        for path in SERIES.glob("**/*"):
            if not path.is_file() or path.suffix not in {".md", ".py"}:
                continue
            text = path.read_text()
            for old_name in stale:
                with self.subTest(path=path.relative_to(ROOT), old_name=old_name):
                    self.assertNotIn(old_name, text)


class CurriculumInvariantTests(unittest.TestCase):
    def _source(self, level: str) -> str:
        return (SERIES / level / "main.py").read_text()

    def test_agent_never_owns_terminal_or_environment_policy(self) -> None:
        forbidden_names = {"input", "print", "exit", "quit"}
        forbidden_attributes = {("os", "getenv"), ("sys", "exit")}

        for level in LEVELS:
            tree = ast.parse(self._source(level))
            agent = next(
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "Agent"
            )
            for node in ast.walk(agent):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name):
                    with self.subTest(level=level, call=node.func.id):
                        self.assertNotIn(node.func.id, forbidden_names)
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                ):
                    call = (node.func.value.id, node.func.attr)
                    with self.subTest(level=level, call=call):
                        self.assertNotIn(call, forbidden_attributes)

    def test_protocol_safety_precedes_side_effectful_tools(self) -> None:
        self.assertNotIn("_require_complete", self._source("03-loop"))

        for level in LEVELS[4:]:
            source = self._source(level)
            with self.subTest(level=level):
                self.assertIn("self._require_complete(response)", source)
                self.assertIn("except Exception as error:", source)
                validation = source.index("self._require_complete(response)")
                execution = source.index("tool_result = self._run_tool(tool_call)")
                self.assertLess(validation, execution)

    def test_stream_deltas_are_not_appended_as_conversation_items(self) -> None:
        for level in LEVELS[5:]:
            source = self._source(level)
            with self.subTest(level=level):
                self.assertIn('"response.output_text.delta"', source)
                self.assertIn(
                    'item.model_dump(mode="json", exclude_none=True)',
                    source,
                )
                self.assertNotIn("turn_items.append(event.delta)", source)

    def test_persistence_begins_at_level_nine(self) -> None:
        for level in LEVELS[:9]:
            with self.subTest(level=level):
                self.assertNotIn("import history", self._source(level))

        persistence = self._source("09-persistence")
        self.assertIn("import history", persistence)
        self.assertIn("history.get_input_items(self.chat_file_path)", persistence)
        self.assertIn("history.append_items(self.chat_file_path, turn_items)", persistence)


class FakeItem:
    def __init__(self, item_type: str, **fields) -> None:
        self.type = item_type
        for name, value in fields.items():
            setattr(self, name, value)

    def model_dump(self, **_options) -> dict:
        return {
            name: value
            for name, value in vars(self).items()
            if value is not None
        }


class FakeResponses:
    def __init__(self, responses) -> None:
        self.remaining = list(responses)
        self.requests = []
        self.responses = self

    def create(self, **request):
        self.requests.append(request)
        return self.remaining.pop(0)


class SafeLoopBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.level = load_level_main("04-safe-loop")

    @staticmethod
    def response(*, status="completed", output=(), output_text="", reason=None):
        return SimpleNamespace(
            status=status,
            output=list(output),
            output_text=output_text,
            usage=None,
            error=None,
            incomplete_details=(
                SimpleNamespace(reason=reason)
                if reason is not None
                else None
            ),
        )

    def test_incomplete_response_is_not_executed_or_committed(self) -> None:
        tool_call = FakeItem(
            "function_call",
            name="get_current_time",
            arguments='{"timezone":"Asia/Tokyo"}',
            call_id="call_incomplete",
        )
        client = FakeResponses(
            [
                self.response(
                    status="incomplete",
                    output=[tool_call],
                    reason="max_output_tokens",
                )
            ]
        )
        events = []
        agent = self.level.Agent(client, emit=events.append)

        with self.assertRaisesRegex(self.level.HarnessError, "max_output_tokens"):
            agent.handle_message("What time is it?")

        self.assertEqual(events, [])
        self.assertEqual(agent.input_items, [])
        self.assertEqual(len(client.requests), 1)

    def test_tool_failure_becomes_a_paired_output(self) -> None:
        tool_call = FakeItem(
            "function_call",
            name="get_current_time",
            arguments='{"timezone":"Mars/Olympus"}',
            call_id="call_invalid_zone",
        )
        final_message = FakeItem(
            "message",
            role="assistant",
            content=[{"type": "output_text", "text": "That timezone is invalid."}],
            phase="final_answer",
        )
        client = FakeResponses(
            [
                self.response(output=[tool_call]),
                self.response(
                    output=[final_message],
                    output_text="That timezone is invalid.",
                ),
            ]
        )
        events = []
        agent = self.level.Agent(client, emit=events.append)

        agent.handle_message("Use Mars/Olympus and explain the failure.")

        second_input = client.requests[1]["input"]
        call = next(item for item in second_input if item.get("type") == "function_call")
        result = next(
            item
            for item in second_input
            if item.get("type") == "function_call_output"
        )
        self.assertEqual(result["call_id"], call["call_id"])
        self.assertIn("ZoneInfoNotFoundError", result["output"])
        self.assertEqual(agent.input_items, second_input + [final_message.model_dump()])
        self.assertTrue(
            any(
                event["type"] == "tool_result"
                and "ZoneInfoNotFoundError" in event["output"]
                for event in events
            )
        )


if __name__ == "__main__":
    unittest.main()
