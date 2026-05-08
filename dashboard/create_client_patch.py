def create_client(
    model: str,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[LLMConfig] = None,
) -> LLMClient:
    import os as _os
    from dashboard.lib.settings.resolver import get_settings_resolver

    if provider is None:
        provider = _detect_provider_from_model(model)

    resolver = get_settings_resolver()
    master_settings = resolver.get_master_settings()
    providers = master_settings.providers if master_settings else None

    if provider in ("google", "google-genai", "google_gemini", "google-vertex"):
        base_url = _get_base_url(provider)
        is_vertex = provider == "google-vertex"
        if is_vertex and base_url:
            region = _os.environ.get("VERTEX_LOCATION", "global")
            project = _os.environ.get("GOOGLE_CLOUD_PROJECT", "")
            base_url = base_url.replace("{region}", region).replace("{project}", project)
        api_key = api_key or _os.environ.get("OSTWIN_API_KEY") or _os.environ.get("GOOGLE_API_KEY")
        return GoogleClient(model=model, api_key=api_key, base_url=base_url, config=config, vertexai=is_vertex)

    if provider == "openai-compatible":
        cfg = providers.openai_compatible if providers else None
        base_url = (cfg.base_url if cfg and cfg.base_url else _os.environ.get("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:8000"))
        # we resolve api_key_ref by calling get_effective_settings? No, vault refs are replaced in resolve_role or we can use get() on vault directly.
        # wait, the master_settings just has api_key_ref which could be a vault ref or empty.
        # it is better to resolve it. In resolve_role it resolves vault refs.
        # If we use _os.environ it is ok as a fallback.
        # Actually in master settings, vault refs look like `${vault:providers/openai_compatible}`.
        # We should probably use the vault directly or use effective settings.
        # But we don't have role context here.
