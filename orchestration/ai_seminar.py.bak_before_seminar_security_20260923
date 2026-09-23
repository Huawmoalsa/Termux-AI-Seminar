#!/usr/bin/env python3
"""
AI Seminar Manager
==================

Protocol:

    PROPOSAL
        -> SELECTION
        -> INDEPENDENT_DEVELOPMENT
        -> UPGRADE_SELECTION
        -> DEVELOPMENT
        -> UPGRADE_SELECTION
        -> ...
        -> FINAL_DECISION
        -> EXECUTION
        -> EVIDENCE
        -> GUARD
        -> COMPLETED / KNOWLEDGE_READY / FAILED

Core rules:

1. The Manager is the only decision authority.
2. Agents produce proposals/candidates, never proof.
3. A selected candidate's developer is excluded from the NEXT
   development round only.
4. Development always creates new candidate versions.
5. Each developed candidate keeps a parent_candidate_id.
6. Independent development is development round #1.
7. Maximum development rounds = 3.
8. Agent budget exhaustion never terminates the whole seminar.
9. Full seminar history is not resent to agents.
10. Execution, Evidence and Guard are separate adapters.
11. No hard-coded model/provider is required.
12. No subprocess/shell execution is performed here.
13. A final candidate is preserved as KnowledgeOutput even when
    execution/evidence/verification is unavailable.
14. KNOWLEDGE_READY means the seminar produced a reusable knowledge
    artifact, not that the artifact or its execution is verified.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Allow this file to be executed directly from ~/Termux-AI/orchestration
# while still importing sibling project packages such as core/.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from orchestration.execution_plan import ExecutionPlan
    from orchestration.runtime_adapter import ExistingRuntimeAdapter
except ImportError:
    from execution_plan import ExecutionPlan
    from runtime_adapter import ExistingRuntimeAdapter
import time
import uuid


MAX_DEVELOPMENT_ROUNDS = 3


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class SeminarPhase(Enum):
    PROPOSAL = "proposal"
    SELECTION = "selection"
    INDEPENDENT_DEVELOPMENT = "independent_development"
    UPGRADE_SELECTION = "upgrade_selection"
    DEVELOPMENT = "development"
    FINAL_DECISION = "final_decision"
    EXECUTION = "execution"
    EVIDENCE = "evidence"
    GUARD = "guard"
    KNOWLEDGE_READY = "knowledge_ready"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------

@dataclass
class AgentBudget:
    max_calls: int = 3
    used_calls: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.used_calls)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    def consume(self) -> bool:
        if self.exhausted:
            return False

        self.used_calls += 1
        return True


# ---------------------------------------------------------------------------
# Proposal
# ---------------------------------------------------------------------------

@dataclass
class Proposal:
    proposal_id: str
    agent_id: str
    content: str
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    candidate_id: str
    content: str

    # Agent that originally proposed the lineage.
    origin_agent_id: str

    # Agent responsible for the current version.
    developer_agent_id: str

    # Parent version. None means root/original proposal.
    parent_candidate_id: Optional[str] = None

    # 0 = original proposal.
    # 1 = independent development.
    # 2/3 = subsequent development rounds.
    development_round: int = 0

    created_at: float = field(default_factory=time.time)

    @property
    def is_root(self) -> bool:
        return self.parent_candidate_id is None


# ---------------------------------------------------------------------------
# Development record
# ---------------------------------------------------------------------------

@dataclass
class DevelopmentRecord:
    round_number: int
    parent_candidate_id: str
    developer_agent_id: str
    candidate_id: str
    accepted_as_current: bool = False
    reason: str = ""


# ---------------------------------------------------------------------------
# Execution / Evidence
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    success: bool
    output: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    evidence_id: str
    source: str
    data: Any
    candidate_id: str
    created_at: float = field(default_factory=time.time)


@dataclass
class KnowledgeOutput:
    """Persistent reusable result of the Seminar reasoning process.

    This object is intentionally independent from live agent instances.
    It records the selected candidate plus its lineage and verification
    state so another Seminar can use it as a starting point.
    """

    candidate_id: str
    content: str
    task: str
    development_round: int
    origin_agent_id: str
    developer_agent_id: str
    parent_candidate_id: Optional[str] = None
    verification_status: str = "NOT_VERIFIED"
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "content": self.content,
            "task": self.task,
            "development_round": self.development_round,
            "origin_agent_id": self.origin_agent_id,
            "developer_agent_id": self.developer_agent_id,
            "parent_candidate_id": self.parent_candidate_id,
            "verification_status": self.verification_status,
            "evidence_ids": list(self.evidence_ids),
        }


# ---------------------------------------------------------------------------
# Seminar state
# ---------------------------------------------------------------------------

@dataclass
class SeminarState:

    # Explicit execution request.
    # Never inferred from Candidate.content.
    task: str

    phase: SeminarPhase = SeminarPhase.PROPOSAL

    proposals: List[Proposal] = field(default_factory=list)

    # All candidate versions ever created.
    candidates: Dict[str, Candidate] = field(default_factory=dict)

    # Candidate currently selected by the Manager.
    current_candidate_id: Optional[str] = None

    # Candidate finally selected for execution.
    final_candidate_id: Optional[str] = None

    # Current development round.
    development_round: int = 0

    # Agent temporarily excluded from the NEXT development round.
    temporarily_excluded_agent: Optional[str] = None

    development_records: List[DevelopmentRecord] = field(
        default_factory=list
    )

    execution_result: Optional[ExecutionResult] = None

    evidence: List[Evidence] = field(default_factory=list)

    # Reusable terminal knowledge artifact.
    knowledge_output: Optional[KnowledgeOutput] = None

    guard_passed: Optional[bool] = None

    guard_reason: str = ""

    events: List[Dict[str, Any]] = field(default_factory=list)

    error: Optional[str] = None
    # Explicit execution request.
    # Never inferred from Candidate.content.
    execution_plan: Optional[ExecutionPlan] = None


# ---------------------------------------------------------------------------
# Agent interface
# ---------------------------------------------------------------------------

class SeminarAgent(Protocol):

    agent_id: str

    def propose(self, task: str) -> str:
        ...

    def develop(
        self,
        task: str,
        parent: Candidate,
        round_number: int,
    ) -> str:
        ...


class FunctionAgent:
    """
    Small adapter useful for tests and later integration.

    proposal_fn:
        task -> proposal text

    development_fn:
        task, parent candidate, round -> developed text
    """

    def __init__(
        self,
        agent_id: str,
        proposal_fn: Callable[[str], str],
        development_fn: Callable[
            [str, Candidate, int],
            str,
        ],
    ):
        self.agent_id = agent_id
        self._proposal_fn = proposal_fn
        self._development_fn = development_fn

    def propose(self, task: str) -> str:
        return str(self._proposal_fn(task))

    def develop(
        self,
        task: str,
        parent: Candidate,
        round_number: int,
    ) -> str:
        return str(
            self._development_fn(
                task,
                parent,
                round_number,
            )
        )


# ---------------------------------------------------------------------------
# Evaluator interface
# ---------------------------------------------------------------------------

class CandidateEvaluator(Protocol):

    def is_valid(
        self,
        candidate: Candidate,
        parent: Optional[Candidate],
    ) -> bool:
        ...

    def material_improvement(
        self,
        parent: Candidate,
        candidate: Candidate,
    ) -> bool:
        ...


class ConservativeEvaluator:
    """
    Structural fallback evaluator.

    This is deliberately NOT a semantic quality authority.

    It verifies:
      - non-empty content
      - content differs from parent

    A stronger evaluator can be injected later without changing
    SeminarManager.
    """

    def is_valid(
        self,
        candidate: Candidate,
        parent: Optional[Candidate],
    ) -> bool:
        if not candidate.content.strip():
            return False

        if parent is not None:
            if not candidate.content.strip():
                return False

        return True

    def material_improvement(
        self,
        parent: Candidate,
        candidate: Candidate,
    ) -> bool:
        return (
            candidate.content.strip()
            != parent.content.strip()
        )


# ---------------------------------------------------------------------------
# Selection interface
# ---------------------------------------------------------------------------

class CandidateSelector(Protocol):

    def select(
        self,
        task: str,
        candidates: List[Candidate],
        current: Optional[Candidate],
        round_number: int,
    ) -> Optional[str]:
        ...


class FirstValidSelector:
    """
    Deterministic fallback selector.

    It deliberately does not pretend to perform semantic ranking.
    It simply returns the first valid candidate.

    Production integration can inject an evaluator/selector that
    uses an LLM or another decision mechanism.
    """

    def select(
        self,
        task: str,
        candidates: List[Candidate],
        current: Optional[Candidate],
        round_number: int,
    ) -> Optional[str]:

        if not candidates:
            return None

        return candidates[0].candidate_id


# ---------------------------------------------------------------------------
# Execution interface
# ---------------------------------------------------------------------------

class ExecutionAdapter(Protocol):

    def execute(
        self,
        candidate: Candidate,
        state: SeminarState,
    ) -> ExecutionResult:
        ...


class RuntimeExecutionAdapter:
    """
    Real execution adapter.

    Execution is possible only through an explicit ExecutionPlan.

    Candidate.content is never parsed or interpreted as executable
    code.
    """

    def __init__(self) -> None:
        self._runtime = ExistingRuntimeAdapter()

    def execute(
        self,
        candidate: Candidate,
        state: SeminarState,
    ) -> ExecutionResult:

        plan = state.execution_plan

        if plan is None:
            return ExecutionResult(
                success=False,
                output="",
                error=(
                    "No explicit ExecutionPlan was supplied. "
                    "Candidate prose is not executable."
                ),
                metadata={
                    "mode": "runtime",
                    "executed": False,
                    "reason": "missing_execution_plan",
                },
            )

        try:
            result = self._runtime.execute_plan(plan)

        except Exception as exc:
            return ExecutionResult(
                success=False,
                output="",
                error=str(exc),
                metadata={
                    "mode": "runtime",
                    "executed": False,
                    "reason": "runtime_exception",
                },
            )

        runtime_evidence = None

        if result.evidence is not None:
            runtime_evidence = {
                "fact_id": result.evidence.fact_id,
                "tool": result.evidence.tool,
                "success": result.evidence.success,
                "payload_hash": result.evidence.payload_hash,
                "timestamp": result.evidence.timestamp,
            }

        return ExecutionResult(
            success=result.success,
            output=result.output,
            error=result.error,
            metadata={
                "mode": "runtime",
                "executed": True,
                "tool_name": result.tool_name,
                "arguments": result.arguments or {},
                "runtime_evidence": runtime_evidence,
            },
        )


class NoopExecutionAdapter:
    """
    Safe default.

    It does not execute anything externally.
    """

    def execute(
        self,
        candidate: Candidate,
        state: SeminarState,
    ) -> ExecutionResult:

        return ExecutionResult(
            success=True,
            output=candidate.content,
            metadata={
                "mode": "noop",
                "executed": False,
            },
        )


# ---------------------------------------------------------------------------
# Evidence interface
# ---------------------------------------------------------------------------

class EvidenceAdapter(Protocol):

    def produce(
        self,
        candidate: Candidate,
        execution: ExecutionResult,
        state: SeminarState,
    ) -> List[Evidence]:
        ...


class ExecutionEvidenceAdapter:
    """
    Converts authenticated runtime evidence into a Seminar Evidence
    reference.

    Important:
        Execution output itself is NOT treated as trusted evidence.
        Trusted evidence must originate from the existing TRUST ledger.
    """

    def produce(
        self,
        candidate: Candidate,
        execution: ExecutionResult,
        state: SeminarState,
    ) -> List[Evidence]:

        if not execution.success:
            return []

        runtime_evidence = execution.metadata.get(
            "runtime_evidence"
        )

        if not isinstance(runtime_evidence, dict):
            return []

        fact_id = str(
            runtime_evidence.get("fact_id", "")
        ).strip()

        tool = str(
            runtime_evidence.get("tool", "")
        ).strip()

        payload_hash = str(
            runtime_evidence.get("payload_hash", "")
        ).strip()

        timestamp = runtime_evidence.get("timestamp")

        if not fact_id or not tool or not payload_hash:
            return []

        if not bool(
            runtime_evidence.get("success", False)
        ):
            return []

        return [
            Evidence(
                evidence_id=fact_id,
                source="TRUST",
                data={
                    "fact_id": fact_id,
                    "tool": tool,
                    "success": True,
                    "payload_hash": payload_hash,
                    "timestamp": timestamp,
                },
                candidate_id=candidate.candidate_id,
                created_at=time.time(),
            )
        ]


# ---------------------------------------------------------------------------
# Guard interface
# ---------------------------------------------------------------------------

class GuardAdapter(Protocol):

    def verify(
        self,
        candidate: Candidate,
        execution: ExecutionResult,
        evidence: List[Evidence],
        state: SeminarState,
    ) -> tuple[bool, str]:
        ...


class ConservativeGuard:
    """
    Minimal structural Guard.

    Production integration can replace this with the project's
    Proof / FactStore / Outer Guard layer.
    """

    def verify(
        self,
        candidate: Candidate,
        execution: ExecutionResult,
        evidence: List[Evidence],
        state: SeminarState,
    ) -> tuple[bool, str]:

        if not execution.success:
            return False, "execution_failed"

        if not evidence:
            return False, "no_evidence"

        return True, "structural_guard_passed"


# ---------------------------------------------------------------------------
# Seminar Console
# ---------------------------------------------------------------------------

class SeminarConsole:
    """Human-facing event renderer; it does not alter Seminar semantics."""

    def agent_result(
        self,
        agent_id: str,
        *,
        words: int = 0,
        elapsed: float = 0.0,
        error: Optional[str] = None,
        round_number: Optional[int] = None,
    ) -> None:
        suffix = "" if round_number is None else f" — round {round_number}"
        if error:
            print(f"{agent_id} — (خطأ) — {elapsed:.2f}s{suffix}")
        else:
            print(f"{agent_id} — {words} words — {elapsed:.2f}s{suffix}")

    def broadcast(self, message: str) -> None:
        print(f"[BROADCAST] {message}")


# ---------------------------------------------------------------------------
# Seminar Manager
# ---------------------------------------------------------------------------

class SeminarManager:

    def __init__(
        self,
        agents: List[SeminarAgent],
        *,
        budgets: Optional[Dict[str, AgentBudget]] = None,
        evaluator: Optional[CandidateEvaluator] = None,
        selector: Optional[CandidateSelector] = None,
        executor: Optional[ExecutionAdapter] = None,
        evidence_adapter: Optional[EvidenceAdapter] = None,
        guard: Optional[GuardAdapter] = None,
        max_development_rounds: int = MAX_DEVELOPMENT_ROUNDS,
        console: Optional[SeminarConsole] = None,
    ):
        if not agents:
            raise ValueError("At least one seminar agent is required")

        if max_development_rounds < 1:
            raise ValueError(
                "max_development_rounds must be >= 1"
            )

        self.agents = {
            agent.agent_id: agent
            for agent in agents
        }

        if len(self.agents) != len(agents):
            raise ValueError(
                "Agent IDs must be unique"
            )

        self.budgets = budgets or {
            agent_id: AgentBudget()
            for agent_id in self.agents
        }

        # Ensure every registered agent has a budget.
        for agent_id in self.agents:
            self.budgets.setdefault(
                agent_id,
                AgentBudget(),
            )

        self.evaluator = (
            evaluator
            or ConservativeEvaluator()
        )

        self.selector = (
            selector
            or FirstValidSelector()
        )

        self.executor = (
            executor
            or NoopExecutionAdapter()
        )

        self.evidence_adapter = (
            evidence_adapter
            or ExecutionEvidenceAdapter()
        )

        self.guard = (
            guard
            or ConservativeGuard()
        )

        self.max_development_rounds = (
            max_development_rounds
        )

        self.console = console or SeminarConsole()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    def _record(
        self,
        state: SeminarState,
        event: str,
        **data: Any,
    ) -> None:
        state.events.append(
            {
                "timestamp": time.time(),
                "event": event,
                **data,
            }
        )

    def _agent(
        self,
        agent_id: str,
    ) -> SeminarAgent:
        return self.agents[agent_id]

    def _consume_budget(
        self,
        agent_id: str,
    ) -> bool:
        budget = self.budgets[agent_id]

        if not budget.consume():
            return False

        return True

    def _candidate(
        self,
        state: SeminarState,
        candidate_id: str,
    ) -> Candidate:
        try:
            return state.candidates[candidate_id]
        except KeyError:
            raise ValueError(
                f"Unknown candidate: {candidate_id}"
            )

    def _current_candidate(
        self,
        state: SeminarState,
    ) -> Candidate:
        if state.current_candidate_id is None:
            raise ValueError(
                "No current candidate selected"
            )

        return self._candidate(
            state,
            state.current_candidate_id,
        )

    def _preserve_knowledge_output(
        self,
        state: SeminarState,
        *,
        verification_status: str = "NOT_VERIFIED",
    ) -> KnowledgeOutput:
        candidate = self._current_candidate(state)

        output = KnowledgeOutput(
            candidate_id=candidate.candidate_id,
            content=candidate.content,
            task=state.task,
            development_round=candidate.development_round,
            origin_agent_id=candidate.origin_agent_id,
            developer_agent_id=candidate.developer_agent_id,
            parent_candidate_id=candidate.parent_candidate_id,
            verification_status=verification_status,
            evidence_ids=[e.evidence_id for e in state.evidence],
        )

        state.knowledge_output = output
        self._record(
            state,
            "knowledge_output_preserved",
            candidate_id=output.candidate_id,
            verification_status=output.verification_status,
            evidence_count=len(output.evidence_ids),
        )
        return output

    # ------------------------------------------------------------------
    # Proposal phase
    # ------------------------------------------------------------------

    def collect_proposals(
        self,
        state: SeminarState,
    ) -> List[Proposal]:

        state.phase = SeminarPhase.PROPOSAL

        def worker(agent_id: str) -> tuple[str, Optional[str], Optional[str], float]:
            started = time.perf_counter()

            if not self._consume_budget(agent_id):
                self._record(
                    state,
                    "agent_budget_exhausted",
                    agent_id=agent_id,
                    phase=state.phase.value,
                )
                return agent_id, None, "budget_exhausted", 0.0

            try:
                content = self._agent(agent_id).propose(state.task)
                return (
                    agent_id,
                    str(content).strip(),
                    None,
                    time.perf_counter() - started,
                )
            except Exception as exc:
                return (
                    agent_id,
                    None,
                    str(exc),
                    time.perf_counter() - started,
                )

        results: Dict[str, tuple[Optional[str], Optional[str], float]] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(self.agents))) as pool:
            futures = {pool.submit(worker, agent_id): agent_id for agent_id in self.agents}
            for future in as_completed(futures):
                agent_id = futures[future]
                try:
                    _, content, error, elapsed = future.result()
                except Exception as exc:
                    content, error, elapsed = None, str(exc), 0.0
                results[agent_id] = (content, error, elapsed)

        for agent_id in self.agents:
            content, error, elapsed = results.get(agent_id, (None, "missing_result", 0.0))

            if error is not None:
                self._record(
                    state,
                    "proposal_failed",
                    agent_id=agent_id,
                    error=error,
                    elapsed=elapsed,
                )
                continue

            proposal = Proposal(
                proposal_id=self._new_id("proposal"),
                agent_id=agent_id,
                content=content or "",
            )

            if not proposal.content:
                self._record(
                    state,
                    "empty_proposal_rejected",
                    agent_id=agent_id,
                    elapsed=elapsed,
                )
                continue

            state.proposals.append(proposal)

            candidate = Candidate(
                candidate_id=self._new_id("candidate"),
                content=proposal.content,
                origin_agent_id=agent_id,
                developer_agent_id=agent_id,
                parent_candidate_id=None,
                development_round=0,
            )

            state.candidates[candidate.candidate_id] = candidate

            self._record(
                state,
                "proposal_accepted",
                agent_id=agent_id,
                proposal_id=proposal.proposal_id,
                candidate_id=candidate.candidate_id,
                words=len(proposal.content.split()),
                elapsed=elapsed,
            )

        for agent_id in self.agents:
            event = next((e for e in reversed(state.events) if e.get("agent_id") == agent_id and e.get("event") in {"proposal_accepted", "proposal_failed", "empty_proposal_rejected"}), None)
            if event is None:
                continue
            if event.get("event") == "proposal_accepted":
                self.console.agent_result(agent_id, words=event.get("words", 0), elapsed=event.get("elapsed", 0.0))
            else:
                self.console.agent_result(agent_id, elapsed=event.get("elapsed", 0.0), error=event.get("error") or event.get("event"))

        self.console.broadcast("Proposal phase completed")
        return state.proposals

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _select_from_candidates(
        self,
        state: SeminarState,
        candidates: List[Candidate],
        *,
        round_number: int,
    ) -> Optional[Candidate]:

        if not candidates:
            return None

        selected_id = self.selector.select(
            state.task,
            list(candidates),
            (
                self._current_candidate(state)
                if state.current_candidate_id
                else None
            ),
            round_number,
        )

        if selected_id is None:
            return None

        allowed_ids = {
            candidate.candidate_id
            for candidate in candidates
        }

        if selected_id not in allowed_ids:
            raise ValueError(
                "Selector returned a candidate that "
                "was not offered to it"
            )

        return self._candidate(
            state,
            selected_id,
        )

    def select_candidate(
        self,
        state: SeminarState,
    ) -> Optional[Candidate]:

        state.phase = SeminarPhase.SELECTION

        candidates = list(
            state.candidates.values()
        )

        selected = self._select_from_candidates(
            state,
            candidates,
            round_number=0,
        )

        if selected is None:
            return None

        state.current_candidate_id = (
            selected.candidate_id
        )

        self._record(
            state,
            "candidate_selected",
            candidate_id=selected.candidate_id,
            developer_agent_id=(
                selected.developer_agent_id
            ),
            round_number=0,
        )
        self.console.broadcast("Initial selection completed")

        return selected

    # ------------------------------------------------------------------
    # Development
    # ------------------------------------------------------------------

    def _eligible_developers(
        self,
        state: SeminarState,
        parent: Candidate,
    ) -> List[str]:

        excluded = (
            state.temporarily_excluded_agent
        )

        result: List[str] = []

        for agent_id in self.agents:

            # This is the critical independence rule.
            if (
                excluded is not None
                and agent_id == excluded
            ):
                continue

            if self.budgets[agent_id].exhausted:
                continue

            result.append(agent_id)

        return result

    def _develop_independently(
        self,
        state: SeminarState,
        parent: Candidate,
        round_number: int,
    ) -> List[Candidate]:

        eligible = self._eligible_developers(state, parent)

        def worker(agent_id: str) -> tuple[str, Optional[str], Optional[str], float]:
            started = time.perf_counter()

            if not self._consume_budget(agent_id):
                return agent_id, None, "budget_exhausted", 0.0

            try:
                content = self._agent(agent_id).develop(
                    state.task,
                    parent,
                    round_number,
                )
                return (
                    agent_id,
                    str(content).strip(),
                    None,
                    time.perf_counter() - started,
                )
            except Exception as exc:
                return (
                    agent_id,
                    None,
                    str(exc),
                    time.perf_counter() - started,
                )

        results: Dict[str, tuple[Optional[str], Optional[str], float]] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(eligible))) as pool:
            futures = {pool.submit(worker, agent_id): agent_id for agent_id in eligible}
            for future in as_completed(futures):
                agent_id = futures[future]
                try:
                    _, content, error, elapsed = future.result()
                except Exception as exc:
                    content, error, elapsed = None, str(exc), 0.0
                results[agent_id] = (content, error, elapsed)

        variants: List[Candidate] = []

        for agent_id in eligible:
            content, error, elapsed = results.get(agent_id, (None, "missing_result", 0.0))

            if error is not None:
                self._record(
                    state,
                    "development_failed",
                    agent_id=agent_id,
                    parent_candidate_id=parent.candidate_id,
                    round_number=round_number,
                    error=error,
                    elapsed=elapsed,
                )
                continue

            candidate = Candidate(
                candidate_id=self._new_id("candidate"),
                content=content or "",
                origin_agent_id=parent.origin_agent_id,
                developer_agent_id=agent_id,
                parent_candidate_id=parent.candidate_id,
                development_round=round_number,
            )

            if not self.evaluator.is_valid(candidate, parent):
                self._record(
                    state,
                    "candidate_rejected",
                    candidate_id=candidate.candidate_id,
                    agent_id=agent_id,
                    reason="invalid",
                    elapsed=elapsed,
                )
                continue

            if not self.evaluator.material_improvement(parent, candidate):
                self._record(
                    state,
                    "candidate_rejected",
                    candidate_id=candidate.candidate_id,
                    agent_id=agent_id,
                    reason="no_material_improvement",
                    elapsed=elapsed,
                )
                continue

            state.candidates[candidate.candidate_id] = candidate
            variants.append(candidate)

            state.development_records.append(
                DevelopmentRecord(
                    round_number=round_number,
                    parent_candidate_id=parent.candidate_id,
                    developer_agent_id=agent_id,
                    candidate_id=candidate.candidate_id,
                )
            )

            self._record(
                state,
                "candidate_developed",
                candidate_id=candidate.candidate_id,
                parent_candidate_id=parent.candidate_id,
                developer_agent_id=agent_id,
                round_number=round_number,
                words=len(candidate.content.split()),
                elapsed=elapsed,
            )

        for agent_id in eligible:
            event = next((e for e in reversed(state.events) if e.get("agent_id") == agent_id and e.get("round_number") == round_number and e.get("event") in {"candidate_developed", "development_failed", "candidate_rejected"}), None)
            if event is None:
                continue
            if event.get("event") == "candidate_developed":
                self.console.agent_result(agent_id, words=event.get("words", 0), elapsed=event.get("elapsed", 0.0), round_number=round_number)
            else:
                self.console.agent_result(agent_id, elapsed=event.get("elapsed", 0.0), error=event.get("error") or event.get("reason") or event.get("event"), round_number=round_number)

        self.console.broadcast(f"Development round {round_number} completed")
        return variants

    # ------------------------------------------------------------------
    # Round 1: Independent Development
    # ------------------------------------------------------------------

    def independent_development(
        self,
        state: SeminarState,
    ) -> List[Candidate]:

        if state.current_candidate_id is None:
            raise ValueError(
                "Cannot develop without a selected candidate"
            )

        if state.development_round != 0:
            raise ValueError(
                "Independent development must be round 1"
            )

        state.phase = (
            SeminarPhase.INDEPENDENT_DEVELOPMENT
        )

        state.development_round = 1

        parent = self._current_candidate(state)

        # The owner/developer of the selected candidate
        # is excluded for exactly this development round.
        state.temporarily_excluded_agent = (
            parent.developer_agent_id
        )

        self._record(
            state,
            "development_round_started",
            round_number=1,
            parent_candidate_id=parent.candidate_id,
            excluded_agent=(
                state.temporarily_excluded_agent
            ),
        )

        variants = self._develop_independently(
            state,
            parent,
            round_number=1,
        )

        return variants

    # ------------------------------------------------------------------
    # Upgrade selection
    # ------------------------------------------------------------------

    def select_for_upgrade(
        self,
        state: SeminarState,
        variants: Optional[List[Candidate]] = None,
    ) -> Optional[Candidate]:

        state.phase = SeminarPhase.UPGRADE_SELECTION

        parent = self._current_candidate(state)

        if variants is None:
            variants = [
                candidate
                for candidate in state.candidates.values()
                if (
                    candidate.parent_candidate_id
                    == parent.candidate_id
                    and candidate.development_round
                    == state.development_round
                )
            ]

        # If no independent improvement exists,
        # retain the current candidate and stop development.
        if not variants:
            self._record(
                state,
                "no_upgrade_available",
                round_number=state.development_round,
                candidate_id=parent.candidate_id,
            )

            # Temporary exclusion is cleared after
            # the round has ended.
            state.temporarily_excluded_agent = None

            self.console.broadcast(f"Upgrade selection completed — round {state.development_round}")
            return parent

        selected = self._select_from_candidates(
            state,
            variants,
            round_number=state.development_round,
        )

        if selected is None:
            state.temporarily_excluded_agent = None
            return parent

        state.current_candidate_id = (
            selected.candidate_id
        )

        # Record which variant became the current version.
        for record in reversed(
            state.development_records
        ):
            if (
                record.candidate_id
                == selected.candidate_id
                and record.round_number
                == state.development_round
            ):
                record.accepted_as_current = True
                break

        self._record(
            state,
            "upgrade_selected",
            candidate_id=selected.candidate_id,
            parent_candidate_id=(
                selected.parent_candidate_id
            ),
            developer_agent_id=(
                selected.developer_agent_id
            ),
            round_number=state.development_round,
        )

        # The exclusion only applied to this round.
        state.temporarily_excluded_agent = None

        self.console.broadcast(f"Upgrade selection completed — round {state.development_round}")
        return selected

    # ------------------------------------------------------------------
    # Subsequent development rounds
    # ------------------------------------------------------------------

    def develop_round(
        self,
        state: SeminarState,
    ) -> List[Candidate]:

        if state.current_candidate_id is None:
            raise ValueError(
                "Cannot develop without a current candidate"
            )

        if state.development_round >= (
            self.max_development_rounds
        ):
            return []

        parent = self._current_candidate(state)

        next_round = (
            state.development_round + 1
        )

        state.phase = SeminarPhase.DEVELOPMENT
        state.development_round = next_round

        # Exclude the developer of the currently selected
        # version from this NEXT round.
        state.temporarily_excluded_agent = (
            parent.developer_agent_id
        )

        self._record(
            state,
            "development_round_started",
            round_number=next_round,
            parent_candidate_id=parent.candidate_id,
            excluded_agent=(
                state.temporarily_excluded_agent
            ),
        )

        variants = self._develop_independently(
            state,
            parent,
            round_number=next_round,
        )

        return variants

    # ------------------------------------------------------------------
    # Final decision
    # ------------------------------------------------------------------

    def final_decision(
        self,
        state: SeminarState,
    ) -> Candidate:

        state.phase = SeminarPhase.FINAL_DECISION

        candidate = self._current_candidate(state)

        state.final_candidate_id = (
            candidate.candidate_id
        )

        self._record(
            state,
            "final_candidate_selected",
            candidate_id=candidate.candidate_id,
            developer_agent_id=(
                candidate.developer_agent_id
            ),
            development_round=(
                candidate.development_round
            ),
        )

        return candidate

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        state: SeminarState,
        execution_plan: Optional[ExecutionPlan] = None,
    ) -> ExecutionResult:
        if execution_plan is not None:
            state.execution_plan = execution_plan


        state.phase = SeminarPhase.EXECUTION

        candidate = self._current_candidate(state)

        try:
            result = self.executor.execute(
                candidate,
                state,
            )
        except Exception as exc:
            result = ExecutionResult(
                success=False,
                error=str(exc),
            )

        state.execution_result = result

        self._record(
            state,
            "execution_completed",
            candidate_id=candidate.candidate_id,
            success=result.success,
        )

        return result

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def produce_evidence(
        self,
        state: SeminarState,
    ) -> List[Evidence]:

        state.phase = SeminarPhase.EVIDENCE

        candidate = self._current_candidate(state)

        if state.execution_result is None:
            raise ValueError(
                "Cannot produce evidence before execution"
            )

        try:
            evidence = self.evidence_adapter.produce(
                candidate,
                state.execution_result,
                state,
            )
        except Exception as exc:
            state.error = str(exc)
            evidence = []

        state.evidence.extend(evidence)

        self._record(
            state,
            "evidence_produced",
            candidate_id=candidate.candidate_id,
            count=len(evidence),
        )

        return evidence

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def guard_result(
        self,
        state: SeminarState,
    ) -> bool:

        state.phase = SeminarPhase.GUARD

        candidate = self._current_candidate(state)

        if state.execution_result is None:
            state.guard_passed = False
            state.guard_reason = (
                "execution_missing"
            )
            return False

        try:
            passed, reason = self.guard.verify(
                candidate,
                state.execution_result,
                list(state.evidence),
                state,
            )
        except Exception as exc:
            passed = False
            reason = str(exc)

        state.guard_passed = bool(passed)
        state.guard_reason = str(reason)

        self._record(
            state,
            "guard_completed",
            candidate_id=candidate.candidate_id,
            passed=state.guard_passed,
            reason=state.guard_reason,
        )

        return state.guard_passed

    # ------------------------------------------------------------------
    # Full protocol
    # ------------------------------------------------------------------

    def run(
        self,
        task: str,
    ) -> SeminarState:

        state = SeminarState(task=task)

        try:
            # 1. Proposal
            self.collect_proposals(state)
            if not state.proposals:
                state.phase = SeminarPhase.FAILED
                state.error = "no_valid_proposals"
                return state

            # 2. Initial selection
            selected = self.select_candidate(state)
            if selected is None:
                state.phase = SeminarPhase.FAILED
                state.error = "initial_selection_failed"
                return state

            # 3. Development rounds
            while state.development_round < self.max_development_rounds:
                if state.development_round == 0:
                    variants = self.independent_development(state)
                else:
                    variants = self.develop_round(state)

                previous = self._current_candidate(state)
                upgraded = self.select_for_upgrade(state, variants)

                if upgraded.candidate_id == previous.candidate_id:
                    break

            # 4. Final decision
            self.final_decision(state)
            self.console.broadcast("Final decision completed")

            # Preserve the reasoning artifact immediately. Verification is
            # a separate property and never a prerequisite for preservation.
            self._preserve_knowledge_output(state, verification_status="NOT_VERIFIED")

            # 5. Execution
            execution = self.execute(state)
            self.console.broadcast("Execution completed")

            # Execution is unavailable when there is no explicit plan.
            # That does not invalidate the knowledge result.
            if not execution.success:
                reason = str(execution.metadata.get("reason", ""))
                if reason in {"missing_execution_plan", "execution_unavailable"}:
                    state.guard_passed = False
                    state.guard_reason = "execution_unavailable"
                    state.error = "execution_unavailable"
                    state.phase = SeminarPhase.KNOWLEDGE_READY
                    self._preserve_knowledge_output(
                        state,
                        verification_status="NOT_VERIFIED",
                    )
                    self.console.broadcast("Knowledge output preserved — execution unavailable")
                    return state

                state.error = execution.error or "execution_failed"
                state.knowledge_output.verification_status = "EXECUTION_FAILED"
                state.phase = SeminarPhase.FAILED
                self.console.broadcast("Knowledge output preserved — execution failed")
                return state

            # 6. Evidence
            self.produce_evidence(state)
            self.console.broadcast("Evidence phase completed")

            # 7. Guard
            if not self.guard_result(state):
                state.error = state.guard_reason or "guard_rejected_result"
                if state.guard_reason == "no_evidence" or not state.evidence:
                    state.phase = SeminarPhase.KNOWLEDGE_READY
                    self._preserve_knowledge_output(
                        state,
                        verification_status="NOT_VERIFIED",
                    )
                    self.console.broadcast("Knowledge output preserved — no authenticated evidence")
                    self.console.broadcast("Guard rejected result")
                    return state

                state.phase = SeminarPhase.FAILED
                state.knowledge_output.verification_status = "NOT_VERIFIED"
                self.console.broadcast("Guard rejected result")
                return state

            # 8. Verified completion
            state.knowledge_output.verification_status = "VERIFIED"
            state.knowledge_output.evidence_ids = [e.evidence_id for e in state.evidence]
            state.phase = SeminarPhase.COMPLETED

            self._record(
                state,
                "seminar_completed",
                candidate_id=state.final_candidate_id,
            )
            self.console.broadcast("Seminar completed — knowledge verified")
            return state

        except Exception as exc:
            state.phase = SeminarPhase.FAILED
            state.error = str(exc)
            if state.current_candidate_id is not None:
                try:
                    self._preserve_knowledge_output(
                        state,
                        verification_status="NOT_VERIFIED",
                    )
                except Exception:
                    pass
            self._record(state, "seminar_failed", error=str(exc))
            return state


# ---------------------------------------------------------------------------
# LLM boundary integrity
# ---------------------------------------------------------------------------

_AGENT_FAILURE_PREFIXES = (
    "[ERROR]",
    "[EMPTY RESPONSE]",
    "[External delegation unavailable]",
    "[LLM Unreachable:",
    "[HTTP Error ",
)


def _require_agent_content(result: Any, agent_id: str, operation: str) -> str:
    """Fail closed when the LLM layer returns a status/error sentinel."""
    content = "" if result is None else str(result).strip()
    if not content:
        raise RuntimeError(f"{agent_id}:{operation}:empty_response")
    for prefix in _AGENT_FAILURE_PREFIXES:
        if content.startswith(prefix):
            raise RuntimeError(f"{agent_id}:{operation}:llm_failure_response")
    return content


# ---------------------------------------------------------------------------
# LLM adapter
# ---------------------------------------------------------------------------

def build_llm_agent(
    agent_id: str,
) -> SeminarAgent:
    """
    Adapter around the existing core.llm_client.ask_agent.

    Important:
        history=[] is intentional.

    The Seminar Manager supplies only the local context needed for
    the current proposal/development operation. Full seminar history
    is not resent to the model.
    """

    from core.llm_client import ask_seminar_agent

    class LLMSeminarAgent:

        def __init__(self) -> None:
            self.agent_id = agent_id

        def propose(self, task: str) -> str:
            prompt = (
                "You are a proposal agent inside an AI Seminar.\n"
                "Produce a concrete candidate solution for the task.\n"
                "Your output is a proposal, not proof.\n\n"
                f"TASK:\n{task}"
            )

            result = ask_seminar_agent(
                prompt,
                history=[],
            )

            return _require_agent_content(result, self.agent_id, "proposal")

        def develop(
            self,
            task: str,
            parent: Candidate,
            round_number: int,
        ) -> str:

            prompt = (
                "You are an independent development agent inside "
                "an AI Seminar.\n"
                "Review the supplied candidate and produce an "
                "improved independent version.\n"
                "Do not claim verification or proof.\n"
                "Preserve useful parts when justified and correct "
                "errors or omissions.\n\n"
                f"TASK:\n{task}\n\n"
                f"DEVELOPMENT ROUND:\n{round_number}\n\n"
                "PARENT CANDIDATE:\n"
                f"{parent.content}"
            )

            result = ask_seminar_agent(
                prompt,
                history=[],
            )

            return _require_agent_content(result, self.agent_id, "development")

    return LLMSeminarAgent()

# ---------------------------------------------------------------------------
# Executable entry point
# ---------------------------------------------------------------------------

def _build_demo_agent(agent_id: str) -> SeminarAgent:
    """Deterministic local agent used for architecture tests."""

    def proposal_fn(task: str) -> str:
        return (
            f"[{agent_id}] Independent proposal for task: {task}. "
            f"Design a modular, verifiable solution."
        )

    def development_fn(task: str, parent: Candidate, round_no: int) -> str:
        return (
            f"[{agent_id}] Independent revision of candidate "
            f"{parent.candidate_id} for round {round_no}. "
            f"Task: {task}. Preserve valid parts and address weaknesses."
        )

    return FunctionAgent(
        agent_id=agent_id,
        proposal_fn=proposal_fn,
        development_fn=development_fn,
    )


def _build_demo_manager() -> SeminarManager:
    agents = [
        _build_demo_agent("A"),
        _build_demo_agent("B"),
        _build_demo_agent("C"),
    ]

    budgets = {
        "A": AgentBudget(max_calls=20),
        "B": AgentBudget(max_calls=20),
        "C": AgentBudget(max_calls=20),
    }

    return SeminarManager(
        agents,
        budgets=budgets,
        evaluator=ConservativeEvaluator(),
        selector=FirstValidSelector(),
        executor=NoopExecutionAdapter(),
        evidence_adapter=ExecutionEvidenceAdapter(),
        guard=ConservativeGuard(),
        max_development_rounds=MAX_DEVELOPMENT_ROUNDS,
    )


def _build_llm_manager() -> SeminarManager:
    """
    Real LLM-backed Seminar.

    The Seminar protocol remains deterministic and authoritative.
    The LLM only supplies proposals/developments.
    It does not select, execute, authenticate evidence, or approve claims.
    """

    agents = [
        build_llm_agent("A"),
        build_llm_agent("B"),
        build_llm_agent("C"),
    ]

    budgets = {
        "A": AgentBudget(max_calls=20),
        "B": AgentBudget(max_calls=20),
        "C": AgentBudget(max_calls=20),
    }

    return SeminarManager(
        agents,
        budgets=budgets,
        evaluator=ConservativeEvaluator(),
        selector=FirstValidSelector(),
        executor=RuntimeExecutionAdapter(),
        evidence_adapter=ExecutionEvidenceAdapter(),
        guard=ConservativeGuard(),
        max_development_rounds=MAX_DEVELOPMENT_ROUNDS,
    )


def _print_result(state: SeminarState) -> None:
    print()
    print("AI SEMINAR")
    print("=" * 60)
    print(f"Task: {state.task}")
    print(f"Phase: {state.phase.value}")
    print(f"Development rounds: {state.development_round}")
    print(f"Current candidate: {state.current_candidate_id}")
    print(f"Final candidate: {state.final_candidate_id}")
    print(f"Guard passed: {state.guard_passed}")
    print(f"Guard reason: {state.guard_reason}")
    print(f"Evidence count: {len(state.evidence)}")

    if state.error:
        print(f"Error: {state.error}")

    if state.knowledge_output is not None:
        ko = state.knowledge_output
        print()
        print("KNOWLEDGE OUTPUT")
        print("-" * 60)
        print(f"Candidate: {ko.candidate_id}")
        print(f"Verification: {ko.verification_status}")
        print(f"Round: {ko.development_round}")
        print(f"Origin agent: {ko.origin_agent_id}")
        print(f"Developer agent: {ko.developer_agent_id}")
        print(f"Parent: {ko.parent_candidate_id}")
        print(f"Evidence IDs: {ko.evidence_ids}")
        print()
        print(ko.content)

    print()
    print("CANDIDATE LINEAGE")
    print("-" * 60)

    for candidate in state.candidates.values():
        print(
            f"{candidate.candidate_id} | "
            f"origin={candidate.origin_agent_id} | "
            f"developer={candidate.developer_agent_id} | "
            f"parent={candidate.parent_candidate_id} | "
            f"round={candidate.development_round}"
        )

    print()
    print("EVENTS")
    print("-" * 60)

    for event in state.events:
        print(event)

    print()
    if state.phase == SeminarPhase.COMPLETED:
        print("SEMINAR COMPLETED")
    elif state.phase == SeminarPhase.KNOWLEDGE_READY:
        print("KNOWLEDGE OUTPUT READY")
    else:
        print("SEMINAR NOT COMPLETED")


def main() -> int:
    """
    CLI.

    Default:
        local deterministic demo.

    --demo:
        explicitly run the deterministic architecture test.

    --llm:
        run the same Seminar protocol with real LLM-backed agents.

    Important:
        --llm supplies proposals/developments only.
        Execution is gated by an explicit ExecutionPlan; candidate prose
        is never interpreted as executable code.
        When execution/evidence is unavailable, the final knowledge output
        is preserved as KNOWLEDGE_READY rather than discarded.
    """

    args = sys.argv[1:]

    mode = "demo"

    if args and args[0] in {"--demo", "demo"}:
        args = args[1:]
        mode = "demo"
    elif args and args[0] in {"--llm", "llm"}:
        args = args[1:]
        mode = "llm"
    elif args and args[0] in {"--help", "-h"}:
        print("Usage:")
        print("  ./ai_seminar.py [--demo] [task]")
        print("  ./ai_seminar.py --llm [task]")
        print()
        print("Default mode: deterministic local demo.")
        print("LLM mode: real Seminar agents via build_llm_agent().")
        print("Android execution is available only with an explicit ExecutionPlan.")
        return 0

    task = " ".join(args).strip()

    if not task:
        task = "Design a reliable Android AI agent architecture."

    if mode == "llm":
        manager = _build_llm_manager()
    else:
        manager = _build_demo_manager()

    state = manager.run(task)
    _print_result(state)

    return 0 if state.phase in {SeminarPhase.COMPLETED, SeminarPhase.KNOWLEDGE_READY} else 1


if __name__ == "__main__":
    raise SystemExit(main())

