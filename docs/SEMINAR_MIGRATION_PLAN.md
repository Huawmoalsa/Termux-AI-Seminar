# Termux-AI-Seminar Migration Plan

## Purpose

Migrate the current Termux-AI codebase into a standalone, secure, maintainable Seminar architecture without losing verified work or repeating previous development.

## Current Baseline

- Repository: Termux-AI-Seminar
- Git history: independent from the legacy Orion repository history
- Main branch: synchronized with GitHub
- SSH authentication: configured
- Working tree: clean before this document
- Secrets: API key files are not tracked by Git
- Agent tool boundary: allow_tools=False

## Migration Phases

### 1. Baseline and Security
- Verify secrets and Git tracking boundaries.
- Confirm agent tool restrictions.
- Review .gitignore.

### 2. Architecture Mapping
- Map existing modules to the target src/seminar architecture.
- Identify dependencies before moving files.
- Preserve working behavior during migration.

### 3. Migration
- Move reusable Seminar components into src/seminar.
- Organize orchestration, agents, llm, execution, capabilities, evidence, trust, and presentation.
- Avoid unnecessary rewrites.

### 4. Validation
- Verify imports and startup.
- Verify Seminar protocol.
- Verify allow_tools=False.
- Verify Trust and Evidence boundaries.
- Verify Broadcast and fallback behavior.
- Verify presentation behavior.

### 5. Cleanup
- Remove obsolete backups, caches, patch scripts, and migration artifacts after dependency checks.
- Separate unrelated legacy projects.
- Finalize .gitignore.

### 6. Documentation
- Complete README.md.
- Align PROJECT_STRUCTURE.md.
- Align CHANGELOG.md and security documentation.
- Record important architectural decisions.

### 7. Release Baseline
- Clean working tree.
- Passing validation.
- Clear release commit.
- Push synchronized state to GitHub.

## Working Rule

Do not delete or rewrite existing components until their dependencies and role in the target architecture are understood. Complete one phase before moving to the next.

## Status

Phase 1: Completed.
Phase 2: Completed.
Phase 3: In progress (core Seminar migration completed; further extraction is intentionally deferred).
Phase 4: Not started.
Phase 5: Not started.
Phase 6: In progress.
Phase 7: Not started.
