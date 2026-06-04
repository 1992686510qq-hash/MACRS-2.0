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
    # Whitelist of environment variables to pass to the claude CLI subprocess.
    # Only safe, necessary variables are included to minimize information leakage.
    _SAFE_ENV_KEYS = {
        # --- OS & shell essentials ---
        "PATH",               # Executable search path (required to find claude, node, etc.)
        "HOME",               # Unix-style home directory (used by Node.js, npm)
        "USERPROFILE",        # Windows-style home directory
        "APPDATA",            # Windows per-user app data (npm cache, etc.)
        "LOCALAPPDATA",       # Windows local app data
        "SYSTEMROOT",         # Windows system directory
        "WINDIR",             # Windows directory (alias of SYSTEMROOT)
        "TEMP",               # Temporary directory (Unix convention)
        "TMP",                # Temporary directory (Windows/convention)
        "COMSPEC",            # Windows command interpreter path (cmd.exe)
        # --- Locale (ensures UTF-8 output from child processes) ---
        "LANG",               # POSIX locale setting
        "LC_ALL",             # Override all locale categories
        "LC_CTYPE",           # Character classification locale
        # --- Node.js / npm ---
        "NODE_PATH",          # Additional module search paths for Node.js
        "NPM_CONFIG_PREFIX",  # Global npm install prefix
        # --- API authentication ---
        # SECURITY NOTE: These keys are passed so the claude CLI can authenticate
        # with the Anthropic API.  They are NOT logged or stored by MACRS itself.
        # Risk mitigation:
        #   1. Keys are only passed to the claude CLI subprocess, never written to disk
        #   2. Debug output files are redacted (see main.py _redact_sensitive_data)
        #   3. If a more secure credential store (e.g., OS keychain) is available,
        #      consider migrating to it in a future version.
        #   4. Users should use short-lived / scoped API keys where possible.
        "ANTHROPIC_API_KEY",  # Primary Anthropic API key
        "CLAUDE_API_KEY",     # Alternative key name used by some claude CLI versions
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
