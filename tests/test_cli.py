import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tool_context_relay.cli import _parse_kv, _run_from_files, main, _validate_case
from tool_context_relay.cli import _normalize_model_for_agents
from tool_context_relay.cli import _format_startup_config_line
from tool_context_relay.testing.integration_hooks import CapturedToolCall
from tool_context_relay.testing.prompt_cases import PromptCase, ToolCallExpectation
from tool_context_relay.tools.tool_relay import box_value
from tool_context_relay.openai_env import load_profile


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        keys = (
            "OPENAI_BASE_URL",
            "OPENAI_API_BASE",
            "OPENAI_API_KEY",
            "OPENAI_MODEL",
            "OPENAI_TEMPERATURE",
            "TOOL_CONTEXT_RELAY_PROFILE",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_BASE_URL",
            "BIELIK_PROVIDER",
            "BIELIK_API_KEY",
            "BIELIK_BASE_URL",
            "BIELIK_MODEL",
            "BIELIK_TEMPERATURE",
            "QWEN_PROVIDER",
            "QWEN_API_KEY",
            "QWEN_BASE_URL",
            "QWEN_MODEL",
            "QWEN_TEMPERATURE",
            "QWEN_BACKEND_PROVIDER",
            "OPENROUTER_PROVIDER",
            "OPENROUTER_API_KEY",
            "OPENROUTER_BASE_URL",
            "OPENROUTER_MODEL",
            "OPENROUTER_BACKEND_PROVIDER",
        )
        self._prior: dict[str, str | None] = {key: os.environ.get(key) for key in keys}
        for key in keys:
            os.environ.pop(key, None)
        os.environ["OPENAI_API_KEY"] = "sk-test"
        self._load_dotenv_patcher = patch("tool_context_relay.cli.load_dotenv", return_value=True)
        self.load_dotenv = self._load_dotenv_patcher.start()

    def tearDown(self) -> None:
        for key, value in self._prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._load_dotenv_patcher.stop()
        super().tearDown()

    def test_format_startup_config_line(self):
        line = _format_startup_config_line(
            profile="bielik",
            provider="openai-compat",
            model_requested="openai/speakleash/Bielik",
            model_effective="speakleash/Bielik",
            endpoint="http://127.0.0.1:1234/v1",
            temperature=0.1,
            boxing_mode="opaque",
        )
        self.assertIn("profile=bielik", line)
        self.assertIn("provider=openai-compat", line)
        self.assertIn("model=speakleash/Bielik (requested=openai/speakleash/Bielik)", line)
        self.assertIn("endpoint=http://127.0.0.1:1234/v1", line)
        self.assertIn("temperature=0.1", line)
        self.assertIn("boxing=opaque", line)

    def test_normalize_model_for_agents_leaves_plain_models_untouched(self):
        self.assertEqual(_normalize_model_for_agents(model="gpt-4.1-mini"), "gpt-4.1-mini")
        self.assertEqual(
            _normalize_model_for_agents(model="litellm/openai/gpt-4.1-mini"),
            "litellm/openai/gpt-4.1-mini",
        )

    def test_normalize_model_for_agents_strips_openai_prefix(self):
        self.assertEqual(
            _normalize_model_for_agents(model="openai/gpt-4.1-mini"),
            "gpt-4.1-mini",
        )

    def test_normalize_model_for_agents_keeps_slash_model_ids(self):
        self.assertEqual(
            _normalize_model_for_agents(model="speakleash/Bielik-11B"),
            "speakleash/Bielik-11B",
        )

    def test_main_prints_startup_config_for_valid_invocation(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "tool_context_relay.main.run_once",
                return_value=("ok", SimpleNamespace(kv={})),
            ) as run_once,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["--model", "speakleash/Bielik", "hi"])

        self.assertEqual(code, 0)
        self.assertIn("<info>", stdout.getvalue())
        self.assertIn("Config used:", stdout.getvalue())
        self.assertIn("profile=openai", stdout.getvalue())
        self.assertIn("provider=openai", stdout.getvalue())
        self.assertIn("model=speakleash/Bielik", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["print_tools"], False)
        self.assertIsNone(run_once.call_args.kwargs["temperature"])
        self.assertEqual(run_once.call_args.kwargs["boxing_mode"], "opaque")
        self.assertEqual(run_once.call_args.kwargs["profile"], "openai")
        self.assertEqual(run_once.call_args.kwargs["profile_config"].provider, "openai")

    def test_main_print_tools_flag_is_passed_to_runner(self):
        os.environ["OPENAI_API_KEY"] = "sk-compat"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "tool_context_relay.main.run_once",
                return_value=("ok", SimpleNamespace(kv={})),
            ) as run_once,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["--model", "speakleash/Bielik", "--print-tools", "hi"])

        self.assertEqual(code, 0)
        self.assertIn("<info>", stdout.getvalue())
        self.assertIn("Config used:", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["print_tools"], True)
        self.assertIsNone(run_once.call_args.kwargs["temperature"])
        self.assertEqual(run_once.call_args.kwargs["boxing_mode"], "opaque")
        self.assertEqual(run_once.call_args.kwargs["profile"], "openai")

    def test_main_passes_temperature_flag_to_runner(self):
        os.environ["OPENAI_API_KEY"] = "sk-compat"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "tool_context_relay.main.run_once",
                return_value=("ok", SimpleNamespace(kv={})),
            ) as run_once,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["--model", "gpt-4.1-mini", "--temperature", "0.7", "hi"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["temperature"], 0.7)
        self.assertEqual(run_once.call_args.kwargs["boxing_mode"], "opaque")
        self.assertEqual(run_once.call_args.kwargs["profile"], "openai")

    def test_main_uses_profile_temperature_when_no_flag(self):
        os.environ["BIELIK_API_KEY"] = "sk-bielik"
        os.environ["BIELIK_TEMPERATURE"] = "0.35"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "tool_context_relay.main.run_once",
                return_value=("ok", SimpleNamespace(kv={})),
            ) as run_once,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["--profile", "bielik", "--model", "gpt-4.1-mini", "hi"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["temperature"], 0.35)
        self.assertEqual(run_once.call_args.kwargs["profile"], "bielik")

    def test_main_cli_temperature_overrides_profile(self):
        os.environ["BIELIK_API_KEY"] = "sk-bielik"
        os.environ["BIELIK_TEMPERATURE"] = "0.35"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "tool_context_relay.main.run_once",
                return_value=("ok", SimpleNamespace(kv={})),
            ) as run_once,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["--profile", "bielik", "--model", "gpt-4.1-mini", "--temperature", "0.6", "hi"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["temperature"], 0.6)
        self.assertEqual(run_once.call_args.kwargs["profile"], "bielik")

    def test_main_passes_boxing_flag_to_runner(self):
        os.environ["OPENAI_API_KEY"] = "sk-compat"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "tool_context_relay.main.run_once",
                return_value=("ok", SimpleNamespace(kv={})),
            ) as run_once,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["--boxing", "json", "hi"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["boxing_mode"], "json")
        self.assertEqual(run_once.call_args.kwargs["profile"], "openai")

    def test_main_ignores_temperature_for_reasoning_model(self):
        os.environ["OPENAI_API_KEY"] = "sk-compat"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "tool_context_relay.main.run_once",
                return_value=("ok", SimpleNamespace(kv={})),
            ) as run_once,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["--model", "gpt-5.2", "--temperature", "0.7", "hi"])

        self.assertEqual(code, 0)
        self.assertIn("Ignoring temperature=0.7", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assertIsNone(run_once.call_args.kwargs["temperature"])
        self.assertEqual(run_once.call_args.kwargs["boxing_mode"], "opaque")

    def test_main_rejects_profile_without_api_key(self):
        os.environ["BIELIK_PROVIDER"] = "openrouter"
        os.environ["OPENROUTER_BASE_URL"] = "http://localhost:1234/v1"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--profile", "bielik", "hi"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("must set BIELIK_API_KEY", stderr.getvalue())

    def test_parse_kv_ok(self):
        self.assertEqual(_parse_kv(["a=1", "b=two=2"]), {"a": "1", "b": "two=2"})

    def test_parse_kv_invalid(self):
        for pairs in (["nope"], ["=x"], [""]):
            with self.assertRaises(ValueError):
                _parse_kv(pairs)

    def test_main_rejects_empty_prompt(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main([""])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Prompt must not be empty.", stderr.getvalue())

    def test_main_rejects_whitespace_prompt(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["   "])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Prompt must not be empty.", stderr.getvalue())

    def test_main_treats_glob_like_string_as_literal_prompt(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch(
                "tool_context_relay.main.run_once",
                return_value=("ok", SimpleNamespace(kv={})),
            ) as run_once,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            code = main(["prompts/*.md"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["prompt"], "prompts/*.md")

    def test_main_rejects_prompt_and_file_flags_together(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--file", "x.md", "hi"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Use either a literal prompt argument OR --file/--glob", stderr.getvalue())

    def test_main_file_mode_calls_run_from_files(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "case.md"
            path.write_text("hello", encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch("tool_context_relay.cli._run_from_files", return_value=0) as run_from_files,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                code = main(
                    [
                        "--file",
                        str(path),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(run_from_files.call_count, 1)
            called_files = run_from_files.call_args.kwargs["files"]
            self.assertEqual([Path(p) for p in called_files], [path])
            self.assertEqual(run_from_files.call_args.kwargs["profile"], "openai")
            self.assertEqual(run_from_files.call_args.kwargs["profile_config"].provider, "openai")

    def test_main_glob_mode_expands_and_calls_run_from_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.md").write_text("a", encoding="utf-8")
            (root / "b.md").write_text("b", encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch("tool_context_relay.cli._run_from_files", return_value=0) as run_from_files,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                code = main(
                    [
                        "--glob",
                        str(root / "*.md"),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            called_files = [Path(p) for p in run_from_files.call_args.kwargs["files"]]
            self.assertEqual(called_files, [root / "a.md", root / "b.md"])
        self.assertEqual(run_from_files.call_args.kwargs["profile"], "openai")
        self.assertEqual(run_from_files.call_args.kwargs["profile_config"].provider, "openai")

    def test_run_from_files_prints_end_summary_with_pass_fail_and_reasons(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pass_path = root / "pass.md"
            fail_path = root / "fail.md"
            broken_path = root / "broken.md"

            pass_path.write_text(
                "---\n"
                "id: passcase\n"
                "---\n"
                "hello\n",
                encoding="utf-8",
            )
            fail_path.write_text(
                "---\n"
                "id: failcase\n"
                "tool_calls:\n"
                "  - tool_name: yt_transcribe\n"
                "---\n"
                "hello\n",
                encoding="utf-8",
            )
            broken_path.write_text("---\n" "id: broken\n", encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch(
                    "tool_context_relay.main.run_once",
                    return_value=("ok", SimpleNamespace(kv={})),
                ),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                code = _run_from_files(
                    files=[pass_path, fail_path, broken_path],
                    model="gpt-4.1-mini",
                    profile="openai",
                    profile_config=load_profile("openai"),
                    initial_kv={},
                    print_tools=False,
                    fewshots=False,
                    show_system_instruction=False,
                    temperature=None,
                    boxing_mode="opaque",
                    dump_context=False,
            )

            self.assertEqual(code, 1)
            self.assertIn("| Model | Prompt Id | Few-shot | Resolve success | Reason |", stdout.getvalue())
            self.assertIn("passcase", stdout.getvalue())
            self.assertIn("failcase", stdout.getvalue())
            self.assertIn("broken.md", stderr.getvalue())
            self.assertIn("tool call sequence mismatch", stderr.getvalue())
            self.assertIn("missing YAML frontmatter closing", stderr.getvalue())

    def test_validate_case_accepts_json_boxed_results(self):
        case = PromptCase(
            case_id="case1",
            prompt="hi",
            forbidden_tools=set(),
            tool_calls=[ToolCallExpectation(tool_name="yt_transcribe", opaque_id_result=True)],
            expect_internal_resolve=False,
        )
        result = box_value("x" * 2048, mode="json")
        calls = [CapturedToolCall(name="yt_transcribe", arguments={}, result=result)]

        errors = _validate_case(case, calls)
        self.assertEqual(errors, [])
