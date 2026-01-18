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


def parse_shorthand_id(shorthand):
    """
    Parse a shorthand session ID like 't4p2' or 'w1t4p2' into indices.
    Uses 1-based indexing to match iTerm2's UI.
    Returns (window_idx, tab_idx, pane_idx) as 0-based indices for internal use,
    or None if the format is invalid.
    """
    import re

    # Match patterns like "t4p2" or "w1t4p2"
    match = re.match(r'^(?:w(\d+))?t(\d+)p(\d+)$', shorthand.lower())
    if not match:
        return None

    window = int(match.group(1)) if match.group(1) else 1  # Default to window 1
    tab = int(match.group(2))
    pane = int(match.group(3))

    # Convert from 1-based (user) to 0-based (internal)
    return (window - 1, tab - 1, pane - 1)


async def resolve_session_id(app, session_id_or_shorthand):
    """
    Resolve a session ID from either a full UUID or shorthand format.
    Returns (session, shorthand_str) or exits with error.
    """
    # Check if it's a shorthand format
    indices = parse_shorthand_id(session_id_or_shorthand)

    if indices:
        window_idx, tab_idx, pane_idx = indices

        if window_idx < 0 or window_idx >= len(app.windows):
            output_error(
                f"Window {window_idx + 1} not found (have {len(app.windows)} windows)",
                "SESSION_NOT_FOUND"
            )

        window = app.windows[window_idx]
        if tab_idx < 0 or tab_idx >= len(window.tabs):
            output_error(
                f"Tab {tab_idx + 1} not found in window {window_idx + 1} (have {len(window.tabs)} tabs)",
                "SESSION_NOT_FOUND"
            )

        tab = window.tabs[tab_idx]
        if pane_idx < 0 or pane_idx >= len(tab.sessions):
            output_error(
                f"Pane {pane_idx + 1} not found in tab {tab_idx + 1} (have {len(tab.sessions)} panes)",
                "SESSION_NOT_FOUND"
            )

        session = tab.sessions[pane_idx]
        shorthand = f"w{window_idx + 1}t{tab_idx + 1}p{pane_idx + 1}"
        return session, shorthand

    # Otherwise, search for the full session ID
    for window_idx, window in enumerate(app.windows):
        for tab_idx, tab in enumerate(window.tabs):
            for pane_idx, session in enumerate(tab.sessions):
                if session.session_id == session_id_or_shorthand:
                    shorthand = f"w{window_idx + 1}t{tab_idx + 1}p{pane_idx + 1}"
                    return session, shorthand

    output_error(f"Session '{session_id_or_shorthand}' not found", "SESSION_NOT_FOUND")


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

    # Find current session shorthand
    current_shorthand = None
    for window_idx, window in enumerate(app.windows):
        for tab_idx, tab in enumerate(window.tabs):
            for pane_idx, session in enumerate(tab.sessions):
                if session.session_id == current_session_id:
                    current_shorthand = f"w{window_idx + 1}t{tab_idx + 1}p{pane_idx + 1}"
                    break

    result = {
        "current_session_id": current_session_id,
        "current_shorthand": current_shorthand,
        "windows": []
    }

    for window_idx, window in enumerate(app.windows):
        window_data = {
            "index": window_idx + 1,  # 1-based
            "id": window.window_id,
            "tabs": []
        }

        for tab_idx, tab in enumerate(window.tabs):
            tab_data = {
                "index": tab_idx + 1,  # 1-based
                "id": tab.tab_id,
                "sessions": []
            }

            for session_idx, session in enumerate(tab.sessions):
                session_id = session.session_id
                shorthand = f"w{window_idx + 1}t{tab_idx + 1}p{session_idx + 1}"

                # Get session details
                name = await session.async_get_variable("name") or ""
                tty = await session.async_get_variable("tty") or ""
                cwd = await session.async_get_variable("path") or ""
                job_name = await session.async_get_variable("jobName") or ""

                session_data = {
                    "index": session_idx + 1,  # 1-based
                    "id": session_id,
                    "shorthand": shorthand,
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


async def read_pane(session_id_or_shorthand):
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

    # Resolve the session (supports both shorthand and full UUID)
    target_session, shorthand = await resolve_session_id(app, session_id_or_shorthand)

    # Read screen contents
    try:
        contents = await target_session.async_get_screen_contents()
        lines = []

        for i in range(contents.number_of_lines):
            line = contents.line(i)
            lines.append(line.string.replace('\x00', '').rstrip())

        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()

        name = await target_session.async_get_variable("name") or ""
        cwd = await target_session.async_get_variable("path") or ""

        output_json({
            "session_id": target_session.session_id,
            "shorthand": shorthand,
            "name": name,
            "cwd": cwd,
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
                    shorthand = f"w{window_idx + 1}t{tab_idx + 1}p{session_idx + 1}"

                    output_json({
                        "session_id": current_session_id,
                        "shorthand": shorthand,
                        "name": name,
                        "tty": tty,
                        "cwd": cwd,
                        "job": job_name,
                        "location": {
                            "window": window_idx + 1,  # 1-based
                            "tab": tab_idx + 1,        # 1-based
                            "pane": session_idx + 1    # 1-based
                        }
                    })
                    return

    output_error(f"Current session '{current_session_id}' not found", "SESSION_NOT_FOUND")


async def find_session(session_id_or_shorthand):
    """Find a session by ID or shorthand. Returns (connection, session, shorthand) or exits with error."""
    import iterm2

    try:
        connection = await iterm2.Connection.async_create()
    except Exception as e:
        output_error(f"Failed to connect to iTerm2: {e}", "CONNECTION_FAILED")

    app = await iterm2.async_get_app(connection)
    session, shorthand = await resolve_session_id(app, session_id_or_shorthand)

    return connection, session, shorthand


async def send_text(session_id, text, newline=True):
    """Send text to a specific pane."""
    connection, session, shorthand = await find_session(session_id)

    try:
        text_to_send = text + "\n" if newline else text
        await session.async_send_text(text_to_send)

        output_json({
            "success": True,
            "session_id": session.session_id,
            "shorthand": shorthand,
            "text_sent": text,
            "newline": newline
        })
    except Exception as e:
        output_error(f"Failed to send text: {e}", "SEND_FAILED")


async def send_control(session_id, control):
    """Send a control character to a specific pane."""
    # Control character mapping
    control_chars = {
        "c": "\u0003",  # Ctrl+C - Interrupt/SIGINT
        "d": "\u0004",  # Ctrl+D - EOF/logout
        "z": "\u001a",  # Ctrl+Z - Suspend/SIGTSTP
        "l": "\u000c",  # Ctrl+L - Clear screen
    }

    if control not in control_chars:
        output_error(
            f"Unknown control character: {control}. Valid options: c, d, z, l",
            "INVALID_CONTROL"
        )

    connection, session, shorthand = await find_session(session_id)

    try:
        await session.async_send_text(control_chars[control])

        output_json({
            "success": True,
            "session_id": session.session_id,
            "shorthand": shorthand,
            "control": control,
            "description": {
                "c": "Ctrl+C (SIGINT)",
                "d": "Ctrl+D (EOF)",
                "z": "Ctrl+Z (SIGTSTP)",
                "l": "Ctrl+L (Clear)"
            }[control]
        })
    except Exception as e:
        output_error(f"Failed to send control character: {e}", "SEND_FAILED")


async def split_pane(session_id, vertical=False):
    """Split a pane horizontally or vertically."""
    connection, session, shorthand = await find_session(session_id)

    try:
        new_session = await session.async_split_pane(vertical=vertical)

        # Note: We can't easily get the new pane's shorthand without re-listing
        # The new pane will be adjacent to the original
        output_json({
            "success": True,
            "original_session_id": session.session_id,
            "original_shorthand": shorthand,
            "new_session_id": new_session.session_id,
            "split_direction": "vertical" if vertical else "horizontal"
        })
    except Exception as e:
        output_error(f"Failed to split pane: {e}", "SPLIT_FAILED")


async def get_side_pane():
    """Get a side pane in the same tab as the current pane.

    Prefers the pane to the right, but falls back to left if current is rightmost.
    """
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

    # Find current session and its location
    for window_idx, window in enumerate(app.windows):
        for tab_idx, tab in enumerate(window.tabs):
            for session_idx, session in enumerate(tab.sessions):
                if session.session_id == current_session_id:
                    # Found current session, now find a side pane
                    num_panes = len(tab.sessions)

                    if num_panes == 1:
                        output_error(
                            "No side pane found - this is the only pane in the tab",
                            "NO_SIDE_PANE"
                        )

                    # Prefer pane to the right (higher index)
                    if session_idx + 1 < num_panes:
                        side_idx = session_idx + 1
                    else:
                        # Fall back to pane on the left (lower index)
                        side_idx = session_idx - 1

                    side_session = tab.sessions[side_idx]
                    side_shorthand = f"w{window_idx + 1}t{tab_idx + 1}p{side_idx + 1}"
                    current_shorthand = f"w{window_idx + 1}t{tab_idx + 1}p{session_idx + 1}"

                    # Get side pane details
                    name = await side_session.async_get_variable("name") or ""
                    cwd = await side_session.async_get_variable("path") or ""
                    job_name = await side_session.async_get_variable("jobName") or ""

                    output_json({
                        "session_id": side_session.session_id,
                        "shorthand": side_shorthand,
                        "name": name,
                        "cwd": cwd,
                        "job": job_name,
                        "position": "right" if side_idx > session_idx else "left",
                        "current_shorthand": current_shorthand,
                        "location": {
                            "window": window_idx + 1,
                            "tab": tab_idx + 1,
                            "pane": side_idx + 1
                        }
                    })
                    return

    output_error(f"Current session '{current_session_id}' not found", "SESSION_NOT_FOUND")


def main():
    parser = argparse.ArgumentParser(description="iTerm2 client for MCP server")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Side-pane command (most commonly used)
    subparsers.add_parser("side-pane", help="Get the side pane in the current tab")

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

    # Send-text command
    send_text_parser = subparsers.add_parser("send-text", help="Send text to a pane")
    send_text_parser.add_argument("session_id", help="Session ID to send text to")
    send_text_parser.add_argument("text", help="Text to send")
    send_text_parser.add_argument(
        "--no-newline", action="store_true",
        help="Don't append newline (don't press Enter)"
    )

    # Send-control command
    send_control_parser = subparsers.add_parser("send-control", help="Send control character to a pane")
    send_control_parser.add_argument("session_id", help="Session ID to send control to")
    send_control_parser.add_argument(
        "control", choices=["c", "d", "z", "l"],
        help="Control character: c=Ctrl+C, d=Ctrl+D, z=Ctrl+Z, l=Ctrl+L"
    )

    # Split command
    split_parser = subparsers.add_parser("split", help="Split a pane")
    split_parser.add_argument("session_id", help="Session ID to split")
    split_parser.add_argument(
        "--vertical", action="store_true",
        help="Split vertically (default is horizontal)"
    )

    args = parser.parse_args()

    if args.command == "side-pane":
        if not check_iterm2_module():
            output_error(
                "iterm2 Python module not installed. Run: pip install iterm2",
                "MODULE_NOT_INSTALLED"
            )
        asyncio.run(get_side_pane())

    elif args.command == "status":
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

    elif args.command == "send-text":
        if not check_iterm2_module():
            output_error(
                "iterm2 Python module not installed. Run: pip install iterm2",
                "MODULE_NOT_INSTALLED"
            )
        asyncio.run(send_text(args.session_id, args.text, newline=not args.no_newline))

    elif args.command == "send-control":
        if not check_iterm2_module():
            output_error(
                "iterm2 Python module not installed. Run: pip install iterm2",
                "MODULE_NOT_INSTALLED"
            )
        asyncio.run(send_control(args.session_id, args.control))

    elif args.command == "split":
        if not check_iterm2_module():
            output_error(
                "iterm2 Python module not installed. Run: pip install iterm2",
                "MODULE_NOT_INSTALLED"
            )
        asyncio.run(split_pane(args.session_id, vertical=args.vertical))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
