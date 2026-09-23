#!/usr/bin/env python3
"""
Model health checker for Termux-AI.
Tests every model in MODEL_SLOTS and AGENT_MODEL_SLOTS with a minimal
non-tool request and reports OK / FAIL per model per key.
"""
import os
import sys
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- path bootstrap (same as llm_client.py) ---
_CORE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_CORE)
sys.path.insert(0, _CORE)
sys.path.insert(1, _ROOT)

import paths
from openai import OpenAI
from core.models import PROVIDERS, MODEL_SLOTS, AGENT_MODEL_SLOTS

# -------- colors --------
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GRAY   = "\033[90m"
CYAN   = "\033[96m"
RESET  = "\033[0m"

# -------- API key loading (mirrors llm_client._load_api_keys) --------
def load_api_keys() -> dict[str, list[str]]:
    path = paths.API_KEYS_FILE
    res: dict[str, list[str]] = {}
    if os.path.exists(path):
        try:
            raw = open(path, "r", encoding="utf-8").read().strip()
            data = json.loads(raw)
            res = {k: (v if isinstance(v, list) else [v]) for k, v in data.items()}
        except Exception:
            try:
                raw = open(path, "r", encoding="utf-8").read().strip()
                keys = [l.strip() for l in raw.splitlines() if l.strip()]
                res = {"google": keys}
            except Exception:
                res = {}
    env_map = {
        "openrouter": ["OPENROUTER_API_KEY"],
        "google":     ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "groq":       ["GROQ_API_KEY"],
        "mistral":    ["MISTRAL_API_KEY"],
    }
    for provider, env_vars in env_map.items():
        existing = res.get(provider, [])
        for ev in env_vars:
            val = os.environ.get(ev)
            if val and val not in existing:
                existing.append(val)
        res[provider] = existing
    return res

API_KEYS = load_api_keys()

# -------- status parser (copied from llm_client) --------
def error_status(exc: Exception) -> int | None:
    s = getattr(exc, "status_code", None)
    if isinstance(s, int):
        return s
    r = getattr(exc, "response", None)
    s = getattr(r, "status_code", None)
    if isinstance(s, int):
        return s
    msg = str(exc)
    for code in (400, 401, 403, 404, 429, 500, 502, 503, 504):
        if re.search(rf"\b{code}\b", msg):
            return code
    return None


def make_client(provider_id: str, api_key: str) -> OpenAI:
    headers = {}
    if provider_id == "openrouter":
        headers = {
            "HTTP-Referer": "https://github.com/opsonusdh/Termux-AI",
            "X-Title": "Termux-AI",
        }
    return OpenAI(
        api_key=api_key or "no-key",
        base_url=PROVIDERS[provider_id]["base_url"],
        default_headers=headers or None,
    )


# -------- single test --------
TEST_PROMPT = "Reply with exactly: OK"

def test_one(slot: dict, key_index: int, api_key: str, timeout: float = 25.0) -> dict:
    pid   = slot["provider_id"]
    model = slot["name"]
    max_tok = slot.get("max_tokens") or 64
    if max_tok > 64:
        max_tok = 64

    result = {
        "provider": pid,
        "model": model,
        "key_index": key_index,
        "status": None,
        "ok": False,
        "latency": None,
        "error": None,
    }

    try:
        client = make_client(pid, api_key)
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": TEST_PROMPT}],
            "max_tokens": max_tok,
        }
        # provider-specific quirks
        if pid == "groq":
            kwargs["reasoning_effort"] = "low"
        elif pid == "openrouter":
            kwargs["extra_body"] = {"reasoning": {"enabled": False}}

        t0 = time.monotonic()
        resp = client.chat.completions.create(**kwargs)
        dt = time.monotonic() - t0

        content = (resp.choices[0].message.content or "").strip()
        result["latency"] = round(dt, 2)
        result["ok"] = True
        result["status"] = 200
        result["error"] = f"reply: {content[:60]!r}"
    except Exception as exc:
        st = error_status(exc)
        result["status"] = st
        msg = str(exc)
        result["error"] = msg[:200]

    return result


# -------- runner --------
def run_for_slots(title: str, slots: list[dict], max_workers: int = 8):
    print(f"\n{CYAN}{'='*72}{RESET}")
    print(f"{CYAN}  {title}  ({len(slots)} models){RESET}")
    print(f"{CYAN}{'='*72}{RESET}")

    tasks = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for slot in slots:
            pid = slot["provider_id"]
            keys = API_KEYS.get(pid, [])
            if not keys:
                print(f"{YELLOW}[SKIP]{RESET} {pid}/{slot['name']} — no API key")
                continue
            # test only with the first key for brevity
            k = keys[0]
            tasks.append(pool.submit(test_one, slot, 0, k))

        for fut in as_completed(tasks):
            r = fut.result()
            tag = f"{r['provider']}/{r['model']}"
            if r["ok"]:
                print(
                    f"{GREEN}[OK]{RESET}   {tag:<60} "
                    f"{GRAY}{r['latency']}s | {r['error']}{RESET}"
                )
            else:
                print(
                    f"{RED}[FAIL]{RESET} {tag:<60} "
                    f"status={r['status']} | {r['error']}"
                )


def main():
    print(f"{CYAN}Termux-AI model health check{RESET}")
    print(f"{GRAY}API_KEYS_FILE = {paths.API_KEYS_FILE}{RESET}")
    for pid, keys in API_KEYS.items():
        print(f"{GRAY}  {pid:<12} -> {len(keys)} key(s){RESET}")

    run_for_slots("MODEL_SLOTS (chat + broadcast)", MODEL_SLOTS)
    run_for_slots("AGENT_MODEL_SLOTS (agent mode)", AGENT_MODEL_SLOTS)

    print(f"\n{CYAN}Done.{RESET}")


if __name__ == "__main__":
    main()
