import os
from pathlib import Path


def pytest_addoption(parser) -> None:
    group = parser.getgroup("tool-context-relay")
    group.addoption(
        "--provider",
        action="store",
        default="all",
        choices=("all", "openai", "openai-compat"),
        help="Run integration scenarios only for the selected provider.",
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
    prompt_cases_dir = repo_root / "prompt_cases"

    selected_provider = metafunc.config.getoption("--provider")
    selected_models = metafunc.config.getoption("--model") or []
    selected_prompt_cases = metafunc.config.getoption("--prompt-case") or []

    params, ids = build_integration_matrix(
        cases_dir=prompt_cases_dir,
        provider_option=selected_provider,
        model_options=list(selected_models),
        prompt_case_options=[str(x) for x in selected_prompt_cases],
        env=os.environ,
    )

    metafunc.parametrize(
        (
            "provider",
            "model",
            "case_id",
            "prompt",
            "forbidden_tools",
            "tool_calls",
            "expect_internal_resolve",
        ),
        params,
        ids=ids,
    )
