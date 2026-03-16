"""
cli.py — deepagents TUI engine helpers for ostwin chat.

This module is a minimized extraction from deepagents_cli.cli_main,
keeping only the 4 functions consumed by chat.py:

    check_cli_dependencies()      — verify textual/requests/dotenv/tavily
    run_textual_cli_async()       — run the interactive Textual TUI
    _check_mcp_project_trust()   — gate project-level stdio MCP servers
    _print_session_stats()        — print token-usage table after exit

Everything else (parse_args, cli_main, ACP server, stdin piping,
non-interactive runner, subcommands) has been removed.
"""

import warnings

warnings.filterwarnings("ignore", module="langchain_core._api.deprecation")
warnings.filterwarnings("ignore", message=".*Pydantic V1.*", category=UserWarning)

import asyncio
import contextlib
import importlib.util
import logging
import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool
    from deepagents_cli.app import AppResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def check_cli_dependencies() -> None:
    """Verify that the required CLI optional packages are installed."""
    missing = []

    if importlib.util.find_spec("requests") is None:
        missing.append("requests")
    if importlib.util.find_spec("dotenv") is None:
        missing.append("python-dotenv")
    if importlib.util.find_spec("tavily") is None:
        missing.append("tavily-python")
    if importlib.util.find_spec("textual") is None:
        missing.append("textual")

    if missing:
        print("\nMissing required CLI dependencies!")
        print("\nThe following packages are required to use the deepagents CLI:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nPlease install them with:")
        print("  pip install deepagents[cli]")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Core interactive TUI runner
# ---------------------------------------------------------------------------

async def run_textual_cli_async(
    assistant_id: str,
    *,
    auto_approve: bool = False,
    sandbox_type: str = "none",
    sandbox_id: str | None = None,
    sandbox_setup: str | None = None,
    model_name: str | None = None,
    model_params: dict[str, Any] | None = None,
    profile_override: dict[str, Any] | None = None,
    thread_id: str | None = None,
    is_resumed: bool = False,
    initial_prompt: str | None = None,
    enable_ask_user: bool = False,
    mcp_config_path: str | None = None,
    no_mcp: bool = False,
    trust_project_mcp: bool | None = None,
) -> "AppResult":
    """Run the Textual CLI interface (async).

    Args:
        assistant_id: Agent identifier for memory storage.
        auto_approve: Whether to auto-approve tool usage.
        sandbox_type: Type of sandbox (always "none" for chat mode).
        sandbox_id: Optional existing sandbox ID to reuse.
        sandbox_setup: Optional path to setup script.
        model_name: Optional model name to use.
        model_params: Extra kwargs to pass to the model.
        profile_override: Extra profile fields.
        thread_id: Thread ID (new or resumed).
        is_resumed: Whether this is a resumed session.
        initial_prompt: Optional prompt auto-submitted on start.
        enable_ask_user: Enable the ask_user tool.
        mcp_config_path: Optional path to MCP servers JSON config.
        no_mcp: Disable all MCP tool loading.
        trust_project_mcp: Controls project-level stdio server trust.

    Returns:
        AppResult with return_code and final thread_id.
    """
    from rich.text import Text

    from deepagents_cli.agent import create_cli_agent
    from deepagents_cli.app import run_textual_app
    from deepagents_cli.config import console, create_model, settings
    from deepagents_cli.model_config import ModelConfigError
    from deepagents_cli.sessions import get_checkpointer
    from deepagents_cli.tools import fetch_url, http_request, web_search

    try:
        result = create_model(
            model_name,
            extra_kwargs=model_params,
            profile_overrides=profile_override,
        )
    except ModelConfigError as e:
        from deepagents_cli.app import AppResult

        console.print(f"[bold red]Error:[/bold red] {e}")
        return AppResult(return_code=1, thread_id=None)

    model = result.model
    result.apply_to_settings()

    # Show thread info
    if is_resumed:
        msg = Text("Resuming thread: ", style="dim")
        msg.append(str(thread_id), style="dim")
        console.print(msg)
    else:
        msg = Text("Starting with thread: ", style="dim")
        msg.append(str(thread_id), style="dim")
        console.print(msg)

    async with get_checkpointer() as checkpointer:
        tools: list[BaseTool | Callable[..., Any] | dict[str, Any]] = [
            http_request,
            fetch_url,
        ]
        if settings.has_tavily:
            tools.append(web_search)

        # Load MCP tools
        mcp_session_manager = None
        mcp_server_info = None
        try:
            from deepagents_cli.mcp_tools import resolve_and_load_mcp_tools

            # Default to AGENT_DIR/mcp/mcp-config.json when not explicitly set
            resolved_mcp_config = mcp_config_path
            if not resolved_mcp_config and not no_mcp:
                _agents_dir = Path(__file__).resolve().parent.parent
                default_cfg = _agents_dir / "mcp" / "mcp-config.json"
                if default_cfg.exists():
                    resolved_mcp_config = str(default_cfg)

            (
                mcp_tools,
                mcp_session_manager,
                mcp_server_info,
            ) = await resolve_and_load_mcp_tools(
                explicit_config_path=resolved_mcp_config,
                no_mcp=no_mcp,
                trust_project_mcp=trust_project_mcp,
            )
            tools.extend(mcp_tools)
        except FileNotFoundError as e:
            console.print(f"[yellow]⚠ MCP config not found: {e} — continuing without MCP tools[/yellow]")
        except RuntimeError as e:
            console.print(f"[red]✗ Failed to load MCP tools: {e}[/red]")
            sys.exit(1)

        # Handle sandbox (chat mode always uses "none", kept for signature compat)
        sandbox_backend = None
        sandbox_cm = None

        if sandbox_type != "none":
            from deepagents_cli.integrations.sandbox_factory import create_sandbox

            try:
                sandbox_cm = create_sandbox(
                    sandbox_type,
                    sandbox_id=sandbox_id,
                    setup_script_path=sandbox_setup,
                )
                sandbox_backend = sandbox_cm.__enter__()  # noqa: PLC2801
            except (ImportError, ValueError, RuntimeError, NotImplementedError) as e:
                console.print()
                console.print("[red]Sandbox creation failed[/red]")
                console.print(Text(str(e), style="dim"))
                sys.exit(1)

        try:
            agent, composite_backend = create_cli_agent(
                model=model,
                assistant_id=assistant_id,
                tools=tools,
                sandbox=sandbox_backend,
                sandbox_type=sandbox_type if sandbox_type != "none" else None,
                auto_approve=auto_approve,
                enable_ask_user=enable_ask_user,
                checkpointer=checkpointer,
                mcp_server_info=mcp_server_info,
            )
        except Exception as e:
            logger.debug("Failed to create agent", exc_info=True)
            error_text = Text("Failed to create agent: ", style="red")
            error_text.append(str(e))
            console.print(error_text)
            if logger.isEnabledFor(logging.DEBUG):
                console.print(Text(traceback.format_exc(), style="dim"))
            sys.exit(1)

        from deepagents_cli.app import AppResult

        result = AppResult(return_code=1, thread_id=None)
        try:
            result = await run_textual_app(
                agent=agent,
                assistant_id=assistant_id,
                backend=composite_backend,
                auto_approve=auto_approve,
                enable_ask_user=enable_ask_user,
                cwd=Path.cwd(),
                thread_id=thread_id,
                initial_prompt=initial_prompt,
                checkpointer=checkpointer,
                tools=tools,
                sandbox=sandbox_backend,
                sandbox_type=sandbox_type if sandbox_type != "none" else None,
                mcp_server_info=mcp_server_info,
                profile_override=profile_override,
            )
        finally:
            if mcp_session_manager is not None:
                try:
                    await mcp_session_manager.cleanup()
                except Exception:
                    logger.warning("MCP session cleanup failed", exc_info=True)

            if sandbox_cm is not None:
                try:
                    sandbox_cm.__exit__(None, None, None)
                except Exception:
                    logger.warning("Sandbox cleanup failed", exc_info=True)

        return result


