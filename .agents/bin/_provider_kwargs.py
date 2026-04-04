def _get_provider_kwargs(
    provider: str, *, model_name: str | None = None
) -> dict[str, Any]:
    """Get provider-specific kwargs from the config file.

    Reads `base_url`, `api_key_env`, and the `params` table from the user's
    `config.toml` for the given provider.

    When `model_name` is provided, per-model overrides from the `params`
    sub-table are shallow-merged on top.

    Args:
        provider: Provider name (e.g., openai, anthropic, fireworks, ollama).
        model_name: Optional model name for per-model overrides.

    Returns:
        Dictionary of provider-specific kwargs.
    """
    config = ModelConfig.load()
    result: dict[str, Any] = config.get_kwargs(provider, model_name=model_name)
    base_url = config.get_base_url(provider)
    if base_url:
        result["base_url"] = base_url
    api_key_env = config.get_api_key_env(provider)
    if api_key_env:
        api_key = os.environ.get(api_key_env)
        if api_key:
            result["api_key"] = api_key

    if provider == "openrouter":
        _apply_openrouter_defaults(result)

    return result


def _create_model_from_class(
    class_path: str,
    model_name: str,
    provider: str,
    kwargs: dict[str, Any],
) -> BaseChatModel:
    """Import and instantiate a custom `BaseChatModel` class.

    Args:
        class_path: Fully-qualified class in `module.path:ClassName` format.
        model_name: Model identifier to pass as `model` kwarg.
        provider: Provider name (for error messages).
        kwargs: Additional keyword arguments for the constructor.

    Returns:
        Instantiated `BaseChatModel`.

    Raises:
        ModelConfigError: If the class cannot be imported, is not a
            `BaseChatModel` subclass, or fails to instantiate.
    """
    from langchain_core.language_models import (
        BaseChatModel as _BaseChatModel,  # Runtime import; module level is typing only
    )

    if ":" not in class_path:
        msg = (
            f"Invalid class_path '{class_path}' for provider '{provider}': "
            "must be in module.path:ClassName format"
        )
        raise ModelConfigError(msg)

    module_path, class_name = class_path.rsplit(":", 1)

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        msg = f"Could not import module '{module_path}' for provider '{provider}': {e}"
        raise ModelConfigError(msg) from e
