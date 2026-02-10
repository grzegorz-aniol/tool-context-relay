import os
from pathlib import Path


def pytest_addoption(parser) -> None:
    group = parser.getgroup("tool-context-relay")
    group.addoption(
        "--profile",
        action="store",
        default="all",
        choices=("all", "openai", "bielik", "qwen"),
        help="Run integration scenarios only for the selected profile.",
    )
    group.addoption(
        "--model",
        action="append",
        default=[],
        help="Override integration scenario models. Repeatable; omit to use configured defaults; use 'all' to disable override.",
    )
    group.addoption(
        "--prompt-case",
        action="append",
        default=[],
        help="Run integration scenarios only for the selected prompt case(s) (e.g. case1, 1, case1.md). Repeatable; omit for all.",
    )


def pytest_generate_tests(metafunc) -> None:
    if metafunc.function.__name__ != "test_scenarios_integration":
        return

    from tool_context_relay.testing.integration_matrix import build_integration_matrix

    repo_root = Path(__file__).resolve().parents[1]
    prompt_cases_dir = repo_root / "prompts"

    selected_profile = metafunc.config.getoption("--profile")
    selected_models = metafunc.config.getoption("--model") or []
    selected_prompt_cases = metafunc.config.getoption("--prompt-case") or []

    params, ids = build_integration_matrix(
        cases_dir=prompt_cases_dir,
        profile_option=selected_profile,
        model_options=list(selected_models),
        prompt_case_options=[str(x) for x in selected_prompt_cases],
        env=os.environ,
    )

    metafunc.parametrize(
        (
            "profile",
            "model",
            "case_id",
            "prompt",
            "forbidden_tools",
            "tool_calls",
        ),
        params,
        ids=ids,
    )
