"""MACRS Coordinator - Agent Runner.

Dispatches 3 review agents in parallel using claude CLI subprocess.
Each agent runs independently with its own prompt.
"""

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import AGENT_TIMEOUT_SECONDS, AGENTS


def _run_single_agent(agent_id: str, prompt: str, output_dir: Path) -> dict:
    """Run a single agent via claude CLI and return its result."""
    agent_name = AGENTS[agent_id]["name"]
    output_file = output_dir / f"review-{agent_id.lower()}.json"
    prompt_file = output_dir / f"prompt-{agent_id.lower()}.md"

    # Write prompt to file for debugging/retry
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"[AgentRunner] Starting {agent_name}...")
    print(f"  Prompt: {prompt_file}")
    print(f"  Output: {output_file}")

    start_time = time.time()

    try:
        # Use claude CLI in print mode (non-interactive)
        # -p/--print: non-interactive mode, prompt via stdin
        # Use shell=True on Windows to find claude in PATH
        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["LANG"] = "en_US.UTF-8"

        cmd = f'cat "{prompt_file}" | claude -p --model sonnet --output-format text'
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=AGENT_TIMEOUT_SECONDS,
            shell=True,
            env=env,
        )
        # Decode stdout/stderr manually with utf-8
        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

        elapsed = time.time() - start_time
        stdout = stdout.strip()
        stderr = stderr.strip()

        if result.returncode != 0:
            return {
                "agent_id": agent_id,
                "status": "FAILED",
                "error": f"Exit code {result.returncode}: {stderr}",
                "elapsed_seconds": round(elapsed, 1),
            }

        # Try to extract JSON from stdout
        parsed = _extract_json(stdout)
        if parsed is None:
            return {
                "agent_id": agent_id,
                "status": "FAILED",
                "error": "Could not extract valid JSON from agent output",
                "raw_output": stdout[:2000],
                "elapsed_seconds": round(elapsed, 1),
            }

        # Save result
        output_file.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "agent_id": agent_id,
            "status": "OK",
            "data": parsed,
            "elapsed_seconds": round(elapsed, 1),
            "output_file": str(output_file),
        }

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return {
            "agent_id": agent_id,
            "status": "TIMEOUT",
            "error": f"Agent timed out after {AGENT_TIMEOUT_SECONDS}s",
            "elapsed_seconds": round(elapsed, 1),
        }
    except FileNotFoundError:
        return {
            "agent_id": agent_id,
            "status": "FAILED",
            "error": "claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code",
        }
    except Exception as e:
        return {
            "agent_id": agent_id,
            "status": "FAILED",
            "error": str(e),
        }


def _extract_json(text: str) -> dict | None:
    """Try to extract a JSON object from agent output text."""
    import re

    if not text or len(text.strip()) < 10:
        print(f"[AgentRunner] Output too short ({len(text)} chars)")
        return None

    # Strategy 1: try parsing the whole text as JSON
    try:
        result = json.loads(text)
        if isinstance(result, dict) and len(result) > 0:
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: find JSON block in markdown code fence
    json_blocks = re.findall(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    for block in json_blocks:
        try:
            result = json.loads(block)
            if isinstance(result, dict) and len(result) > 0:
                return result
        except json.JSONDecodeError:
            continue

    # Strategy 3: find the first { ... } block (must contain "findings" or "agent_id")
    brace_depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                candidate = text[start:i + 1]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict) and ("findings" in result or "agent_id" in result):
                        return result
                except json.JSONDecodeError:
                    start = -1

    # Strategy 4: try to find any JSON object with at least 3 keys
    brace_depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                candidate = text[start:i + 1]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, dict) and len(result) >= 3:
                        return result
                except json.JSONDecodeError:
                    start = -1

    print(f"[AgentRunner] Could not extract valid JSON from {len(text)} chars output")
    print(f"[AgentRunner] First 500 chars: {text[:500]}")
    return None


def run_agents_parallel(prompts: dict[str, str], output_dir: Path) -> dict[str, dict]:
    """Run all agents in parallel. Returns {agent_id: result}."""
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_run_single_agent, agent_id, prompt, output_dir): agent_id
            for agent_id, prompt in prompts.items()
        }
        for future in as_completed(futures):
            agent_id = futures[future]
            try:
                results[agent_id] = future.result()
            except Exception as e:
                results[agent_id] = {
                    "agent_id": agent_id,
                    "status": "FAILED",
                    "error": str(e),
                }

    return results


def retry_failed_agents(
    results: dict[str, dict], prompts: dict[str, str], output_dir: Path
) -> dict[str, dict]:
    """Retry each failed agent once."""
    failed_ids = [aid for aid, r in results.items() if r.get("status") != "OK"]

    if not failed_ids:
        return results

    print(f"\n[AgentRunner] Retrying {len(failed_ids)} failed agent(s): {failed_ids}")

    for agent_id in failed_ids:
        print(f"[AgentRunner] Retrying {AGENTS[agent_id]['name']}...")
        result = _run_single_agent(agent_id, prompts[agent_id], output_dir)
        results[agent_id] = result

    return results
