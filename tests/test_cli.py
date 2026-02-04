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

from tool_context_relay.cli import _parse_kv, _run_from_files, main
from tool_context_relay.cli import _normalize_model_for_agents
from tool_context_relay.cli import _format_startup_config_line


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._prior: dict[str, str | None] = {}
        for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "OPENAI_API_KEY"):
            self._prior[key] = os.environ.get(key)
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        super().tearDown()

    def test_format_startup_config_line(self):
        line = _format_startup_config_line(
            provider_requested="auto",
            provider_resolved="openai-compat",
            model_requested="speakleash/Bielik",
            model_effective="speakleash/Bielik",
            endpoint="http://127.0.0.1:1234/v1",
        )
        self.assertIn("provider=openai-compat (requested=auto)", line)
        self.assertIn("model=speakleash/Bielik", line)
        self.assertIn("endpoint=http://127.0.0.1:1234/v1", line)

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
        os.environ["OPENAI_COMPAT_API_KEY"] = "sk-compat"
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
            code = main(
                [
                    "--provider",
                    "openai-compat",
                    "--endpoint",
                    "http://127.0.0.1:1234/v1",
                    "--model",
                    "speakleash/Bielik",
                    "hi",
                ]
        )

        self.assertEqual(code, 0)
        self.assertIn("<info>", stdout.getvalue())
        self.assertIn("Config used:", stdout.getvalue())
        self.assertIn("provider=openai-compat", stdout.getvalue())
        self.assertIn("model=speakleash/Bielik", stdout.getvalue())
        self.assertIn("endpoint=http://127.0.0.1:1234/v1", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["print_tools"], False)

    def test_main_print_tools_flag_is_passed_to_runner(self):
        os.environ["OPENAI_COMPAT_API_KEY"] = "sk-compat"
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
            code = main(
                [
                    "--provider",
                    "openai-compat",
                    "--endpoint",
                    "http://127.0.0.1:1234/v1",
                    "--model",
                    "speakleash/Bielik",
                    "--print-tools",
                    "hi",
                ]
        )

        self.assertEqual(code, 0)
        self.assertIn("<info>", stdout.getvalue())
        self.assertIn("Config used:", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["print_tools"], True)

    def test_main_rejects_openai_provider_with_endpoint(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--provider", "openai", "--endpoint", "http://example.test/v1", "   "])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Provider 'openai' cannot be used with an endpoint override", stderr.getvalue())

    def test_main_rejects_openai_compat_provider_without_endpoint(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--provider", "openai-compat", "   "])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Provider 'openai-compat' requires an endpoint override", stderr.getvalue())

    def test_main_sets_endpoint_env(self):
        prior_base_url = os.environ.get("OPENAI_BASE_URL")
        prior_api_base = os.environ.get("OPENAI_API_BASE")
        try:
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(["--endpoint", "http://example.test/v1", "   "])

            self.assertEqual(code, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("Prompt must not be empty.", stderr.getvalue())
            self.assertEqual(os.environ.get("OPENAI_BASE_URL"), "http://example.test/v1")
            self.assertEqual(os.environ.get("OPENAI_API_BASE"), "http://example.test/v1")
        finally:
            if prior_base_url is None:
                os.environ.pop("OPENAI_BASE_URL", None)
            else:
                os.environ["OPENAI_BASE_URL"] = prior_base_url

            if prior_api_base is None:
                os.environ.pop("OPENAI_API_BASE", None)
            else:
                os.environ["OPENAI_API_BASE"] = prior_api_base

    def test_main_rejects_empty_endpoint(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--endpoint", "   ", "hi"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Endpoint must not be empty.", stderr.getvalue())

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
            code = main(["prompt_cases/*.md"])

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(run_once.call_args.kwargs["prompt"], "prompt_cases/*.md")

    def test_main_rejects_prompt_and_file_flags_together(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(["--file", "x.md", "hi"])

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Use either a literal prompt argument OR --file/--glob", stderr.getvalue())

    def test_main_file_mode_calls_run_from_files(self):
        os.environ["OPENAI_COMPAT_API_KEY"] = "sk-compat"
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
                        "--provider",
                        "openai-compat",
                        "--endpoint",
                        "http://127.0.0.1:1234/v1",
                        "--file",
                        str(path),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(run_from_files.call_count, 1)
            called_files = run_from_files.call_args.kwargs["files"]
            self.assertEqual([Path(p) for p in called_files], [path])

    def test_main_glob_mode_expands_and_calls_run_from_files(self):
        os.environ["OPENAI_COMPAT_API_KEY"] = "sk-compat"
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
                        "--provider",
                        "openai-compat",
                        "--endpoint",
                        "http://127.0.0.1:1234/v1",
                        "--glob",
                        str(root / "*.md"),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertEqual(stderr.getvalue(), "")
            called_files = [Path(p) for p in run_from_files.call_args.kwargs["files"]]
            self.assertEqual(called_files, [root / "a.md", root / "b.md"])

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
                    provider="openai",
                    initial_kv={},
                    print_tools=False,
                    fewshots=False,
                    show_system_instruction=False,
                    dump_context=False,
                )

            self.assertEqual(code, 1)
            self.assertIn("Run summary:", stdout.getvalue())
            self.assertIn("passcase", stdout.getvalue())
            self.assertIn("failcase", stderr.getvalue())
            self.assertIn("broken.md", stderr.getvalue())
            self.assertIn("tool call sequence mismatch", stderr.getvalue())
            self.assertIn("missing YAML frontmatter closing delimiter", stderr.getvalue())
