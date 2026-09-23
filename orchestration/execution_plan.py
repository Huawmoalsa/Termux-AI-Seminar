#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class ExecutionPlan:
    """
    Explicit structured execution request.

    Candidate.content is never converted into an ExecutionPlan.
    """

    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    purpose: str = ""
    voice: bool = False

    def __post_init__(self) -> None:
        name = str(self.tool_name).strip()

        if not name:
            raise ValueError(
                "ExecutionPlan.tool_name cannot be empty"
            )

        object.__setattr__(self, "tool_name", name)
        object.__setattr__(
            self,
            "arguments",
            dict(self.arguments or {}),
        )
        object.__setattr__(
            self,
            "purpose",
            str(self.purpose or ""),
        )
        object.__setattr__(
            self,
            "voice",
            bool(self.voice),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "arguments": dict(self.arguments),
            "purpose": self.purpose,
            "voice": self.voice,
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> "ExecutionPlan":
        if not isinstance(data, Mapping):
            raise TypeError(
                "ExecutionPlan requires a mapping"
            )

        return cls(
            tool_name=str(data.get("tool_name", "")),
            arguments=data.get("arguments", {}) or {},
            purpose=str(data.get("purpose", "") or ""),
            voice=bool(data.get("voice", False)),
        )


def make_tool_call(plan: ExecutionPlan) -> dict:
    """
    Convert the explicit plan to the exact structure expected by
    core.llm_client._dispatch_tool().
    """

    return {
        "function": {
            "name": plan.tool_name,
            "arguments": json.dumps(
                dict(plan.arguments),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
    }
