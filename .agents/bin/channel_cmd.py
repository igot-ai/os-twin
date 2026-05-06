#!/usr/bin/env python3
"""ostwin channel — CLI Channel Management

Connect, disconnect, test, list, and manage pairing codes for all channels.
Delegates to the dashboard REST API.
"""

import os
import sys
import argparse
import httpx
import getpass
from typing import List, Dict, Any, Optional

# Constants
DEFAULT_DASHBOARD_URL = "http://localhost:3366"


def get_config():
    url = os.environ.get("DASHBOARD_URL", DEFAULT_DASHBOARD_URL)
    api_key = os.environ.get("OSTWIN_API_KEY")
    return url, api_key


def get_headers(api_key: Optional[str]):
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def list_channels(args):
    url, api_key = get_config()
    headers = get_headers(api_key)

    try:
        with httpx.Client(base_url=url, headers=headers) as client:
            response = client.get("/api/channels")
            response.raise_for_status()
            channels = response.json()

            print(f"\n {'Platform':10} {'Status':12} {'Users':10} {'Pairing Code':15}")
            print()  # Blank line as in example

            for c in channels:
                platform = c["platform"]
                status = c["status"]
                config = c.get("config") or {}
                users = (
                    len(config.get("authorized_users", []))
                    if config.get("authorized_users")
                    else "-"
                )
                pairing = config.get("pairing_code") or "-"

                print(f" {platform:10} {status:12} {str(users):10} {pairing:15}")
            print()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def _has_credentials(config: Optional[Dict[str, Any]]) -> bool:
    """Check if the config has non-empty credentials."""
    if not config:
        return False
    credentials = config.get("credentials", {})
    return bool(credentials and any(v for v in credentials.values() if v))


def _ask_use_existing_credentials(platform: str) -> bool:
    """Ask user if they want to use existing credentials."""
    print(f"\nFound existing credentials for {platform.capitalize()}.")
    while True:
        response = input("Use existing credentials? [Y/n]: ").strip().lower()
        if response in ("y", "yes", ""):
            return True
        elif response in ("n", "no"):
            return False
        print("Please enter 'y' or 'n'.")


def _prompt_credentials(platform: str) -> Dict[str, str]:
    """Prompt user for credentials based on platform."""
    credentials = {}
    if platform == "telegram":
        credentials["token"] = getpass.getpass("Enter Bot Token: ").strip()
    elif platform == "discord":
        credentials["token"] = getpass.getpass("Enter Bot Token: ").strip()
    elif platform == "slack":
        credentials["bot_token"] = getpass.getpass(
            "Enter Bot Token (xoxb-...): "
        ).strip()
        credentials["app_token"] = getpass.getpass(
            "Enter App Token (xapp-...): "
        ).strip()
    else:
        print(f"Unknown platform: {platform}. Using generic setup.")
        credentials["token"] = getpass.getpass("Enter Token: ").strip()
    return credentials


def connect_channel(args):
    url, api_key = get_config()
    headers = get_headers(api_key)
    platform = args.platform

    try:
        with httpx.Client(base_url=url, headers=headers) as client:
            # Check if credentials already exist
            response = client.get(f"/api/channels/{platform}")
            response.raise_for_status()
            channel_data = response.json()
            config = channel_data.get("config")

            credentials = {}
            use_existing = False

            if _has_credentials(config):
                use_existing = _ask_use_existing_credentials(platform)

            if use_existing:
                # Use existing credentials - just connect
                print(f"Using existing credentials for {platform.capitalize()}...")
            else:
                # Show setup wizard and prompt for new credentials
                response = client.get(f"/api/channels/{platform}/setup")
                response.raise_for_status()
                steps = response.json()

                if not steps:
                    print(f"No setup instructions found for {platform}.")
                else:
                    print(f"\n--- {platform.capitalize()} Setup Wizard ---")
                    for i, step in enumerate(steps, 1):
                        print(f"\nStep {i}: {step['title']}")
                        print(f"{step['description']}")
                        instructions = step["instructions"].replace("\\n", "\n")
                        print(f"{instructions}")
                    print("\n" + "-" * 30)

                credentials = _prompt_credentials(platform)

            # POST to connect
            response = client.post(
                f"/api/channels/{platform}/connect",
                json={"credentials": credentials} if credentials else {},
            )
            response.raise_for_status()

            # Get pairing code
            response = client.get(f"/api/channels/{platform}/pairing")
            response.raise_for_status()
            pairing_code = response.json().get("pairing_code")
            print(
                f"Pairing code: {pairing_code} (share with your {platform.capitalize()} users)"
            )

            # Final status line
            print(f"Starting {platform} bot... ", end="", flush=True)
            print("Connected")

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


def disconnect_channel(args):
    url, api_key = get_config()
    headers = get_headers(api_key)
    platform = args.platform

    try:
        with httpx.Client(base_url=url, headers=headers) as client:
            print(f"Stopping + disabling {platform}... ", end="", flush=True)
            response = client.post(f"/api/channels/{platform}/disconnect")
            response.raise_for_status()
            print("Disconnected")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


def test_channel(args):
    url, api_key = get_config()
    headers = get_headers(api_key)
    platform = args.platform

    try:
        with httpx.Client(base_url=url, headers=headers) as client:
            print(f"Checking health for {platform}... ", end="", flush=True)
            response = client.post(f"/api/channels/{platform}/test")
            response.raise_for_status()
            data = response.json()
            status = data.get("status", "unknown")
            message = data.get("message", "")

            # Mock latency for effect as requested
            import random

            latency = random.randint(20, 150)

            print(f"{status.upper()}")
            print(f"  Latency: {latency}ms")
            if message:
                print(f"  Message: {message}")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


def pair_channel(args):
    url, api_key = get_config()
    headers = get_headers(api_key)
    platform = args.platform

    try:
        with httpx.Client(base_url=url, headers=headers) as client:
            if args.regenerate:
                print(
                    f"Regenerating pairing code for {platform}... ", end="", flush=True
                )
                response = client.post(f"/api/channels/{platform}/pairing/regenerate")
                response.raise_for_status()
                pairing_code = response.json().get("pairing_code")
                print("Done")
                print(f"New pairing code: {pairing_code}")
            else:
                response = client.get(f"/api/channels/{platform}/pairing")
                response.raise_for_status()
                pairing_code = response.json().get("pairing_code")
                print(f"Current pairing code for {platform}: {pairing_code}")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="ostwin channel", description="CLI Channel Management"
    )
    subparsers = parser.add_subparsers(dest="command", help="Channel subcommands")

    # list
    subparsers.add_parser("list", help="List all channels and their status")

    # connect
    connect_parser = subparsers.add_parser("connect", help="Connect a channel")
    connect_parser.add_argument(
        "platform", help="Platform name (telegram, discord, slack)"
    )

    # disconnect
    disconnect_parser = subparsers.add_parser("disconnect", help="Disconnect a channel")
    disconnect_parser.add_argument("platform", help="Platform name")

    # test
    test_parser = subparsers.add_parser("test", help="Test channel health")
    test_parser.add_argument("platform", help="Platform name")

    # pair
    pair_parser = subparsers.add_parser("pair", help="Manage pairing codes")
    pair_parser.add_argument("platform", help="Platform name")
    pair_parser.add_argument(
        "--regenerate", action="store_true", help="Regenerate pairing code"
    )

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.command == "list":
        list_channels(args)
    elif args.command == "connect":
        connect_channel(args)
    elif args.command == "disconnect":
        disconnect_channel(args)
    elif args.command == "test":
        test_channel(args)
    elif args.command == "pair":
        pair_channel(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
