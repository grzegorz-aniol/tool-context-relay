from pathlib import Path

import pytest

from tool_context_relay.testing.prompt_cases import (
    expand_wildcard_pattern,
    load_prompt_case_from_file,
    load_prompt_cases,
)


def _write_case(path: Path, *, frontmatter: str, body: str) -> None:
    path.write_text(f"---\n{frontmatter}\n---\n{body}\n", encoding="utf-8")


def test_load_prompt_cases_parses_frontmatter_and_body(tmp_path: Path) -> None:
    cases_dir = tmp_path / "prompts"
    cases_dir.mkdir()

    _write_case(
        cases_dir / "case1.md",
        frontmatter="""
id: case1
forbidden_tools:
  - google_drive_write_file
tool_calls:
  - tool_name: yt_transcribe
    opaque_id_result: true
  - tool_name: deep_check
    opaque_id_input: true
    allow_multiple: true
""".strip(),
        body="hello world",
    )

    [case] = load_prompt_cases(cases_dir)
    assert case.case_id == "case1"
    assert case.prompt == "hello world"
    assert case.forbidden_tools == {"google_drive_write_file"}
    assert [exp.tool_name for exp in case.tool_calls] == ["yt_transcribe", "deep_check"]
    assert case.tool_calls[0].opaque_id_result is True
    assert case.tool_calls[0].opaque_id_input is False
    assert case.tool_calls[0].allow_multiple is False
    assert case.tool_calls[1].opaque_id_input is True
    assert case.tool_calls[1].opaque_id_result is False
    assert case.tool_calls[1].allow_multiple is True


def test_load_prompt_cases_normalizes_numeric_case_id(tmp_path: Path) -> None:
    cases_dir = tmp_path / "prompts"
    cases_dir.mkdir()

    _write_case(cases_dir / "case2.md", frontmatter="id: 2", body="x")
    [case] = load_prompt_cases(cases_dir)
    assert case.case_id == "case2"


def test_load_prompt_cases_requires_frontmatter(tmp_path: Path) -> None:
    cases_dir = tmp_path / "prompts"
    cases_dir.mkdir()
    (cases_dir / "case1.md").write_text("no frontmatter", encoding="utf-8")

    with pytest.raises(ValueError, match="frontmatter"):
        load_prompt_cases(cases_dir)


def test_load_prompt_case_from_file_allows_no_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "plain.md"
    path.write_text("hello world", encoding="utf-8")

    case, body = load_prompt_case_from_file(path)
    assert case is None
    assert body == "hello world"


def test_load_prompt_case_from_file_rejects_non_mapping_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "bad.md"
    path.write_text("---\n- not-a-mapping\n---\nhello\n", encoding="utf-8")

    with pytest.raises(TypeError, match="frontmatter must be a mapping"):
        load_prompt_case_from_file(path)


def test_expand_wildcard_pattern_supports_question_mark(tmp_path: Path) -> None:
    (tmp_path / "case1.md").write_text("x", encoding="utf-8")
    (tmp_path / "case2.md").write_text("y", encoding="utf-8")
    (tmp_path / "case10.md").write_text("z", encoding="utf-8")

    matches = expand_wildcard_pattern(str(tmp_path / "case?.md"))
    assert [p.name for p in matches] == ["case1.md", "case2.md"]
