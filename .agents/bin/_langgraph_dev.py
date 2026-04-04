def dev(
    host: str,
    port: int,
    no_reload: bool,
    config: str,
    n_jobs_per_worker: int | None,
    no_browser: bool,
    debug_port: int | None,
    wait_for_client: bool,
    studio_url: str | None,
    allow_blocking: bool,
    tunnel: bool,
    server_log_level: str,
):
    """CLI entrypoint for running the LangGraph API server."""
    try:
        from langgraph_api.cli import run_server  # type: ignore
    except ImportError:
        py_version_msg = ""
        if sys.version_info < (3, 11):
            py_version_msg = (
                "\n\nNote: The in-mem server requires Python 3.11 or higher to be installed."
                f" You are currently using Python {sys.version_info.major}.{sys.version_info.minor}."
                ' Please upgrade your Python version before installing "langgraph-cli[inmem]".'
            )
        try:
            from importlib import util

            if not util.find_spec("langgraph_api"):
                raise click.UsageError(
                    "Required package 'langgraph-api' is not installed.\n"
                    "Please install it with:\n\n"
                    '    pip install -U "langgraph-cli[inmem]"'
                    f"{py_version_msg}"
                ) from None
        except ImportError:
            raise click.UsageError(
                "Could not verify package installation. Please ensure Python is up to date and\n"
                "langgraph-cli is installed with the 'inmem' extra: pip install -U \"langgraph-cli[inmem]\""
                f"{py_version_msg}"
            ) from None
        raise click.UsageError(
            "Could not import run_server. This likely means your installation is incomplete.\n"
            "Please ensure langgraph-cli is installed with the 'inmem' extra: pip install -U \"langgraph-cli[inmem]\""
            f"{py_version_msg}"
        ) from None

    config_json = langgraph_cli.config.validate_config_file(pathlib.Path(config))
    if config_json.get("node_version"):
        raise click.UsageError(
            "In-mem server for JS graphs is not supported in this version of the LangGraph CLI. Please use `npx @langchain/langgraph-cli` instead."
        ) from None

    cwd = os.getcwd()
    sys.path.append(cwd)
    dependencies = config_json.get("dependencies", [])
    for dep in dependencies:
        dep_path = pathlib.Path(cwd) / dep
        if dep_path.is_dir() and dep_path.exists():
            sys.path.append(str(dep_path))

    graphs = config_json.get("graphs", {})

    run_server(
        host,
        port,
        not no_reload,
        graphs,
        n_jobs_per_worker=n_jobs_per_worker,
        open_browser=not no_browser,
        debug_port=debug_port,
        env=config_json.get("env"),
        store=config_json.get("store"),
        wait_for_client=wait_for_client,
        auth=config_json.get("auth"),
        http=config_json.get("http"),
        ui=config_json.get("ui"),
        ui_config=config_json.get("ui_config"),
        webhooks=config_json.get("webhooks"),
        studio_url=studio_url,
        allow_blocking=allow_blocking,
        tunnel=tunnel,
        server_level=server_log_level,
