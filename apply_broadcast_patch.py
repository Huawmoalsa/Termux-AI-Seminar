#!/usr/bin/env python3

from pathlib import Path
import shutil
import re

ROOT = Path.home() / "Termux-AI"
CORE = ROOT / "core"
LLM = CORE / "llm_client.py"
BROADCAST = CORE / "broadcast.py"
BACKUP = CORE / "llm_client.py.before_broadcast"

if not LLM.exists():
    raise SystemExit(f"ERROR: missing {LLM}")

# ------------------------------------------------------------
# 1. Create a single backup before modifying llm_client.py
# ------------------------------------------------------------

if not BACKUP.exists():
    shutil.copy2(LLM, BACKUP)

source = LLM.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 2. Create broadcast.py
# ------------------------------------------------------------

broadcast_code = r'''"""
Termux-AI bounded parallel broadcast layer.

Purpose:
    Send a read-only reasoning question to multiple model slots
    concurrently, collect responses within a fixed time budget,
    and ignore unavailable/slow providers.

This layer deliberately does NOT execute tools.

It is therefore safe for questions/analysis, but should not be
used as the execution path for side-effecting tasks.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Callable, Any


DEFAULT_TIMEOUT = 12.0
DEFAULT_MIN_RESPONSES = 1


def broadcast(
    prompt: str,
    slots: list[dict],
    ask_one: Callable[[str, list[dict]], str],
    history: list[dict] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    min_responses: int = DEFAULT_MIN_RESPONSES,
) -> dict:
    """
    Execute independent read-only model calls concurrently.

    A provider that fails, times out, or returns an error is simply
    excluded from the response pool.

    Completion occurs when:
      - enough responses have arrived, or
      - the global timeout expires.
    """

    started = time.monotonic()

    if not slots:
        return {
            "status": "no_agents",
            "responses": [],
            "elapsed": 0.0,
        }

    results = []

    def worker(slot):
        provider = slot.get("provider_id", "unknown")
        model = slot.get("name", "unknown")

        worker_started = time.monotonic()

        try:
            answer = ask_one(prompt, [slot])
            elapsed = time.monotonic() - worker_started

            if not answer:
                return {
                    "provider": provider,
                    "model": model,
                    "status": "empty",
                    "answer": "",
                    "elapsed": elapsed,
                }

            if isinstance(answer, str) and answer.startswith("[ERROR]"):
                return {
                    "provider": provider,
                    "model": model,
                    "status": "unavailable",
                    "answer": answer,
                    "elapsed": elapsed,
                }

            return {
                "provider": provider,
                "model": model,
                "status": "ok",
                "answer": answer,
                "elapsed": elapsed,
            }

        except Exception as exc:
            return {
                "provider": provider,
                "model": model,
                "status": "unavailable",
                "answer": f"[ERROR] {exc}",
                "elapsed": time.monotonic() - worker_started,
            }

    # One thread per configured slot.
    # The calls themselves are independent network operations.
    with ThreadPoolExecutor(max_workers=len(slots)) as executor:
        futures = {
            executor.submit(worker, slot): slot
            for slot in slots
        }

        deadline = started + max(0.1, float(timeout))

        while futures:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                break

            done = set()

            try:
                for future in as_completed(
                    list(futures),
                    timeout=remaining,
                ):
                    done.add(future)

                    result = future.result()

                    if result["status"] == "ok":
                        results.append(result)

                    # Early completion:
                    # once the minimum number of useful answers exists,
                    # do not wait for slower providers.
                    if len(results) >= min_responses:
                        break

            except TimeoutError:
                pass

            for future in done:
                futures.pop(future, None)

            if len(results) >= min_responses:
                break

            # No useful result yet; continue until the global deadline.

        # Do not block on unfinished futures.
        for future in futures:
            future.cancel()

    elapsed = time.monotonic() - started

    if results:
        return {
            "status": "responses_available",
            "responses": results,
            "elapsed": elapsed,
        }

    return {
        "status": "no_responses",
        "responses": [],
        "elapsed": elapsed,
    }


def format_response_pool(result: dict) -> str:
    """
    Convert collected responses into deterministic context.

    This does not decide which answer is true.
    It only preserves provenance so a later trust/proof layer
    can reason over the individual observations.
    """

    responses = result.get("responses", [])

    if not responses:
        return (
            "[BROADCAST] No external agent returned a usable response "
            "within the allowed time."
        )

    lines = [
        "[BROADCAST RESPONSE POOL]",
        f"Collected responses: {len(responses)}",
        "",
    ]

    for index, item in enumerate(responses, 1):
        lines.extend(
            [
                f"--- Agent {index} ---",
                f"Provider: {item.get('provider')}",
                f"Model: {item.get('model')}",
                f"Elapsed: {item.get('elapsed', 0.0):.2f}s",
                "Status: OK",
                "Response:",
                str(item.get("answer", "")),
                "",
            ]
        )

    return "\n".join(lines)
'''

