#!/usr/bin/env python3
"""
Install the first Trust/Evidence integration layer into Termux-AI.

Target:
    ~/Termux-AI/core/llm_client.py

Changes:
1. Adds core/trust_layer.py
2. Captures every successful tool result as authenticated evidence.
3. Gives every evidence record an immutable SHA-256 hash.
4. Keeps an append-only JSONL evidence ledger.
5. Prevents the LLM Critic from being the sole authority for VERIFIED.
6. Leaves WhatsApp, orchestration, provider routing, and existing tools untouched.

No external Python packages.
"""

from pathlib import Path
import hashlib
import json
import shutil
import time
import uuid


ROOT = Path.home() / "Termux-AI"
CORE = ROOT / "core"
LLM = CORE / "llm_client.py"
TRUST = CORE / "trust_layer.py"

if not ROOT.is_dir():
    raise SystemExit(f"Project not found: {ROOT}")

if not LLM.is_file():
    raise SystemExit(f"Missing file: {LLM}")

trust_code = r'''"""
Termux-AI Trust / Evidence Layer.

This module deliberately does NOT treat an LLM statement as evidence.

Evidence originates from executed tools/runtime observations.
The module provides:
    Tool result
        -> authenticated evidence
        -> immutable hash
        -> append-only ledger

This is the first integration layer.
Semantic Proof Graph construction remains a separate authority layer.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "data"
_LEDGER = _DATA / "evidence_ledger.jsonl"


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class EvidenceAuthority:
    """
    Local signing authority.

    The key is process-local unless TERMUX_AI_TRUST_SECRET is supplied.
    This prevents the LLM from manufacturing a valid evidence signature.
    """

    def __init__(self) -> None:
        secret = os.environ.get("TERMUX_AI_TRUST_SECRET")

        if secret:
            self._key = secret.encode("utf-8")
        else:
            self._key = os.urandom(32)

    def sign(self, payload: str) -> str:
        return hmac.new(
            self._key,
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def verify(self, payload: str, signature: str) -> bool:
        return hmac.compare_digest(
            self.sign(payload),
            signature,
        )


class EvidenceRecord:
    def __init__(
        self,
        tool: str,
        arguments: dict,
        result: Any,
        success: bool,
        duration_ms: int,
    ) -> None:

        self.fact_id = "FACT_" + uuid.uuid4().hex[:16]
        self.timestamp = time.time()

        self.tool = str(tool)
        self.arguments = dict(arguments or {})
        self.result = result
        self.success = bool(success)
        self.duration_ms = int(duration_ms)

        self.payload = {
            "fact_id": self.fact_id,
            "origin": "TOOL",
            "tool": self.tool,
            "arguments": self.arguments,
            "result": self.result,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }

        self.payload_hash = _sha256(_canonical(self.payload))


class EvidenceLedger:
    def __init__(self) -> None:
        self.authority = EvidenceAuthority()
        self.records: list[EvidenceRecord] = []

        _DATA.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        tool: str,
        arguments: dict,
        result: Any,
        success: bool,
        duration_ms: int,
    ) -> EvidenceRecord:

        fact = EvidenceRecord(
            tool=tool,
            arguments=arguments,
            result=result,
            success=success,
            duration_ms=duration_ms,
        )

        signature = self.authority.sign(
            fact.payload_hash
        )

        entry = {
            **fact.payload,
            "payload_hash": fact.payload_hash,
            "signature": signature,
        }

        with _LEDGER.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    entry,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )

        self.records.append(fact)

        return fact

    def latest(self) -> EvidenceRecord | None:
        if not self.records:
            return None

        return self.records[-1]

    def count(self) -> int:
        return len(self.records)


class TrustBoundary:
    """
    Central trust boundary used by llm_client.py.

    Important:
        LLM output is never inserted into this ledger as evidence.
    """

    def __init__(self) -> None:
        self.ledger = EvidenceLedger()

    def observe_tool(
        self,
        tool_name: str,
        arguments: dict,
        result: Any,
        success: bool,
        duration_ms: int,
    ) -> EvidenceRecord:

        return self.ledger.record(
            tool=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            duration_ms=duration_ms,
        )

    def evidence_context(self) -> str:
        fact = self.ledger.latest()

        if fact is None:
            return (
                "[TRUST] No authenticated tool evidence exists "
                "for this turn."
            )

        return (
            "[TRUST]\n"
            f"Evidence ID: {fact.fact_id}\n"
            f"Origin: TOOL\n"
            f"Tool: {fact.tool}\n"
            f"Success: {fact.success}\n"
            f"Payload hash: {fact.payload_hash}\n"
            "Important: tool evidence is an observation, not "
            "automatically a proven claim."
        )

    def critic_is_authoritative(self, critic_text: str) -> bool:
        """
        Deliberately always False.

        The LLM Critic is advisory only.
        A future Proof Graph validator will determine PROVEN.
        """
        return False

    def status(self) -> dict:
        latest = self.ledger.latest()

        return {
            "evidence_records": self.ledger.count(),
            "latest_fact_id": (
                latest.fact_id if latest else None
            ),
            "authority": "TOOL_ONLY",
            "llm_can_create_facts": False,
            "llm_critic_is_authority": False,
        }


TRUST = TrustBoundary()
'''


# ------------------------------------------------------------
# 1. Write Trust layer
# ------------------------------------------------------------

TRUST.write_text(trust_code, encoding="utf-8")


# ------------------------------------------------------------
# 2. Backup llm_client.py
# ------------------------------------------------------------

