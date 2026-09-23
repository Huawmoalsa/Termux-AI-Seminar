#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    from ..orchestration.execution_plan import (
        ExecutionPlan,
        make_tool_call,
    )
except ImportError:
    from execution_plan import (
        ExecutionPlan,
        make_tool_call,
    )


@dataclass(frozen=True)
class RuntimeEvidenceRef:
    """
    Reference to evidence already created by TRUST.

    This object does not create or sign evidence.
    """

    fact_id: str
    tool: str
    success: bool
    payload_hash: str
    timestamp: float


@dataclass(frozen=True)
class RuntimeResult:
    """
    Result returned by the existing runtime boundary.
    """

    success: bool
    output: str = ""
    error: str = ""
    tool_name: str = ""
    arguments: Optional[Dict[str, Any]] = None
    evidence: Optional[RuntimeEvidenceRef] = None


class ExistingRuntimeAdapter:
    """
    Bridge to the existing llm_client runtime.

    No subprocess is used here.
    No tool routing table is duplicated here.
    Candidate prose is never parsed here.
    """

    def __init__(self) -> None:
        from ..llm.client import _dispatch_tool

        self._dispatch_tool = _dispatch_tool

    @staticmethod
    def _latest_trust_record(
        expected_tool: str,
    ) -> Optional[RuntimeEvidenceRef]:

        from ..trust.core import TRUST

        try:
            record = TRUST.ledger.latest()
        except Exception:
            return None

        if record is None:
            return None

        tool = str(
            getattr(record, "tool", "") or ""
        )

        if tool != expected_tool:
            return None

        fact_id = str(
            getattr(record, "fact_id", "") or ""
        )

        if not fact_id:
            return None

        return RuntimeEvidenceRef(
            fact_id=fact_id,
            tool=tool,
            success=bool(
                getattr(record, "success", False)
            ),
            payload_hash=str(
                getattr(record, "payload_hash", "") or ""
            ),
            timestamp=float(
                getattr(record, "timestamp", 0.0) or 0.0
            ),
        )

    def execute_plan(
        self,
        plan: ExecutionPlan,
    ) -> RuntimeResult:

        if not isinstance(plan, ExecutionPlan):
            raise TypeError(
                "execute_plan() requires ExecutionPlan"
            )

        tool_call = make_tool_call(plan)

        try:
            output = self._dispatch_tool(
                tool_call,
                voice=plan.voice,
            )
        except Exception as exc:
            return RuntimeResult(
                success=False,
                error=(
                    f"{type(exc).__name__}: {exc}"
                ),
                tool_name=plan.tool_name,
                arguments=dict(plan.arguments),
            )

        normalized = str(output)

        if normalized.startswith("[TOOL ERROR]"):
            return RuntimeResult(
                success=False,
                output=normalized,
                error=normalized,
                tool_name=plan.tool_name,
                arguments=dict(plan.arguments),
                evidence=self._latest_trust_record(
                    plan.tool_name
                ),
            )

        if normalized.startswith(
            "[ERROR] Unknown tool:"
        ):
            return RuntimeResult(
                success=False,
                output=normalized,
                error=normalized,
                tool_name=plan.tool_name,
                arguments=dict(plan.arguments),
                evidence=None,
            )

        return RuntimeResult(
            success=True,
            output=normalized,
            tool_name=plan.tool_name,
            arguments=dict(plan.arguments),
            evidence=self._latest_trust_record(
                plan.tool_name
            ),
        )
