def _build_server_env() -> dict[str, str]:
    """Build the environment dict for the server subprocess.

    Copies `os.environ`, sets required flags, and strips auth-related variables
    that are not needed (and could interfere) for the local dev server.

    Returns:
        Environment dict for `subprocess.Popen`.
    """
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["LANGGRAPH_AUTH_TYPE"] = "noop"
    for key in (
        "LANGGRAPH_AUTH",
        "LANGGRAPH_CLOUD_LICENSE_KEY",
        "LANGSMITH_CONTROL_PLANE_API_KEY",
        "LANGSMITH_TENANT_ID",
    ):
        env.pop(key, None)
    return env


# ---------------------------------------------------------------------------
# ServerProcess
# ---------------------------------------------------------------------------


class ServerProcess:
    """Manages a `langgraph dev` server subprocess.

    Focuses on subprocess lifecycle (start, stop, restart) and health checking.
    Env-var management for restarts (e.g. configuration changes requiring a full
    restart) is handled by `_scoped_env_overrides`, keeping this class focused
    on process management.
    """

    def __init__(
        self,
        *,
        host: str = _DEFAULT_HOST,
        port: int = _DEFAULT_PORT,
        config_dir: str | Path | None = None,
        owns_config_dir: bool = False,
    ) -> None:
        """Initialize server process manager.

        Args:
            host: Host to bind the server to.
