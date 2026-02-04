from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ToolCallExpectation:
    tool_name: str
    opaque_id_input: bool = False
    opaque_id_result: bool = False


@dataclass(frozen=True)
class PromptCase:
    case_id: str
    prompt: str
    forbidden_tools: set[str]
    tool_calls: list[ToolCallExpectation]
    expect_internal_resolve: bool


def _split_frontmatter(markdown: str) -> tuple[str, str]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing YAML frontmatter delimiter '---' on the first line")

    end_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("missing YAML frontmatter closing delimiter '---'")

    frontmatter = "\n".join(lines[1:end_idx]).strip()
    body = "\n".join(lines[end_idx + 1 :]).strip()
    return frontmatter, body


def try_split_frontmatter(markdown: str) -> tuple[dict[str, object] | None, str]:
    """Try to split frontmatter from markdown content.

    Returns (frontmatter_dict, body) if frontmatter exists, or (None, body) if not.
    Raises ValueError if frontmatter delimiters are malformed.
    """
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        # No frontmatter - return entire content as body
        return None, markdown.strip()

    end_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        raise ValueError("missing YAML frontmatter closing delimiter '---'")

    frontmatter_str = "\n".join(lines[1:end_idx]).strip()
    body = "\n".join(lines[end_idx + 1 :]).strip()

    if not body:
        raise ValueError("prompt body is empty")

    frontmatter_obj = yaml.safe_load(frontmatter_str) if frontmatter_str else {}
    if frontmatter_obj is None:
        frontmatter_obj = {}
    if not isinstance(frontmatter_obj, dict):
        raise TypeError("frontmatter must be a mapping")

    return frontmatter_obj, body


def _normalize_case_id(raw: str) -> str:
    raw = raw.strip()
    raw = raw.removesuffix(".md").removesuffix(".txt")
    raw = raw.rsplit("/", 1)[-1]
    raw = raw.rsplit("\\", 1)[-1]
    if raw.isdigit():
        return f"case{raw}"
    return raw


def _as_str_set(value: object) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError("expected a list of strings")
    return set(value)


def _parse_tool_calls(value: object) -> list[ToolCallExpectation]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("expected a list of mappings")

    expectations: list[ToolCallExpectation] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise TypeError(f"expected mapping at index {idx}")

        tool_name = item.get("tool_name")
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise TypeError(f"tool_name must be a non-empty string (index {idx})")

        opaque_id_input = item.get("opaque_id_input", False)
        opaque_id_result = item.get("opaque_id_result", False)
        if not isinstance(opaque_id_input, bool):
            raise TypeError(f"opaque_id_input must be a boolean (index {idx})")
        if not isinstance(opaque_id_result, bool):
            raise TypeError(f"opaque_id_result must be a boolean (index {idx})")

        expectations.append(
            ToolCallExpectation(
                tool_name=tool_name,
                opaque_id_input=opaque_id_input,
                opaque_id_result=opaque_id_result,
            )
        )

    return expectations


def _parse_frontmatter_to_case(
    frontmatter_obj: dict[str, object] | None,
    body: str,
    case_id_source: str,
) -> PromptCase | None:
    """Parse frontmatter dict into PromptCase, or return None if no frontmatter."""
    if frontmatter_obj is None:
        return None

    case_id = _normalize_case_id(str(frontmatter_obj.get("id") or case_id_source))
    forbidden_tools = _as_str_set(frontmatter_obj.get("forbidden_tools"))
    tool_calls = _parse_tool_calls(frontmatter_obj.get("tool_calls"))
    expect_internal_resolve_raw = frontmatter_obj.get("expect_internal_resolve", False)
    if not isinstance(expect_internal_resolve_raw, bool):
        raise TypeError("expect_internal_resolve must be a boolean")

    return PromptCase(
        case_id=case_id,
        prompt=body,
        forbidden_tools=forbidden_tools,
        tool_calls=tool_calls,
        expect_internal_resolve=expect_internal_resolve_raw,
    )


