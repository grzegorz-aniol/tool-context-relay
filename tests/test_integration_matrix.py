from pathlib import Path

from tool_context_relay.testing.integration_matrix import build_integration_matrix


def _write_case(path: Path, *, frontmatter: str, body: str) -> None:
    path.write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")


def test_build_integration_matrix_model_override_for_profile(tmp_path: Path) -> None:
    cases_dir = tmp_path / "prompts"
    cases_dir.mkdir()

    _write_case(
        cases_dir / "case1.md",
        frontmatter="""
id: case1
tool_calls:
  - tool_name: yt_transcribe
    opaque_id_result: true
expect_internal_resolve: false
""".strip(),
        body="hello",
    )

    params, ids = build_integration_matrix(
        cases_dir=cases_dir,
        profile_option="openai",
        model_options=["Qwen/Qwen3-8B-GGUF:Q8_0"],
        prompt_case_options=[],
        env={},
    )

    assert len(params) == 1
    (profile, model, case_id, prompt, forbidden_tools, tool_calls, expect_internal_resolve) = params[0]
    assert profile == "openai"
    assert model == "Qwen/Qwen3-8B-GGUF:Q8_0"
    assert case_id == "case1"
    assert prompt == "hello"
    assert ids == ["openai-Qwen/Qwen3-8B-GGUF:Q8_0-case1"]


def test_build_integration_matrix_model_all_disables_override(tmp_path: Path) -> None:
    cases_dir = tmp_path / "prompts"
    cases_dir.mkdir()
    _write_case(cases_dir / "case1.md", frontmatter="id: case1", body="hello")

    params, _ids = build_integration_matrix(
        cases_dir=cases_dir,
        profile_option="openai",
        model_options=["all"],
        prompt_case_options=[],
        env={},
    )

    assert params[0][1] == "gpt-4.1-mini"


def test_build_integration_matrix_prompt_case_filter(tmp_path: Path) -> None:
    cases_dir = tmp_path / "prompts"
    cases_dir.mkdir()
    _write_case(cases_dir / "case1.md", frontmatter="id: case1", body="a")
    _write_case(cases_dir / "case2.md", frontmatter="id: case2", body="b")

    params, _ids = build_integration_matrix(
        cases_dir=cases_dir,
        profile_option="openai",
        model_options=["X"],
        prompt_case_options=["2"],
        env={},
    )

    assert len(params) == 1
    assert params[0][2] == "case2"
