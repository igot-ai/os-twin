#!/usr/bin/env python3
"""
ostwin connectors — Manage chat platform connectors (Telegram, Discord, Slack).

Works directly with ~/.ostwin/chat_adapters.json config file.
No dashboard required except for the `test` subcommand.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".ostwin" / "chat_adapters.json"
PLATFORMS = ["telegram", "discord", "slack"]

PLATFORM_FLAGS = {
    "telegram": {
        "--bot-token": "bot_token",
        "--chat-id": "chat_id",
        "--bot-username": "bot_username",
        "--secret-token": "secret_token",
    },
    "discord": {
        "--webhook-url": "webhook_url",
        "--public-key": "public_key",
    },
    "slack": {
        "--bot-token": "bot_token",
        "--channel-id": "channel_id",
        "--signing-secret": "signing_secret",
        "--webhook-url": "webhook_url",
    },
}

VALIDATION_RULES = {
    "telegram": lambda c: bool(c.get("bot_token") and c.get("chat_id")),
    "discord": lambda c: bool(c.get("webhook_url")),
    "slack": lambda c: bool(c.get("webhook_url") or (c.get("bot_token") and c.get("channel_id"))),
}

REQUIRED_FIELDS = {
    "telegram": "bot_token, chat_id",
    "discord": "webhook_url",
    "slack": "webhook_url OR (bot_token + channel_id)",
}

DEFAULT_EVENTS = ["room_status_change", "error", "escalation", "alert", "done"]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")


def get_settings(config: dict) -> dict:
    return config.get("_settings", {
        "important_events": list(DEFAULT_EVENTS),
        "enabled_platforms": list(PLATFORMS),
    })


def is_configured(config: dict, platform: str) -> bool:
    return VALIDATION_RULES[platform](config.get(platform, {}))


def is_enabled(config: dict, platform: str) -> bool:
    return platform in get_settings(config).get("enabled_platforms", [])


def _toggle_platform(platform: str, enable: bool):
    config = load_config()
    settings = get_settings(config)
    enabled = settings.get("enabled_platforms", [])
    if enable and platform not in enabled:
        enabled.append(platform)
    elif not enable and platform in enabled:
        enabled.remove(platform)
    settings["enabled_platforms"] = enabled
    config["_settings"] = settings
    save_config(config)
    action = "enabled" if enable else "disabled"
    print(f"✓ {platform.capitalize()} notifications {action}")


def cmd_list(_args):
    config = load_config()
    print(f"{'Platform':<12}{'Status':<20}{'Enabled'}")
    print("─" * 40)
    for p in PLATFORMS:
        configured = is_configured(config, p)
        enabled = is_enabled(config, p)
        status = "Connected" if configured else "Not Configured"
        if configured and enabled:
            enabled_str = "✓"
        elif configured:
            enabled_str = "✗ (disabled)"
        else:
            enabled_str = "-"
        print(f"{p.capitalize():<12}{status:<20}{enabled_str}")


def cmd_configure(args):
    config = load_config()
    platform_config = config.get(args.platform, {})

    flags = PLATFORM_FLAGS[args.platform]
    updated = False
    for flag, key in flags.items():
        val = getattr(args, key, None)
        if val is not None:
            platform_config[key] = val
            updated = True

    if not updated:
        print(f"No configuration values provided for {args.platform}.", file=sys.stderr)
        print(f"Available flags: {', '.join(flags.keys())}", file=sys.stderr)
        sys.exit(1)

    config[args.platform] = platform_config
    save_config(config)
    print(f"✓ {args.platform.capitalize()} configuration updated")

    if is_configured(config, args.platform):
        print("  Status: Connected")
    else:
        print(f"  Status: Incomplete — requires {REQUIRED_FIELDS[args.platform]}")


def cmd_test(args):
    config = load_config()
    if not is_configured(config, args.platform):
        print(f"✗ {args.platform.capitalize()} is not configured. "
              f"Run: ostwin connectors configure {args.platform} ...", file=sys.stderr)
        sys.exit(1)

    dashboard_url = os.environ.get("DASHBOARD_URL", "http://localhost:9000")
    url = f"{dashboard_url}/api/chat-adapters/{args.platform}/test"
    curl_cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", "POST", url]

    api_key = os.environ.get("OSTWIN_API_KEY")
    if api_key:
        curl_cmd += ["-H", f"X-API-Key: {api_key}"]

    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        print("✗ curl not found", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("✗ Request timed out — is the dashboard running?", file=sys.stderr)
        sys.exit(1)

    output = result.stdout.strip()
    lines = output.rsplit("\n", 1)
    body = lines[0] if len(lines) > 1 else ""
    status_code = lines[-1] if lines else ""

    try:
        code = int(status_code)
    except ValueError:
        print(f"✗ Could not reach dashboard at {dashboard_url}", file=sys.stderr)
        sys.exit(1)

    if 200 <= code < 300:
        print(f"✓ Test message sent via {args.platform.capitalize()}")
    else:
        print(f"✗ Test failed (HTTP {code})", file=sys.stderr)
        if body:
            try:
                detail = json.loads(body).get("detail", body)
            except json.JSONDecodeError:
                detail = body
            print(f"  {detail}", file=sys.stderr)
        sys.exit(1)


def cmd_enable(args):
    _toggle_platform(args.platform, enable=True)


def cmd_disable(args):
    _toggle_platform(args.platform, enable=False)


def cmd_events(args):
    config = load_config()
    settings = get_settings(config)

    if args.set_events:
        events = [e.strip() for e in args.set_events.split(",") if e.strip()]
        settings["important_events"] = events
        config["_settings"] = settings
        save_config(config)
        print(f"✓ Notification events updated: {', '.join(events)}")
    else:
        events = settings.get("important_events", DEFAULT_EVENTS)
        print("Notification events:")
        for e in events:
            print(f"  • {e}")


def cmd_remove(args):
    config = load_config()
    if args.platform in config:
        del config[args.platform]
        save_config(config)
        print(f"✓ {args.platform.capitalize()} configuration removed")
    else:
        print(f"{args.platform.capitalize()} has no configuration to remove")


def _add_platform_subparser(sub, name, help_text):
    p = sub.add_parser(name, help=help_text)
    p.add_argument("platform", choices=PLATFORMS)
    return p


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ostwin connectors",
        description="Manage chat platform connectors",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all platforms and status")

    configure_p = sub.add_parser("configure", help="Configure a platform")
    configure_p.add_argument("platform", choices=PLATFORMS)
    seen = set()
    for flags in PLATFORM_FLAGS.values():
        for flag, key in flags.items():
            if key not in seen:
                configure_p.add_argument(flag, dest=key, default=None)
                seen.add(key)

    _add_platform_subparser(sub, "test", "Send test message via platform")
    _add_platform_subparser(sub, "enable", "Enable notifications for platform")
    _add_platform_subparser(sub, "disable", "Disable notifications for platform")
    _add_platform_subparser(sub, "remove", "Remove platform configuration")

    events_p = sub.add_parser("events", help="Show or set notification events")
    events_p.add_argument("set_action", nargs="?", choices=["set"], default=None)
    events_p.add_argument("set_events", nargs="?", default=None)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "list": cmd_list,
        "configure": cmd_configure,
        "test": cmd_test,
        "enable": cmd_enable,
        "disable": cmd_disable,
        "events": cmd_events,
        "remove": cmd_remove,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
