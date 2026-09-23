# Termux-AI Seminar
## Project Status

Date: 2026-09-23
Version: 0.1.0
Status: ARCHITECTURAL RELEASE CANDIDATE

---

## 1. Project Identity

Termux-AI Seminar is the standalone Seminar architecture derived from the
existing Termux-AI codebase.

The final project is not Orion and does not depend on the abandoned MalikClaw
direction.

The Seminar architecture is intended to provide controlled multi-agent
reasoning while keeping decision authority, execution authority, evidence
authority, and trust boundaries outside the LLM.

---

## 2. Core Seminar Protocol

The implemented protocol is:

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
    -> COMPLETED / FAILED / KNOWLEDGE_READY

The protocol supports bounded development rounds.

The selected developer is temporarily excluded from the next upgrade round
to encourage independent review. This is temporary exclusion, not permanent
removal, and the agent may participate in later rounds.

Development is bounded by MAX_DEVELOPMENT_ROUNDS and agent call budgets.

Early stopping is allowed when further development produces no material
improvement.

---

## 3. Authority Model

The Seminar Manager is the only decision authority.

LLM agents are proposal and development actors.

LLM agents do not:

- select the winning candidate;
- authenticate evidence;
- approve claims as verified;
- decide Guard outcomes;
- directly execute device operations;
- convert candidate prose into executable operations.

Candidate content is knowledge/proposal material, not executable authority.

---

## 4. Agent Model

The Seminar currently uses exactly three agents:

- Agent A
- Agent B
- Agent C

Each agent has an independent budget:

- max_calls = 20

The agent roster is considered closed for the current release.

No agent-roster redesign is part of the current release closure.

---

## 5. LLM Boundary

The Seminar LLM adapter is:

build_llm_agent()
    -> ask_seminar_agent()
    -> _ask_with_slots(..., allow_tools=False)

The Seminar LLM entry point explicitly uses:

allow_tools=False

The Seminar LLM function is documented as running an agent with no tool or
execution capability.

Therefore Seminar agents receive proposal/development capability but not
direct tool/device execution capability through the Seminar LLM path.

The Seminar intentionally uses:

history=[]

for each proposal/development operation so the complete Seminar dialogue is
not repeatedly resent to the LLM.

Only the context required for the current operation is supplied.

---

## 6. Execution Boundary

Candidate prose is never interpreted as executable code.

Execution requires an explicit ExecutionPlan.

The execution layer is separate from the LLM proposal layer.

The Manager controls the transition toward execution.

Execution adapters are responsible for controlled execution behavior.

No LLM agent is granted direct authority to execute arbitrary Android,
shell, ADB, or device commands.

---

## 7. Evidence and Trust Architecture

The trust architecture follows the separation:

Tool
    -> Evidence Adapter
    -> Authenticated Evidence Ledger

LLM
    -> Proposer

Critic
    -> Advisory role only

Proof/epistemic mechanisms
    -> Reserved for the trust/evidence layer

LLM output is not treated as proof merely because an LLM produced it.

Evidence must originate from controlled observation/execution paths rather
than from candidate prose.

The Guard remains outside LLM authority.

---

## 8. Broadcast Architecture

Broadcast is a supporting mechanism for comparison, verification-oriented
analysis, and related multi-agent operations.

Broadcast is not an authority layer.

Unreliable or unavailable remote agents may be skipped.

If remote responses are unavailable, the system can fall back to the local
agent path where supported.

Broadcast is not required for every Seminar operation.

---

## 9. Package Architecture

The target package is:

src/seminar/

with the following architectural areas:

src/seminar/
    orchestration/
    agents/
    llm/
    execution/
    capabilities/
    evidence/
    trust/
    presentation/

Tests belong under:

tests/

Documentation belongs under:

docs/

The migrated and verified core modules currently include:

- seminar.orchestration.ai_seminar
- seminar.orchestration.execution_plan
- seminar.llm.client
- seminar.llm.broadcast
- seminar.trust.core
- seminar.execution.runtime_adapter

---

## 10. Migrated Sources

The following verified sources were migrated into the new package:

orchestration/ai_seminar.py
    -> src/seminar/orchestration/ai_seminar.py

core/llm_client.py
    -> src/seminar/llm/client.py

core/broadcast.py
    -> src/seminar/llm/broadcast.py

core/trust_layer.py
    -> src/seminar/trust/core.py

