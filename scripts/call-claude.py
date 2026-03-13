#!/usr/bin/env python3
"""Thin wrapper around `claude -p` for use as an LLM provider.

Reads a prompt from a file, calls `claude -p`, writes the response to a file.

Usage:
  python3 scripts/call-claude.py --prompt-file /tmp/prompt.txt \
      --response-file /tmp/response.txt [--system-prompt-file /tmp/sys.txt] \
      [--model sonnet] [--timeout 120]
"""

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path


def _kill(proc, grace=5):
    """Terminate process group gracefully, then force-kill."""
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        proc.wait(timeout=grace)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait(timeout=3)
        except (ProcessLookupError, OSError):
            pass


def main():
    parser = argparse.ArgumentParser(description="Call claude -p with file-based I/O")
    parser.add_argument("--prompt-file", required=True, help="Path to file containing the prompt")
    parser.add_argument("--response-file", required=True, help="Path to write the response")
    parser.add_argument("--system-prompt-file", help="Path to file containing the system prompt")
    parser.add_argument("--model", default="sonnet", help="Model to use (default: sonnet)")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds")
    args = parser.parse_args()

    prompt = Path(args.prompt_file).read_text()

    cmd = [
        "claude",
        "-p", prompt,
        "--model", args.model,
        "--output-format", "text",
        "--no-session-persistence",
        "--dangerously-skip-permissions",
        "--allowedTools", "",
    ]

    if args.system_prompt_file:
        system_prompt = Path(args.system_prompt_file).read_text()
        cmd.extend(["--system-prompt", system_prompt])

    # Clean env: remove nesting guards
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}

    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        stdout_bytes, stderr_bytes = proc.communicate(timeout=args.timeout)
        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        if proc.returncode != 0:
            error_info = json.dumps({
                "error": "claude_cli_failed",
                "returncode": proc.returncode,
                "stderr": stderr[:2000],
                "stdout": stdout[:500],
            })
            Path(args.response_file).write_text(error_info)
            sys.exit(1)

        Path(args.response_file).write_text(stdout)

    except subprocess.TimeoutExpired:
        _kill(proc)
        error_info = json.dumps({
            "error": "timeout",
            "message": f"claude -p timed out after {args.timeout}s",
        })
        Path(args.response_file).write_text(error_info)
        sys.exit(2)

    except FileNotFoundError:
        error_info = json.dumps({
            "error": "claude_not_found",
            "message": "claude CLI not found in PATH",
        })
        Path(args.response_file).write_text(error_info)
        sys.exit(3)


if __name__ == "__main__":
    main()