def load_prompt_case_from_file(path: Path) -> tuple[PromptCase | None, str]:
    """Load a single prompt case from a file.

    Returns:
        A tuple of (PromptCase | None, body):
        - If the file has frontmatter, returns (PromptCase, body)
        - If the file has no frontmatter, returns (None, body)

    Raises:
        ValueError: If frontmatter is malformed
        TypeError: If frontmatter fields have wrong types
    """
    markdown = path.read_text(encoding="utf-8")
    frontmatter_obj, body = try_split_frontmatter(markdown)

    if not body:
        raise ValueError(f"prompt body is empty in {path}")

    case = _parse_frontmatter_to_case(frontmatter_obj, body, path.stem)
    return case, body


def expand_wildcard_pattern(pattern: str, base_dir: Path | None = None) -> list[Path]:
    """Expand a wildcard pattern to a list of file paths.

    Args:
        pattern: A glob pattern like "*.md", "prompt_cases/*.md", "case*.md"
        base_dir: Optional base directory to resolve relative patterns against

    Returns:
        Sorted list of matching file paths
    """
    path_pattern = Path(pattern)

    if base_dir and not path_pattern.is_absolute():
        # If pattern is relative and base_dir provided, resolve against base_dir
        glob_path = base_dir / path_pattern
    else:
        glob_path = path_pattern

    raw_pattern = str(glob_path)
    # Use the parent directory of the pattern for globbing
    if any(ch in raw_pattern for ch in ("*", "?", "[")):
        # Find the first component with a wildcard
        parts = glob_path.parts
        wildcard_idx = next(
            (i for i, p in enumerate(parts) if "*" in p or "?" in p or "[" in p),
            len(parts),
        )

        if wildcard_idx == 0:
            # Pattern starts with wildcard, use current directory
            search_dir = Path(".")
            glob_pattern = str(glob_path)
        else:
            # Use directory up to first wildcard
            search_dir = Path(*parts[:wildcard_idx])
            glob_pattern = str(Path(*parts[wildcard_idx:]))

        if not search_dir.exists():
            return []

        return sorted(search_dir.glob(glob_pattern))
    else:
        # No wildcards - check if it's a single file
        if glob_path.exists() and glob_path.is_file():
            return [glob_path]
        return []


def load_prompt_cases(cases_dir: Path) -> list[PromptCase]:
    cases: list[PromptCase] = []
    for path in sorted(cases_dir.glob("*.md")):
        markdown = path.read_text(encoding="utf-8")
        frontmatter_str, body = _split_frontmatter(markdown)
        if not body:
            raise ValueError(f"prompt body is empty in {path}")

        frontmatter_obj = yaml.safe_load(frontmatter_str) if frontmatter_str else {}
        if frontmatter_obj is None:
            frontmatter_obj = {}
        if not isinstance(frontmatter_obj, dict):
            raise TypeError(f"frontmatter must be a mapping in {path}")

        case_id = _normalize_case_id(str(frontmatter_obj.get("id") or path.stem))
        forbidden_tools = _as_str_set(frontmatter_obj.get("forbidden_tools"))
        tool_calls = _parse_tool_calls(frontmatter_obj.get("tool_calls"))
        expect_internal_resolve_raw = frontmatter_obj.get("expect_internal_resolve", False)
        if not isinstance(expect_internal_resolve_raw, bool):
            raise TypeError(f"expect_internal_resolve must be a boolean in {path}")

        cases.append(
            PromptCase(
                case_id=case_id,
                prompt=body,
                forbidden_tools=forbidden_tools,
                tool_calls=tool_calls,
                expect_internal_resolve=expect_internal_resolve_raw,
            )
        )

    if not cases:
        raise FileNotFoundError(f"no prompt case files found in {cases_dir} (expected *.md)")

    return cases