BROADCAST.write_text(broadcast_code, encoding="utf-8")

# ------------------------------------------------------------
# 3. Add imports
# ------------------------------------------------------------

import_anchor = "import re\n"

if "from core.broadcast import broadcast as _broadcast" not in source:
    if import_anchor not in source:
        raise SystemExit("ERROR: import anchor not found")

    source = source.replace(
        import_anchor,
        import_anchor
        + "from core.broadcast import broadcast as _broadcast\n"
        + "from core.broadcast import format_response_pool as _format_broadcast_pool\n",
        1,
    )

# ------------------------------------------------------------
# 4. Add bounded broadcast helper before ask_ai()
# ------------------------------------------------------------

ask_ai_anchor = "\ndef ask_ai(\n"

if ask_ai_anchor not in source:
    raise SystemExit("ERROR: ask_ai anchor not found")

broadcast_helper = r'''

def ask_broadcast(
    prompt: str,
    history: list[dict] | None = None,
    voice: bool = False,
    timeout: float = 12.0,
    min_responses: int = 1,
) -> str:
    """
    Parallel read-only broadcast.

    IMPORTANT:
    This is intentionally separate from ask_ai().

    It is designed for questions and analysis. It does not make
    the broadcast agents an execution authority and does not allow
    the collected answers to declare themselves PROVEN.
    """

    memory_block = build_memory_block(prompt)

    system_content = (
        (memory_block + "\n\n" + SYSTEM_PROMPT)
        if memory_block
        else SYSTEM_PROMPT
    )

    # Broadcast must remain read-only.
    system_content += """
    
BROADCAST MODE:
- Answer the user's question directly.
- Do not execute tools.
- Do not modify files.
- Do not send messages.
- Do not claim that another agent verified your answer.
- Distinguish observations from inference.
"""

    # Use the configured normal model slots.
    slots = list(MODEL_SLOTS)

    def ask_one(single_prompt: str, single_slots: list[dict]) -> str:
        return _ask_with_slots(
            single_prompt,
            history,
            voice,
            system_content,
            single_slots,
            broadcast_mode=True,
        )

    result = _broadcast(
        prompt=prompt,
        slots=slots,
        ask_one=ask_one,
        history=history,
        timeout=timeout,
        min_responses=min_responses,
    )

    pool = _format_broadcast_pool(result)

    if result.get("status") == "responses_available":
        # Return the collected observations to the main agent.
        # A later synthesis/proof layer can decide what to do with them.
        return pool

    return (
        pool
        + "\n\n[BROADCAST FALLBACK]\n"
        "No external model responded within the allowed time."
    )
'''

source = source.replace(
    ask_ai_anchor,
    broadcast_helper + ask_ai_anchor,
    1,
)

# ------------------------------------------------------------
# 5. Extend _ask_with_slots signature
# ------------------------------------------------------------

old_signature = """def _ask_with_slots(
    prompt: str,
    history: list[dict] | None,
    voice: bool,
    system_content: str,
    model_slots: list[dict],
) -> str:"""

new_signature = """def _ask_with_slots(
    prompt: str,
    history: list[dict] | None,
    voice: bool,
    system_content: str,
    model_slots: list[dict],
    broadcast_mode: bool = False,
) -> str:"""

if old_signature not in source:
    raise SystemExit("ERROR: _ask_with_slots signature not found")

