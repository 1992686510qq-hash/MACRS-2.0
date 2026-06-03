"""MACRS Coordinator - Shared LLM Client.

Provides a single, consistent interface for calling the claude CLI.
All modules should import from here instead of wrapping subprocess directly.
"""

import os
import shutil
import signal
import subprocess
import sys
import time
from typing import Optional


def _kill_process_tree(proc):
    """杀死进程树（跨平台）"""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            check=False,
            capture_output=True,
        )
    else:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)


def call_claude(
    prompt: str,
    model: str = "sonnet",
    timeout: int = 600,
) -> Optional[str]:
    """Call claude CLI with a prompt and return raw text output.

    Args:
        prompt: The prompt text to send to claude.
        model: Model to use (sonnet, opus, etc.).
        timeout: Timeout in seconds.

    Returns:
        Raw text output from claude, or None on failure.
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        raise FileNotFoundError(
            "claude CLI not found. Install: npm install -g @anthropic-ai/claude-code"
        )

    # Only pass safe, necessary environment variables to subprocess
    _SAFE_ENV_KEYS = {
        "PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
        "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC",
        "LANG", "LC_ALL", "LC_CTYPE",
        "NODE_PATH", "NPM_CONFIG_PREFIX",
        "ANTHROPIC_API_KEY", "CLAUDE_API_KEY",
    }
    env = {k: v for k, v in os.environ.items() if k in _SAFE_ENV_KEYS}
    env["PYTHONIOENCODING"] = "utf-8"
    env["LANG"] = "en_US.UTF-8"

    try:
        proc = subprocess.Popen(
            [claude_bin, "-p", "--model", model, "--output-format", "text"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        stdout_bytes, stderr_bytes = proc.communicate(
            input=prompt.encode("utf-8"),
            timeout=timeout,
        )

        if proc.returncode != 0:
            return None

        stdout = (
            stdout_bytes.decode("utf-8", errors="replace")
            if stdout_bytes
            else ""
        )
        return stdout.strip()

    except subprocess.TimeoutExpired:
        _kill_process_tree(proc)
        return None
    except FileNotFoundError:
        raise
