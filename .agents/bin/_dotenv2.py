        `True` when a dotenv file was loaded, `False` otherwise.
    """
    if start_path is None:
        return dotenv.load_dotenv(override=override)

    dotenv_path = _find_dotenv_from_start_path(start_path)
    if dotenv_path is None:
        return False
    return dotenv.load_dotenv(dotenv_path=dotenv_path, override=override)


_bootstrap_project_context = _get_server_project_context()
_bootstrap_start_path = (
    _bootstrap_project_context.user_cwd if _bootstrap_project_context else None
)

_load_dotenv(start_path=_bootstrap_start_path)

# CRITICAL: Override LANGSMITH_PROJECT to route agent traces to separate project
# LangSmith reads LANGSMITH_PROJECT at invocation time, so we override it here
# and preserve the user's original value for shell commands
_deepagents_project = os.environ.get("DEEPAGENTS_LANGSMITH_PROJECT")
_original_langsmith_project = os.environ.get("LANGSMITH_PROJECT")
if _deepagents_project:
    # Override LANGSMITH_PROJECT for agent traces
    os.environ["LANGSMITH_PROJECT"] = _deepagents_project

from deepagents_cli.model_config import (  # noqa: E402  # Import after os.environ setup above
    ModelConfig,
    ModelConfigError,
    ModelSpec,