backup = LLM.with_suffix(
    ".py.before_trust_integration"
)

if not backup.exists():
    shutil.copy2(LLM, backup)


text = LLM.read_text(encoding="utf-8")


# ------------------------------------------------------------
# 3. Add import
# ------------------------------------------------------------

import_anchor = "import core.display_state as display_state\n"

if "from core.trust_layer import TRUST" not in text:

    if import_anchor not in text:
        raise SystemExit(
            "Integration anchor not found: display_state import"
        )

    text = text.replace(
        import_anchor,
        import_anchor
        + "from core.trust_layer import TRUST\n",
        1,
    )


# ------------------------------------------------------------
# 4. Capture successful tool results
# ------------------------------------------------------------

old = """        if expanded:
            print(f"{GRAY}[OUTPUT]{RESET}")
            print(f"{GRAY}{normalized}{RESET}")
        print(f"{GRAY}[TOOL DONE] ({elapsed:.2f}s){RESET}")

        return normalized
"""

new = """        if expanded:
            print(f"{GRAY}[OUTPUT]{RESET}")
            print(f"{GRAY}{normalized}{RESET}")
        print(f"{GRAY}[TOOL DONE] ({elapsed:.2f}s){RESET}")

        # --------------------------------------------------------
        # TRUST BOUNDARY
        # The result is registered as TOOL-origin evidence.
        # The LLM receives the observation but cannot manufacture
        # or sign the resulting evidence record.
        # --------------------------------------------------------
        try:
            TRUST.observe_tool(
                tool_name=name,
                arguments=args,
                result=normalized,
                success=True,
                duration_ms=int(elapsed * 1000),
            )
        except Exception as trust_exc:
            print(
                f"{YELLOW}[TRUST] Evidence recording failed: "
                f"{trust_exc}{RESET}"
            )

        return normalized
"""

if old not in text:
    raise SystemExit(
        "Integration anchor not found: successful tool return"
    )

text = text.replace(old, new, 1)


# ------------------------------------------------------------
# 5. Prevent LLM Critic from becoming verification authority
# ------------------------------------------------------------

old_verified_1 = """        if "VERIFIED" in critic_reply.upper():
            state_manager.update_subtask(task_id, status="completed",
                                         notes="Verified by LLM critic.")
            return f"Subtask {task_id} completed and verified."
"""

new_verified_1 = """        if "VERIFIED" in critic_reply.upper():
            # IMPORTANT:
            # The LLM critic is advisory only.
            # It cannot establish epistemic PROVEN state.
            state_manager.update_subtask(
                task_id,
                status="completed",
                notes=(
                    "Execution accepted; LLM critic advisory only. "
                    "No epistemic proof established."
                ),
                verification="CRITIC_ADVISORY_ONLY",
            )
            return (
                f"Subtask {task_id} completed. "
                "Critic marked it VERIFIED as an advisory execution result; "
                "no epistemic proof was established."
            )
"""

if old_verified_1 not in text:
    raise SystemExit(
        "Integration anchor not found: first critic verification block"
    )

text = text.replace(old_verified_1, new_verified_1, 1)


old_verified_2 = """        if "VERIFIED" in retry_critic_reply.upper():
            state_manager.update_subtask(task_id, status="completed",
                                         notes="Verified by LLM critic on retry.")
            return f"Subtask {task_id} completed on retry."
"""

new_verified_2 = """        if "VERIFIED" in retry_critic_reply.upper():
            # Critic remains advisory after retry as well.
            state_manager.update_subtask(
                task_id,
                status="completed",
                notes=(
                    "Execution completed on retry; LLM critic advisory only. "
                    "No epistemic proof established."
                ),
                verification="CRITIC_ADVISORY_ONLY",
            )
            return (
                f"Subtask {task_id} completed on retry. "
                "Critic verification is advisory only; "
                "no epistemic proof was established."
            )
"""

if old_verified_2 not in text:
    raise SystemExit(
        "Integration anchor not found: retry critic verification block"
    )

text = text.replace(old_verified_2, new_verified_2, 1)


# ------------------------------------------------------------
# 6. Expose evidence status to the agent system prompt
# ------------------------------------------------------------

prompt_anchor = """Preserve the existing architecture unless a change is necessary for correctness.
"""

prompt_addition = """Preserve the existing architecture unless a change is necessary for correctness.

TRUST / EPISTEMIC RULES:
- Tool output is observational evidence, not automatically PROVEN truth.
- The LLM is a proposer/interpreter, never the authority that authenticates evidence.
- The Critic is advisory only and must never be treated as the epistemic authority.
- Never claim that a fact is PROVEN unless a future Proof Graph validator establishes it.
- When evidence exists, distinguish TOOL observation from inference.
"""

if prompt_addition not in text:

    if prompt_anchor not in text:
        raise SystemExit(
            "Integration anchor not found: agent system prompt"
        )

    text = text.replace(
        prompt_anchor,
        prompt_addition,
        1,
    )


# ------------------------------------------------------------
# 7. Save
# ------------------------------------------------------------

LLM.write_text(text, encoding="utf-8")


print()
print("TRUST INTEGRATION INSTALLED")
print()
print(f"Project: {ROOT}")
print(f"Trust layer: {TRUST}")
print(f"Modified: {LLM}")
print(f"Backup: {backup}")
print()
print("Architecture now:")
print("Tool -> Evidence Adapter -> Authenticated Evidence Ledger")
print("LLM -> Proposer")
print("Critic -> Advisory only")
print("Proof Graph -> reserved as epistemic authority")
