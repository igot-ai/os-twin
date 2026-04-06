"""
ostwin chat — Interactive AI chat session powered by deepagents.

Simplified entry point that reuses the Textual TUI engine from cli.py,
stripping away subcommands (list/reset/skills/threads), non-interactive
mode, ACP server, and sandbox features.

Usage:
    ostwin chat [options]
    ostwin chat -a coder -M google-vertex/gemini-3-flash-preview
    ostwin chat -m "Explain the architecture"
    ostwin chat -r                     # Resume most recent thread
    ostwin chat -r <thread-id>         # Resume specific thread
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv("~/.ostwin/.env")

from os import getenv

logger = logging.getLogger(__name__)

# Add bin/ parent to path so we can import cli module
_BIN_DIR = Path(__file__).resolve().parent
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))

_DEFAULT_AGENT_NAME = "agent"


def _show_help() -> None:
    """Print styled help for ostwin chat."""
    help_text = """\
\033[1mostwin chat\033[0m — Interactive AI Chat Session

\033[2mPowered by deepagents Textual TUI\033[0m

\033[1mUsage:\033[0m
  ostwin chat [OPTIONS]

\033[1mOptions:\033[0m
  -a, --agent NAME         Agent to use (default: agent)
  -M, --model MODEL        Model to use (e.g., google-vertex/gemini-3-flash-preview)
  --model-params JSON      Extra model kwargs as JSON string
  -m, --message TEXT       Initial prompt to auto-submit on start
  -r, --resume [ID]        Resume thread: -r for most recent, -r ID for specific
  --auto-approve           Auto-approve all tool calls (use with caution)
  --ask-user               Enable ask_user interactive questions
  --mcp-config PATH        Load MCP tools from config file
  --no-mcp                 Disable all MCP tool loading
  --trust-project-mcp      Trust project MCP configs (skip approval)
  --shell-allow-list CMDS  Comma-separated commands, 'recommended', or 'all'
  -h, --help               Show this help message

\033[1mExamples:\033[0m
  ostwin chat                              # Start new interactive session
  ostwin chat -a coder                     # Use the 'coder' agent
  ostwin chat -M google-vertex/gemini-3-flash-preview    # Use specific model
  ostwin chat -m "Explain the codebase"    # Auto-submit initial prompt
  ostwin chat -r                           # Resume most recent thread
  ostwin chat --auto-approve               # Auto-approve tool calls
"""
    print(help_text)


def parse_chat_args() -> argparse.Namespace:
    """Parse arguments for the simplified chat mode.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="ostwin chat",
        description="Interactive AI chat session",
        add_help=False,
    )

    parser.add_argument(
        "-a", "--agent",
        default=_DEFAULT_AGENT_NAME,
        metavar="NAME",
        help="Agent to use (e.g., coder, researcher)",
    )

    parser.add_argument(
        "-M", "--model",
        metavar="MODEL",
        help="Model to use (e.g., google-vertex/gemini-3-flash-preview). "
             "Provider is auto-detected from model name.",
    )

    parser.add_argument(
        "--model-params",
        metavar="JSON",
        help="Extra kwargs to pass to the model as JSON string",
    )

    parser.add_argument(
        "-m", "--message",
        dest="initial_prompt",
        metavar="TEXT",
        help="Initial prompt to auto-submit when session starts",
    )

    parser.add_argument(
        "-r", "--resume",
        dest="resume_thread",
        nargs="?",
        const="__MOST_RECENT__",
        default=None,
        metavar="ID",
        help="Resume thread: -r for most recent, -r <ID> for specific",
    )

    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve all tool calls without prompting",
    )

    parser.add_argument(
        "--ask-user",
        action="store_true",
        help="Enable the ask_user tool for agent questions",
    )

    parser.add_argument(
        "--mcp-config",
        metavar="PATH",
        help="Path to MCP servers JSON configuration file",
    )

    parser.add_argument(
        "--no-mcp",
        action="store_true",
        help="Disable all MCP tool loading",
    )

    parser.add_argument(
        "--trust-project-mcp",
        action="store_true",
        help="Trust project-level MCP configs (skip approval prompt)",
    )

    parser.add_argument(
        "--shell-allow-list",
        metavar="CMDS",
        help="Comma-separated commands, 'recommended', or 'all'",
    )

    parser.add_argument(
        "-h", "--help",
        action="store_true",
        default=False,
        help="Show this help message",
    )

    return parser.parse_args()


def chat_main() -> None:
    """Entry point for ostwin chat mode."""
    # Fix for gRPC fork issue on macOS
    if sys.platform == "darwin":
        os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"

    args = parse_chat_args()

    if args.help:
        _show_help()
        sys.exit(0)

    # --- Heavy imports after arg parse (fast --help) ---
    from cli import check_cli_dependencies, run_textual_cli_async

    check_cli_dependencies()

    from deepagents_cli.config import console, settings

    try:
        # Parse --model-params JSON
        model_params: dict[str, Any] | None = None
        raw_kwargs = getattr(args, "model_params", None)
        if raw_kwargs:
            try:
                model_params = json.loads(raw_kwargs)
            except json.JSONDecodeError as e:
                console.print(
                    f"[bold red]Error:[/bold red] --model-params is not valid JSON: {e}"
                )
                sys.exit(1)
            if not isinstance(model_params, dict):
                console.print(
                    "[bold red]Error:[/bold red] --model-params must be a JSON object"
                )
                sys.exit(1)

        # Validate mutually exclusive flags
        if getattr(args, "no_mcp", False) and getattr(args, "mcp_config", None):
            console.print(
                "[bold red]Error:[/bold red] --no-mcp and --mcp-config "
                "are mutually exclusive"
            )
            sys.exit(2)

        # Apply shell-allow-list
        if args.shell_allow_list:
            from deepagents_cli.config import parse_shell_allow_list
            settings.shell_allow_list = parse_shell_allow_list(args.shell_allow_list)

        # --- Thread resume/create ---
        from deepagents_cli.sessions import (
            find_similar_threads,
            generate_thread_id,
            get_most_recent,
            get_thread_agent,
            thread_exists,
        )

        thread_id = None
        is_resumed = False

        if args.resume_thread == "__MOST_RECENT__":
            agent_filter = args.agent if args.agent != _DEFAULT_AGENT_NAME else None
            thread_id = asyncio.run(get_most_recent(agent_filter))
            if thread_id:
                is_resumed = True
                agent_name = asyncio.run(get_thread_agent(thread_id))
                if agent_name:
                    args.agent = agent_name
            else:
                if agent_filter:
                    console.print(
                        f"[yellow]No previous thread for '{args.agent}', "
                        "starting new.[/yellow]"
                    )
                else:
                    console.print("[yellow]No previous threads, starting new.[/yellow]")

        elif args.resume_thread:
            if asyncio.run(thread_exists(args.resume_thread)):
                thread_id = args.resume_thread
                is_resumed = True
                if args.agent == _DEFAULT_AGENT_NAME:
                    agent_name = asyncio.run(get_thread_agent(thread_id))
                    if agent_name:
                        args.agent = agent_name
            else:
                console.print(f"[red]Thread '{args.resume_thread}' not found.[/red]")

                similar = asyncio.run(find_similar_threads(args.resume_thread))
                if similar:
                    console.print()
                    console.print("[yellow]Did you mean?[/yellow]")
                    for tid in similar:
                        console.print(f"  [cyan]ostwin chat -r {tid}[/cyan]")
                    console.print()
                sys.exit(1)

        if thread_id is None:
            thread_id = generate_thread_id()

        # --- MCP trust check ---
        from cli import _check_mcp_project_trust

        mcp_trust_decision = _check_mcp_project_trust(
            trust_flag=getattr(args, "trust_project_mcp", False),
        )

        # --- Launch Textual TUI ---
        return_code = 0
        try:
            result = asyncio.run(
                run_textual_cli_async(
                    assistant_id=args.agent,
                    auto_approve=args.auto_approve,
                    sandbox_type="none",
                    model_name=getattr(args, "model", None),
                    model_params=model_params,
                    thread_id=thread_id,
                    is_resumed=is_resumed,
                    initial_prompt=getattr(args, "initial_prompt", None),
                    enable_ask_user=getattr(args, "ask_user", False),
                    mcp_config_path=getattr(args, "mcp_config", None),
                    no_mcp=getattr(args, "no_mcp", False),
                    trust_project_mcp=mcp_trust_decision,
                )
            )
            return_code = result.return_code
            thread_id = result.thread_id or thread_id

            # Print session stats
            from cli import _print_session_stats
            _print_session_stats(result.session_stats, console)

        except Exception as e:
            console.print(f"\n[red]Application error: {e}[/red]")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            sys.exit(1)

        # Show resume hint on exit
        if thread_id and return_code == 0 and asyncio.run(thread_exists(thread_id)):
            console.print()
            console.print("[dim]Resume this thread with:[/dim]")
            console.print(f"[cyan]ostwin chat -r {thread_id}[/cyan]")

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    chat_main()
