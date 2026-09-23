"""
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
