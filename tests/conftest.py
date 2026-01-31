def pytest_addoption(parser) -> None:
    group = parser.getgroup("tool-context-relay")
    group.addoption(
        "--provider",
        action="store",
        default="all",
        choices=("all", "openai", "openai-compat"),
        help="Run integration scenarios only for the selected provider.",
    )

