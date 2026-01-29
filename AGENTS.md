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
* If you made some changes in a round, make a retrospection of the whole process. When you were solving a task did you notice any important misunderstanding, wrong approach, wrong tool calls, anything that user had to explain, change you did. Do you see something could be improved in previously provided rules, content of skills? If so, propose an update and after user's confirmation you can do it.
