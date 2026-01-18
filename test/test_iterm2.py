#!/usr/bin/env python3
"""
Integration tests for iTerm2 MCP Server.

These tests must be run inside an iTerm2 terminal with:
- Python API enabled in iTerm2 preferences
- iterm2 Python module installed (pip install iterm2)
- At least one side pane in the current tab (for side-pane test)

Usage:
    python3 test/test_iterm2.py

Or via npm:
    npm test
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

# Path to the Python client
SCRIPT_DIR = Path(__file__).parent.parent
PYTHON_CLIENT = SCRIPT_DIR / "python" / "iterm2_client.py"

passed = 0
failed = 0
skipped = 0


def run_command(args):
    """Run the Python client with given args and return parsed JSON."""
    result = subprocess.run(
        ["python3", str(PYTHON_CLIENT)] + args,
        capture_output=True,
        text=True
    )

    if result.stdout:
        try:
            return json.loads(result.stdout), result.returncode
        except json.JSONDecodeError:
            return {"raw_output": result.stdout}, result.returncode

    return {"error": "NO_OUTPUT", "stderr": result.stderr}, result.returncode


def test(name, condition, message=""):
    """Record a test result."""
    global passed, failed
    if condition:
        print(f"  {GREEN}✓{RESET} {name}")
        passed += 1
        return True
    else:
        print(f"  {RED}✗{RESET} {name}")
        if message:
            print(f"    {RED}{message}{RESET}")
        failed += 1
        return False


def skip(name, reason):
    """Skip a test."""
    global skipped
    print(f"  {YELLOW}○{RESET} {name} (skipped: {reason})")
    skipped += 1


def test_status():
    """Test the status command."""
    print("\n📋 Testing: status")

    result, code = run_command(["status"])

    test("returns valid JSON", "error" not in result or result.get("error") != "NO_OUTPUT")
    test("has iterm2_module_installed field", "iterm2_module_installed" in result)
    test("has api_enabled field", "api_enabled" in result)
    test("has in_iterm_session field", "in_iterm_session" in result)
    test("has ready field", "ready" in result)

    if result.get("iterm2_module_installed"):
        test("iterm2 module is installed", True)
    else:
        test("iterm2 module is installed", False, "Run: pip install iterm2")

    if result.get("api_enabled"):
        test("API is enabled", True)
    else:
        test("API is enabled", False, "Enable in iTerm2 Preferences > General > Magic")

    return result.get("ready", False)


def test_list_panes():
    """Test the list command."""
    print("\n📋 Testing: list")

    result, code = run_command(["list"])

    if result.get("error"):
        test("list command succeeds", False, result.get("message", "Unknown error"))
        return None

    test("list command succeeds", code == 0)
    test("has windows array", "windows" in result and isinstance(result["windows"], list))
    test("has at least one window", len(result.get("windows", [])) > 0)

    if result.get("windows"):
        window = result["windows"][0]
        test("window has tabs", "tabs" in window and len(window["tabs"]) > 0)

        if window.get("tabs"):
            tab = window["tabs"][0]
            test("tab has sessions", "sessions" in tab and len(tab["sessions"]) > 0)

            if tab.get("sessions"):
                session = tab["sessions"][0]
                test("session has shorthand", "shorthand" in session)
                test("session has id", "id" in session)
                test("shorthand format is correct",
                     session.get("shorthand", "").startswith("w") and "t" in session.get("shorthand", "") and "p" in session.get("shorthand", ""))

    test("has current_shorthand", "current_shorthand" in result)

    return result


def test_current_pane():
    """Test the current command."""
    print("\n📋 Testing: current")

    result, code = run_command(["current"])

    if result.get("error"):
        if result.get("error") == "NOT_IN_ITERM":
            skip("current pane detection", "not running in iTerm2")
            return None
        test("current command succeeds", False, result.get("message", "Unknown error"))
        return None

    test("current command succeeds", code == 0)
    test("has session_id", "session_id" in result)
    test("has shorthand", "shorthand" in result)
    test("has location", "location" in result)

    if result.get("location"):
        loc = result["location"]
        test("location has window", "window" in loc)
        test("location has tab", "tab" in loc)
        test("location has pane", "pane" in loc)

    return result


def test_side_pane():
    """Test the side-pane command."""
    print("\n📋 Testing: side-pane")

    result, code = run_command(["side-pane"])

    if result.get("error"):
        if result.get("error") == "NO_SIDE_PANE":
            skip("side pane detection", "no side pane in current tab - split your pane first")
            return None
        if result.get("error") == "NOT_IN_ITERM":
            skip("side pane detection", "not running in iTerm2")
            return None
        test("side-pane command succeeds", False, result.get("message", "Unknown error"))
        return None

    test("side-pane command succeeds", code == 0)
    test("has session_id", "session_id" in result)
    test("has shorthand", "shorthand" in result)
    test("has position (left/right)", result.get("position") in ["left", "right"])
    test("has current_shorthand", "current_shorthand" in result)
    test("has location", "location" in result)

    return result


def test_read_pane(shorthand):
    """Test the read command."""
    print("\n📋 Testing: read")

    if not shorthand:
        skip("read pane", "no shorthand available")
        return

    result, code = run_command(["read", shorthand])

    if result.get("error"):
        test("read command succeeds", False, result.get("message", "Unknown error"))
        return

    test("read command succeeds", code == 0)
    test("has session_id", "session_id" in result)
    test("has shorthand", "shorthand" in result)
    test("has contents", "contents" in result)
    test("contents is string", isinstance(result.get("contents"), str))


def test_send_text(shorthand):
    """Test the send-text command (without newline to avoid executing)."""
    print("\n📋 Testing: send-text")

    if not shorthand:
        skip("send text", "no shorthand available")
        return

    # Send text without newline so we don't execute anything
    test_text = "# test message - delete me"
    result, code = run_command(["send-text", shorthand, test_text, "--no-newline"])

    if result.get("error"):
        test("send-text command succeeds", False, result.get("message", "Unknown error"))
        return

    test("send-text command succeeds", code == 0)
    test("has success field", result.get("success") == True)
    test("has text_sent field", "text_sent" in result)
    test("newline is false", result.get("newline") == False)

    # Clean up by sending Ctrl+U to clear the line
    run_command(["send-control", shorthand, "c"])
    print(f"    {YELLOW}Note: Sent Ctrl+C to clean up test text{RESET}")


def test_send_control(shorthand):
    """Test the send-control command."""
    print("\n📋 Testing: send-control")

    if not shorthand:
        skip("send control", "no shorthand available")
        return

    # Test sending Ctrl+L (clear screen) - harmless
    result, code = run_command(["send-control", shorthand, "l"])

    if result.get("error"):
        test("send-control command succeeds", False, result.get("message", "Unknown error"))
        return

    test("send-control command succeeds", code == 0)
    test("has success field", result.get("success") == True)
    test("has control field", "control" in result)
    test("has description field", "description" in result)


def test_split_pane(shorthand):
    """Test the split command - SKIPPED by default as it changes UI."""
    print("\n📋 Testing: split")
    skip("split pane", "skipped to avoid changing terminal layout")
    # Uncomment below to actually test:
    # result, code = run_command(["split", shorthand])
    # test("split command succeeds", code == 0)


def main():
    """Run all tests."""
    print("=" * 60)
    print("iTerm2 MCP Server - Integration Tests")
    print("=" * 60)

    # Check environment
    iterm_session = os.environ.get("ITERM_SESSION_ID")
    if not iterm_session:
        print(f"\n{YELLOW}Warning: ITERM_SESSION_ID not set - some tests may be skipped{RESET}")

    # Run tests
    ready = test_status()

    if not ready:
        print(f"\n{RED}iTerm2 API not ready. Please ensure:{RESET}")
        print("  1. You're running inside iTerm2")
        print("  2. Python API is enabled (Preferences > General > Magic)")
        print("  3. iterm2 module is installed (pip install iterm2)")
        print("  4. iTerm2 was restarted after enabling the API")
        sys.exit(1)

    list_result = test_list_panes()
    current_result = test_current_pane()
    side_result = test_side_pane()

    # Get a shorthand for testing read/send
    test_shorthand = None
    if side_result and side_result.get("shorthand"):
        test_shorthand = side_result["shorthand"]
    elif list_result and list_result.get("windows"):
        # Use the first available pane
        try:
            test_shorthand = list_result["windows"][0]["tabs"][0]["sessions"][0]["shorthand"]
        except (KeyError, IndexError):
            pass

    test_read_pane(test_shorthand)
    test_send_text(test_shorthand)
    test_send_control(test_shorthand)
    test_split_pane(test_shorthand)

    # Summary
    print("\n" + "=" * 60)
    total = passed + failed + skipped
    print(f"Results: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}, {YELLOW}{skipped} skipped{RESET} ({total} total)")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
