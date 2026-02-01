# AGENT.md — Coding Agent Playbook (Python)

## Skills

Use the `python-developer` skill for any changes to Python code, project structure, tests, or dependencies.

## Tech Stack

Project's tech stack:
* Python 3.14
* CLI based application
* uv as package management system - use `uv` commands for package management and running scripts.
  * never update or change dependencies by manipulations in uv.lock or uv.toml directly, always use `uv add` or `uv remove` command and then `uv sync`.

## Development task

Always follow this pattern:
* plan solution
* implement solution
* verify solution, try to find mistake or inconsistency
* write tests for new features and bug fixes
* always verify with running pytest on all tests, there is 'ci' Makefile target you should run for it.
* if you modified arguments of CLI commands, update README.md
* If you made some changes in a round, make a retrospection of the whole process. When you were solving a task did you notice any important misunderstanding, wrong approach, wrong tool calls, anything that user had to explain, change you did. Do you see something could be improved in previously provided rules, content of skills? If so, propose an update and after user's confirmation you can do it.

Never make modifications without a permission that are out of the plan and scope of the task!

## Environment notes (Codex CLI)

* `uv run ...` and `make ci` may need access to uv’s global cache under `~/.cache/uv`.
  * In sandboxed runs this can show up as “Operation not permitted”; the agent should rerun those commands with approval/escalated permissions.
  * Documenting this avoids wasted cycles when CI is the next step and makes failures actionable immediately.