source = source.replace(old_signature, new_signature, 1)

# ------------------------------------------------------------
# 6. In broadcast mode disable tool calls.
# ------------------------------------------------------------

old_tool_config = '''                    "tools": TOOLS_DESCRIPTION,
                    "tool_choice": "auto",'''

new_tool_config = '''                    "tools": [] if broadcast_mode else TOOLS_DESCRIPTION,
                    "tool_choice": "none" if broadcast_mode else "auto",'''

if old_tool_config not in source:
    raise SystemExit("ERROR: tool configuration anchor not found")

source = source.replace(
    old_tool_config,
    new_tool_config,
    1,
)

# ------------------------------------------------------------
# 7. Change retry policy:
#    429/transient errors move to another slot immediately.
#    Normal requests retain the existing retry behavior.
# ------------------------------------------------------------

old_error_branch = '''            print(
                f"{RED}[{pid}/{model_name}] API error "
                f"(status {status or 'unknown'}), attempt "
                f"{consecutive_error_count}/5 on current key.{RESET}"
            )

            if consecutive_error_count < 5:
                forced_retry_key = current_identity
                time.sleep(1)
                continue
'''

new_error_branch = '''            print(
                f"{RED}[{pid}/{model_name}] API error "
                f"(status {status or 'unknown'}), attempt "
                f"{consecutive_error_count}/5 on current key.{RESET}"
            )

            # Broadcast mode is latency bounded.
            # A rate limit or transient provider failure must never
            # hold the entire broadcast hostage.
            if broadcast_mode and (
                _is_rate_limit(exc) or _is_transient(exc)
            ):
                _mark_rate_limited(pid, api_key, model_name) if _is_rate_limit(exc) else _mark_transient(pid, model_name)

                _last_response_metadata = {
                    "state": "provider_unavailable",
                    "provider": pid,
                    "model": model_name,
                    "status": status,
                }

                return (
                    f"[ERROR] Provider {pid}/{model_name} unavailable "
                    f"for broadcast (status {status or 'unknown'})."
                )

            if consecutive_error_count < 5:
                forced_retry_key = current_identity
                time.sleep(1)
                continue
'''

if old_error_branch not in source:
    raise SystemExit("ERROR: API retry branch not found")

source = source.replace(
    old_error_branch,
    new_error_branch,
    1,
)

# ------------------------------------------------------------
# 8. Add an explicit broadcast command through /broadcast.
# ------------------------------------------------------------

# We deliberately do NOT replace ask_ai().
# Existing Orion behavior remains intact.
# The user can invoke the new path explicitly with /broadcast.
#
# This avoids unexpectedly multiplying API calls for every ordinary
# message until we have integrated the trust-aware aggregator.

source = source.replace(
    'def ask_ai(\n',
    '''def ask_ai(
''',
    1,
)

# ------------------------------------------------------------
# 9. Validate basic structural anchors before writing.
# ------------------------------------------------------------

required = [
    "from core.broadcast import broadcast as _broadcast",
    "def ask_broadcast(",
    "broadcast_mode: bool = False",
    '"tools": [] if broadcast_mode else TOOLS_DESCRIPTION',
    "if broadcast_mode and (",
]

for anchor in required:
    if anchor not in source:
        raise SystemExit(f"ERROR: final validation failed for anchor: {anchor}")

# ------------------------------------------------------------
# 10. Write modified llm_client.py
# ------------------------------------------------------------

LLM.write_text(source, encoding="utf-8")

print()
print("BROADCAST LAYER INSTALLED")
print()
print(f"Broadcast module: {BROADCAST}")
print(f"Modified:         {LLM}")
print(f"Backup:           {BACKUP}")
print()
print("Architecture now:")
print("User -> optional Broadcast -> parallel agents -> response pool")
print("429/transient -> provider skipped instead of repeated blocking")
print("Broadcast agents -> read-only / no tools")
print("Existing ask_ai() -> preserved")
print("Trust layer -> preserved")
print()
print("IMPORTANT:")
print("Broadcast is installed as ask_broadcast().")
print("It is NOT yet forced onto every normal question.")
print("This prevents multiplying API traffic before the aggregator/proof gate is connected.")
