#!/usr/bin/env python3
"""
iTerm2 Client - Python script for reading iTerm2 pane contents.
Outputs JSON for consumption by the MCP server.

Requires:
- iTerm2 with Python API enabled (Preferences > General > Magic > Enable Python API)
- iterm2 Python package (pip install iterm2)
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys


def check_iterm2_module():
    """Check if iterm2 module is available."""
    try:
        import iterm2
        return True
    except ImportError:
        return False


def check_api_enabled():
    """Check if the Python API is enabled in iTerm2 preferences."""
    try:
        result = subprocess.run(
            ["defaults", "read", "com.googlecode.iterm2", "EnableAPIServer"],
            capture_output=True, text=True
        )
        return result.returncode == 0 and result.stdout.strip() == "1"
    except:
        return False


def enable_api():
    """Enable the Python API in iTerm2 preferences."""
    try:
        subprocess.run(
            ["defaults", "write", "com.googlecode.iterm2", "EnableAPIServer", "-bool", "true"],
            check=True, capture_output=True
        )
        return True
    except:
        return False


def get_current_session_from_env():
    """Get the current session ID from environment."""
    return os.environ.get("ITERM_SESSION_ID", "")


def output_json(data):
    """Output data as JSON."""
    print(json.dumps(data, indent=2))


def output_error(message, code="ERROR"):
    """Output an error as JSON."""
    output_json({"error": code, "message": message})
    sys.exit(1)


async def list_panes():
    """List all iTerm2 panes with their details."""
    import iterm2

    try:
        connection = await iterm2.Connection.async_create()
    except Exception as e:
        output_error(
            f"Failed to connect to iTerm2: {e}. "
            "Make sure Python API is enabled and iTerm2 was restarted.",
            "CONNECTION_FAILED"
        )

    app = await iterm2.async_get_app(connection)
    current_session_id = get_current_session_from_env()

    result = {
        "current_session_id": current_session_id,
        "windows": []
    }

    for window_idx, window in enumerate(app.windows):
        window_data = {
            "index": window_idx,
            "id": window.window_id,
            "tabs": []
        }

        for tab_idx, tab in enumerate(window.tabs):
            tab_data = {
                "index": tab_idx,
                "id": tab.tab_id,
                "sessions": []
            }

            for session_idx, session in enumerate(tab.sessions):
                session_id = session.session_id

                # Get session details
                name = await session.async_get_variable("name") or ""
                tty = await session.async_get_variable("tty") or ""
                cwd = await session.async_get_variable("path") or ""
                job_name = await session.async_get_variable("jobName") or ""

                session_data = {
                    "index": session_idx,
                    "id": session_id,
                    "name": name,
                    "tty": tty,
                    "cwd": cwd,
                    "job": job_name,
                    "is_current": session_id == current_session_id
                }

                tab_data["sessions"].append(session_data)

            window_data["tabs"].append(tab_data)

        result["windows"].append(window_data)

    output_json(result)


async def read_pane(session_id):
    """Read the contents of a specific pane."""
    import iterm2

    try:
        connection = await iterm2.Connection.async_create()
    except Exception as e:
        output_error(
            f"Failed to connect to iTerm2: {e}",
            "CONNECTION_FAILED"
        )

    app = await iterm2.async_get_app(connection)

    # Find the session
    target_session = None
    session_info = None

    for window_idx, window in enumerate(app.windows):
        for tab_idx, tab in enumerate(window.tabs):
            for session_idx, session in enumerate(tab.sessions):
                if session.session_id == session_id:
                    target_session = session
                    session_info = {
                        "window": window_idx,
                        "tab": tab_idx,
                        "pane": session_idx
                    }
                    break

    if target_session is None:
        output_error(f"Session '{session_id}' not found", "SESSION_NOT_FOUND")

    # Read screen contents
    try:
        contents = await target_session.async_get_screen_contents()
        lines = []

        for i in range(contents.number_of_lines):
            line = contents.line(i)
            lines.append(line.string.rstrip())

        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()

        name = await target_session.async_get_variable("name") or ""
        cwd = await target_session.async_get_variable("path") or ""

        output_json({
            "session_id": session_id,
            "name": name,
            "cwd": cwd,
            "location": session_info,
            "contents": "\n".join(lines)
        })

    except Exception as e:
        output_error(f"Failed to read session contents: {e}", "READ_FAILED")


async def get_current_pane():
    """Get information about the current pane."""
    import iterm2

    current_session_id = get_current_session_from_env()

    if not current_session_id:
        output_error(
            "Not running in an iTerm2 session (ITERM_SESSION_ID not set)",
            "NOT_IN_ITERM"
        )

    try:
        connection = await iterm2.Connection.async_create()
    except Exception as e:
        output_error(f"Failed to connect to iTerm2: {e}", "CONNECTION_FAILED")

    app = await iterm2.async_get_app(connection)

    for window_idx, window in enumerate(app.windows):
        for tab_idx, tab in enumerate(window.tabs):
            for session_idx, session in enumerate(tab.sessions):
                if session.session_id == current_session_id:
                    name = await session.async_get_variable("name") or ""
                    tty = await session.async_get_variable("tty") or ""
                    cwd = await session.async_get_variable("path") or ""
                    job_name = await session.async_get_variable("jobName") or ""

                    output_json({
                        "session_id": current_session_id,
                        "name": name,
                        "tty": tty,
                        "cwd": cwd,
                        "job": job_name,
                        "location": {
                            "window": window_idx,
                            "tab": tab_idx,
                            "pane": session_idx
                        }
                    })
                    return

    output_error(f"Current session '{current_session_id}' not found", "SESSION_NOT_FOUND")


def main():
    parser = argparse.ArgumentParser(description="iTerm2 client for MCP server")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Status command
    subparsers.add_parser("status", help="Check iTerm2 API status")

    # Enable command
    subparsers.add_parser("enable", help="Enable iTerm2 Python API")

    # List command
    subparsers.add_parser("list", help="List all panes")

    # Read command
    read_parser = subparsers.add_parser("read", help="Read pane contents")
    read_parser.add_argument("session_id", help="Session ID to read")

    # Current command
    subparsers.add_parser("current", help="Get current pane info")

    args = parser.parse_args()

    if args.command == "status":
        has_module = check_iterm2_module()
        api_enabled = check_api_enabled()
        current_session = get_current_session_from_env()

        output_json({
            "iterm2_module_installed": has_module,
            "api_enabled": api_enabled,
            "in_iterm_session": bool(current_session),
            "current_session_id": current_session,
            "ready": has_module and api_enabled
        })

    elif args.command == "enable":
        if check_api_enabled():
            output_json({"enabled": True, "message": "API was already enabled"})
        elif enable_api():
            output_json({
                "enabled": True,
                "message": "API enabled. Please restart iTerm2 for changes to take effect."
            })
        else:
            output_error("Failed to enable API", "ENABLE_FAILED")

    elif args.command == "list":
        if not check_iterm2_module():
            output_error(
                "iterm2 Python module not installed. Run: pip install iterm2",
                "MODULE_NOT_INSTALLED"
            )
        asyncio.run(list_panes())

    elif args.command == "read":
        if not check_iterm2_module():
            output_error(
                "iterm2 Python module not installed. Run: pip install iterm2",
                "MODULE_NOT_INSTALLED"
            )
        asyncio.run(read_pane(args.session_id))

    elif args.command == "current":
        if not check_iterm2_module():
            output_error(
                "iterm2 Python module not installed. Run: pip install iterm2",
                "MODULE_NOT_INSTALLED"
            )
        asyncio.run(get_current_pane())

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
