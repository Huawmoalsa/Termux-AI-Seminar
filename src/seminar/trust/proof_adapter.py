"""Stable boundary for the external Proof/Trust implementation.

The adapter owns no proof algorithm. A verified proof implementation is
provided explicitly through callables/objects. When it is not bound, all
verification requests fail closed as UNAVAILABLE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ProofResult:
    status: str
    reason: str = ""
    value: Any = None


class ProofCoreAdapter:
    """Contract adapter between Seminar and the authoritative Proof Core."""

    def __init__(
        self,
        *,
        verify_fn: Callable[[Any], Any] | None = None,
        add_fact_fn: Callable[[Any], Any] | None = None,
    ) -> None:
        self._verify_fn = verify_fn
        self._add_fact_fn = add_fact_fn

    @property
    def available(self) -> bool:
        return self._verify_fn is not None

    def verify(self, claim: Any) -> ProofResult:
        if self._verify_fn is None:
            return ProofResult("UNAVAILABLE", "proof_core_not_bound")

        try:
            result = self._verify_fn(claim)
        except Exception as exc:
            return ProofResult("INVALID", str(exc))

        if isinstance(result, ProofResult):
            return result

        # Do not infer epistemic truth from arbitrary return values.
        return ProofResult("DELEGATED", value=result)

    def add_fact(self, fact: Any) -> None:
        if self._add_fact_fn is None:
            raise RuntimeError("proof_core_not_bound")
        self._add_fact_fn(fact)


__all__ = ["ProofCoreAdapter", "ProofResult"]
