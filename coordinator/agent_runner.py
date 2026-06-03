"""MACRS Coordinator - Agent Runner.

Dispatches 3 review agents in parallel using claude CLI subprocess.
Each agent runs independently with its own prompt.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from config import AGENT_TIMEOUT_SECONDS, AGENTS
from json_utils import extract_json
from llm_client import call_claude


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
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_content = f.read()

        stdout = call_claude(prompt_content, model="sonnet", timeout=AGENT_TIMEOUT_SECONDS)

        elapsed = time.time() - start_time

        if stdout is None:
            return {
                "agent_id": agent_id,
                "status": "FAILED",
                "error": "claude CLI returned no output",
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
    """Try to extract a JSON object from agent output text.

    Delegates to json_utils.extract_json with agent-specific fallbacks:
    first tries strict key matching (findings/agent_id), then any dict with >= 3 keys.
    """
    # Pass 1: strict keys (findings or agent_id)
    result = extract_json(text, strict_keys=True)
    if result is not None:
        return result

    # Pass 2: any dict with at least 3 keys
    result = extract_json(text, min_keys=3)
    if result is not None:
        return result

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