orchestration/execution_plan.py
    -> src/seminar/orchestration/execution_plan.py

orchestration/runtime_adapter.py
    -> src/seminar/execution/runtime_adapter.py

Migration was performed with overwrite protection. Existing target files with
different content were not blindly overwritten.

---

## 11. Package Entry Point

The package entry point is:

src/seminar/__main__.py

Its responsibility is limited to invoking the Seminar CLI main function.

The CLI supports:

--demo
    deterministic local architecture/demo mode

--llm
    real LLM-backed Seminar mode

Default mode:

demo

The default task is:

Design a reliable Android AI agent architecture.

The LLM mode supplies proposals/developments only.

---

## 12. Packaging

Package metadata is defined in:

pyproject.toml

Package name:

termux-ai-seminar

Version:

0.1.0

The package entry point and package metadata were structurally verified.

---

## 13. Security and Static Verification

The following checks were completed:

Python compilation:
PASS

Required migrated source files:
PASS

Package imports:
PASS

SeminarManager availability:
PASS

ExecutionPlan availability:
PASS

Package entry point:
PASS

pyproject metadata:
PASS

Static forbidden-operation scan:
PASS

Secret scan:
PASS

Final release audit:
PASS

No LLM/API runtime execution was required for these checks.

No Android/ADB/device execution was performed during release closure.

---

## 14. Release Audit

The main release audit is:

docs/audits/FINAL_RELEASE_AUDIT.md

The audit verifies compilation, architectural restrictions, forbidden
operations, and secret-scan conditions.

The final audit state is:

RELEASE AUDIT: PASS

---

## 15. Release Closure

The release closure document is:

docs/audits/RELEASE_CLOSURE.md

It records the final architectural state and intentionally records that
real LLM/API and Android/ADB execution were not performed as part of the
release closure.

This was deliberate. Release closure is not intended to become an
uncontrolled runtime experiment.

---

## 16. Legacy Isolation

The legacy Termux-WP tree remains retained because existing legacy files
still reference it.

It is not part of the new Seminar execution architecture.

Its retention is a compatibility/isolation decision, not an indication that
Termux-WP is part of the Seminar core.

---

## 17. Important Completed Decisions

The following decisions are considered closed for this release:

- Standalone Seminar rather than Orion as the final project direction.
- No continuation of the MalikClaw direction.
- Three-agent Seminar roster.
- Manager as the sole decision authority.
- Candidate prose is non-executable.
- Explicit ExecutionPlan required for execution.
- LLM Seminar agents use allow_tools=False.
- Evidence and Guard remain outside LLM authority.
- Broadcast is supporting infrastructure, not epistemic authority.
- Bounded development rounds.
- Temporary exclusion of the selected developer from the immediate upgrade
  round.
- No blind migration overwrite.
- No unnecessary runtime/API testing during architectural closure.
- WhatsApp integration is not part of the current active Seminar runtime.
- Project source code, documentation, comments, audit reports, README,
  CHANGELOG, ADRs, test names, and test messages are English-only.

---

## 18. Deliberately Not Reopened

The following subjects are closed unless a new architectural requirement
explicitly requires them:

- Agent roster changes.
- Mistral agent setup.
- API-key marker discussion.
- Re-running the migration finalizer.
- Repeating the same static/import checks without a code change.
- Reopening allow_tools=False as a design question.
- Rebuilding the project from scratch.
- Returning to Orion ownership/path assumptions.

---

## 19. Current Release Boundary

The project is currently at:

ARCHITECTURAL RELEASE CANDIDATE

This means the architecture and static security boundary have been closed
and documented.

It does not mean that every possible runtime integration scenario has been
tested.

In particular, a real LLM/API runtime test remains a separate controlled
validation activity.

Android/device execution validation is also a separate controlled activity
and is not part of the architectural release closure.

---

## 20. Next Work

Future work should begin from this document.

New work should be classified before implementation as one of:

1. Feature development
2. Controlled runtime validation
3. Bug correction
4. Documentation improvement
5. Packaging/release work

Architectural migration and repeated security inspection should not be
restarted unless new evidence requires it.

---

## 21. Source of Truth

For current project status, use this document together with:

docs/audits/FINAL_RELEASE_AUDIT.md
docs/audits/RELEASE_CLOSURE.md

These documents define the recorded release state of Termux-AI Seminar 0.1.0.
