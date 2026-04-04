

def _parse_env_from_config(
    config_json: dict, config_path: pathlib.Path
) -> dict[str, str]:
    """Resolve env vars from langgraph.json 'env' field or a .env fallback."""
    env_field = config_json.get("env")
    # validate_config_file will default env to {}
    if isinstance(env_field, dict) and env_field:
        return {str(k): str(v) for k, v in env_field.items()}
    if isinstance(env_field, str):
        env_path = (config_path.parent / env_field).resolve()
        if not env_path.exists():
            click.secho(
                f"Warning: env file '{env_field}' specified in langgraph.json not found.",
                fg="yellow",
            )
            return {}
    else:
        env_path = pathlib.Path.cwd() / ".env"
    return {k: v for k, v in dotenv_values(env_path).items() if v is not None}


def _secrets_from_env(
    env_vars: dict[str, str],
) -> list[dict[str, str]]:
    """Convert env dict to secrets list, filtering reserved vars with warnings."""
    secrets: list[dict[str, str]] = []
    for name, value in env_vars.items():
        if name in RESERVED_ENV_VARS:
            click.secho(f"   Skipping reserved env var: {name}", fg="yellow")
            continue
        if not value:
            continue
        secrets.append({"name": name, "value": value})
    return secrets


_TERMINAL_STATUSES = frozenset(
    [
        "DEPLOYED",
        "CREATE_FAILED",
        "BUILD_FAILED",
        "DEPLOY_FAILED",
        "SKIPPED",
    ]