# ---------------------------------------------------------------------------
# Session stats printer
# ---------------------------------------------------------------------------

def _print_session_stats(stats: Any, console: Any) -> None:  # noqa: ANN401
    """Print a session-level usage stats table to the console on TUI exit.

    Args:
        stats: The cumulative session stats from the Textual app.
        console: Rich console for output.
    """
    from deepagents_cli.textual_adapter import SessionStats, print_usage_table

    if not isinstance(stats, SessionStats):
        return
    print_usage_table(stats, stats.wall_time_seconds, console)


# ---------------------------------------------------------------------------
# MCP project trust gate
# ---------------------------------------------------------------------------

def _check_mcp_project_trust(*, trust_flag: bool = False) -> bool | None:
    """Gate project-level MCP stdio servers with an interactive approval prompt.

    Args:
        trust_flag: Whether --trust-project-mcp was passed.

    Returns:
        True to allow, False to deny, None when no project stdio servers exist.
    """
    from deepagents_cli.mcp_tools import (
        classify_discovered_configs,
        discover_mcp_configs,
        extract_stdio_server_commands,
        load_mcp_config_lenient,
    )

    try:
        config_paths = discover_mcp_configs()
    except (OSError, RuntimeError):
        return None

    _, project_configs = classify_discovered_configs(config_paths)
    if not project_configs:
        return None

    all_stdio: list[tuple[str, str, list[str]]] = []
    for path in project_configs:
        cfg = load_mcp_config_lenient(path)
        if cfg is not None:
            all_stdio.extend(extract_stdio_server_commands(cfg))

    if not all_stdio:
        return None

    if trust_flag:
        return True

    from deepagents_cli.mcp_trust import (
        compute_config_fingerprint,
        is_project_mcp_trusted,
        trust_project_mcp,
    )
    from deepagents_cli.project_utils import find_project_root

    project_root = str((find_project_root() or Path.cwd()).resolve())
    fingerprint = compute_config_fingerprint(project_configs)

    if is_project_mcp_trusted(project_root, fingerprint):
        return True

    from rich.console import Console as _Console

    prompt_console = _Console(stderr=True)
    prompt_console.print()
    prompt_console.print("[bold yellow]Project MCP servers require approval:[/bold yellow]")
    for name, cmd, args in all_stdio:
        args_str = " ".join(args) if args else ""
        prompt_console.print(f'  [bold]"{name}"[/bold]:  {cmd} {args_str}')
    prompt_console.print()

    try:
        answer = input("Allow? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if answer == "y":
        trust_project_mcp(project_root, fingerprint)
        return True
    return False
