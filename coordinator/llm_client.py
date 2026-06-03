"""MACRS Coordinator - Shared LLM Client.

Provides a single, consistent interface for calling the claude CLI.
All modules should import from here instead of wrapping subprocess directly.
"""

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional


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

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["LANG"] = "en_US.UTF-8"

    # Write prompt to temp file to avoid shell escaping / stdin pipe issues
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(prompt)
            tmp_path = tmp.name

        with open(tmp_path, "r", encoding="utf-8") as f:
            prompt_content = f.read()

        proc = subprocess.Popen(
            [claude_bin, "-p", "--model", model, "--output-format", "text"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        stdout_bytes, stderr_bytes = proc.communicate(
            input=prompt_content.encode("utf-8"),
            timeout=timeout,
        )

        if proc.returncode != 0:
            stderr = (
                stderr_bytes.decode("utf-8", errors="replace")
                if stderr_bytes
                else ""
            )
            return None

        stdout = (
            stdout_bytes.decode("utf-8", errors="replace")
            if stdout_bytes
            else ""
        )
        return stdout.strip()

    except subprocess.TimeoutExpired:
        proc.kill()
        return None
    except FileNotFoundError:
        raise
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
