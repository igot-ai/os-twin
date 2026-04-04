class ServerConfig:
    """Full configuration payload passed from the CLI to the server subprocess.

    Serialized to/from `DA_SERVER_*` environment variables so that the server
    graph (which runs in a separate Python interpreter) can reconstruct the
    CLI's intent without sharing memory.
    """

    model: str | None = None
    model_params: dict[str, Any] | None = None
    assistant_id: str = _DEFAULT_ASSISTANT_ID
    system_prompt: str | None = None
    auto_approve: bool = False
    interactive: bool = True
    enable_shell: bool = True
    enable_ask_user: bool = False
    enable_memory: bool = True
    enable_skills: bool = True
    sandbox_type: str | None = None
    sandbox_id: str | None = None
    sandbox_setup: str | None = None
    cwd: str | None = None
    project_root: str | None = None
    mcp_config_path: str | None = None
    no_mcp: bool = False
    trust_project_mcp: bool | None = None

    def __post_init__(self) -> None:
        """Normalize fields that have canonical representations."""
        if self.sandbox_type == "none":
            object.__setattr__(self, "sandbox_type", None)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_env(self) -> dict[str, str | None]:
        """Serialize this config to a `DA_SERVER_*` env-var mapping.

        `None` values signal that the variable should be *cleared* from the
        environment (rather than set to an empty string), so callers can
        iterate and set or clear each variable in `os.environ`.

        Returns:
            Dict mapping env-var suffixes (without the prefix) to their
                string values or `None`.
        """
        return {
            "MODEL": self.model,
            "MODEL_PARAMS": (
                json.dumps(self.model_params) if self.model_params is not None else None
            ),
            "ASSISTANT_ID": self.assistant_id,
            "SYSTEM_PROMPT": self.system_prompt,
            "AUTO_APPROVE": str(self.auto_approve).lower(),
            "INTERACTIVE": str(self.interactive).lower(),
            "ENABLE_SHELL": str(self.enable_shell).lower(),
            "ENABLE_ASK_USER": str(self.enable_ask_user).lower(),
            "ENABLE_MEMORY": str(self.enable_memory).lower(),
            "ENABLE_SKILLS": str(self.enable_skills).lower(),
            "SANDBOX_TYPE": self.sandbox_type,
            "SANDBOX_ID": self.sandbox_id,
            "SANDBOX_SETUP": self.sandbox_setup,
            "CWD": self.cwd,
            "PROJECT_ROOT": self.project_root,
            "MCP_CONFIG_PATH": self.mcp_config_path,
