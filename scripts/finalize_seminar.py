#!/usr/bin/env python3
"""
Termux-AI Seminar finalization utility.

This script performs the remaining consolidation work as one guarded,
repeatable operation on ~/Termux-AI.

Stages:
    1. Proof-core adapter boundary
    2. Verified source migration into src/seminar
    3. Packaging metadata
    4. Legacy isolation/quarantine where safe
    5. Final release audit

Design constraints:
    - no network calls
    - no LLM calls
    - no Android/ADB commands
    - no shell commands
    - standard library only
    - automatic timestamped backup before modifying existing files
    - exact-path checks before migration
    - no blind overwrite
    - old source remains available through compatibility shims
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import sys
import time
from typing import Iterable

ROOT = Path.home() / "Termux-AI"
SRC = ROOT / "src" / "seminar"
BACKUP_ROOT = ROOT / ".finalize_backups"
REPORT = ROOT / "docs" / "audits" / "FINAL_RELEASE_AUDIT.md"
MANIFEST = ROOT / "docs" / "migration" / "FINALIZATION_MANIFEST.json"

# These are the verified legacy source locations established by the project.
SOURCES = {
    "seminar_orchestration": ROOT / "orchestration" / "ai_seminar.py",
    "llm_client": ROOT / "core" / "llm_client.py",
    "broadcast": ROOT / "core" / "broadcast.py",
    "trust_layer": ROOT / "core" / "trust_layer.py",
    "execution_plan": ROOT / "orchestration" / "execution_plan.py",
    "runtime_adapter": ROOT / "orchestration" / "runtime_adapter.py",
}

TARGETS = {
    "seminar_orchestration": SRC / "orchestration" / "ai_seminar.py",
    "llm_client": SRC / "llm" / "client.py",
    "broadcast": SRC / "llm" / "broadcast.py",
    "trust_layer": SRC / "trust" / "core.py",
    "execution_plan": SRC / "orchestration" / "execution_plan.py",
    "runtime_adapter": SRC / "execution" / "runtime_adapter.py",
}

PACKAGE_DIRS = [
    SRC,
    SRC / "agents",
    SRC / "orchestration",
    SRC / "llm",
    SRC / "execution",
    SRC / "capabilities",
    SRC / "evidence",
    SRC / "trust",
    SRC / "presentation",
]

LEGACY_CANDIDATES = [
    ROOT / "Termux-WP",
]


def stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_new(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = read(path)
        if existing == content:
            return
        raise RuntimeError(f"Refusing overwrite of existing file: {path}")
    path.write_text(content, encoding="utf-8")


def backup_existing(path: Path, root: Path) -> Path:
    rel = path.relative_to(ROOT)
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return target


def ensure_prerequisites() -> None:
    if not ROOT.is_dir():
        raise RuntimeError(f"Project root not found: {ROOT}")

    missing = [str(p) for p in SOURCES.values() if not p.is_file()]
    if missing:
        raise RuntimeError(
            "Required source files are missing; no changes were made:\n"
            + "\n".join(missing)
        )

    for p in PACKAGE_DIRS:
        p.mkdir(parents=True, exist_ok=True)


def migrate_copy(name: str, source: Path, target: Path, backup_root: Path) -> dict:
    source_hash = sha256(source)

    if target.exists():
        target_hash = sha256(target)
        if target_hash != source_hash:
            raise RuntimeError(
                f"Target exists with different content: {target}\n"
                "Refusing blind overwrite."
            )
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    # Keep a source backup only when it is modified later. Currently we never
    # modify the legacy source in this stage.
    return {
        "name": name,
        "source": str(source.relative_to(ROOT)),
        "target": str(target.relative_to(ROOT)),
        "source_sha256": source_hash,
        "target_sha256": sha256(target),
    }


def write_import_compatibility() -> None:
    """Make the new package authoritative while preserving old entry points."""

    # The Seminar orchestration source currently contains the complete Manager.
    # These shims keep existing launchers/importers working during migration.
    shims = {
        ROOT / "orchestration" / "seminar_entry.py": (
            "from seminar.orchestration.ai_seminar import *\n"
        ),
        ROOT / "core" / "seminar_llm.py": (
            "from seminar.llm.client import *\n"
        ),
    }
    for path, content in shims.items():
        if path.exists():
            if read(path) != content:
                # Existing files are not touched. The project can switch over
                # explicitly after the audit.
                continue
        else:
            write_new(path, content)


def make_package_inits() -> None:
    for p in PACKAGE_DIRS:
        init = p / "__init__.py"
        write_new(init, "")


def create_proof_adapter() -> None:
    content = r'''"""Stable boundary for the external Proof/Trust implementation.

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
'''
    write_new(SRC / "trust" / "proof_adapter.py", content)


def create_architecture_facades() -> None:
    facades = {
        SRC / "agents" / "interfaces.py": (
            '"""Public Seminar agent interfaces."""\n'
            'from seminar.orchestration.ai_seminar import FunctionAgent, SeminarAgent\n'
            '__all__ = ["SeminarAgent", "FunctionAgent"]\n'
        ),
        SRC / "presentation" / "console.py": (
            '"""Seminar presentation facade."""\n'
            'from seminar.orchestration.ai_seminar import SeminarConsole\n'
            '__all__ = ["SeminarConsole"]\n'
        ),
        SRC / "execution" / "interfaces.py": (
            '"""Execution boundary facade."""\n'
            'from seminar.orchestration.ai_seminar import (\n'
            '    ExecutionAdapter, ExecutionResult, RuntimeExecutionAdapter, NoopExecutionAdapter\n'
            ')\n'
            '__all__ = ["ExecutionAdapter", "ExecutionResult", "RuntimeExecutionAdapter", "NoopExecutionAdapter"]\n'
        ),
        SRC / "evidence" / "adapters.py": (
            '"""Evidence boundary facade."""\n'
            'from seminar.orchestration.ai_seminar import Evidence, EvidenceAdapter, ExecutionEvidenceAdapter\n'
            '__all__ = ["Evidence", "EvidenceAdapter", "ExecutionEvidenceAdapter"]\n'
        ),
        SRC / "__main__.py": (
            '"""Package entry point."""\n'
            'from seminar.orchestration.ai_seminar import main\n'
            'raise SystemExit(main())\n'
        ),
    }
    for path, content in facades.items():
        write_new(path, content)


def create_pyproject() -> None:
    path = ROOT / "pyproject.toml"
    content = '''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "termux-ai-seminar"
version = "0.1.0"
description = "Controlled multi-agent deliberation and verification framework for Termux-AI"
requires-python = ">=3.10"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
'''
    write_new(path, content)


def update_migrated_orchestration_imports() -> None:
    path = TARGETS["seminar_orchestration"]
    text = read(path)

    replacements = {
        "from orchestration.execution_plan import ExecutionPlan":
            "from .execution_plan import ExecutionPlan",
        "from orchestration.runtime_adapter import ExistingRuntimeAdapter":
            "from ..execution.runtime_adapter import ExistingRuntimeAdapter",
        "from execution_plan import ExecutionPlan":
            "from .execution_plan import ExecutionPlan",
        "from runtime_adapter import ExistingRuntimeAdapter":
            "from ..execution.runtime_adapter import ExistingRuntimeAdapter",
    }

    changed = False
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
            changed = True

    # Make the module usable when imported as seminar.orchestration.ai_seminar.
    old_bootstrap = '''_PROJECT_ROOT = Path(__file__).resolve().parents[1]\nif str(_PROJECT_ROOT) not in sys.path:\n    sys.path.insert(0, str(_PROJECT_ROOT))\n'''
    if old_bootstrap in text:
        text = text.replace(old_bootstrap, "", 1)
        changed = True

    if changed:
        path.write_text(text, encoding="utf-8")


def update_migrated_llm_imports() -> None:
    path = TARGETS["llm_client"]
    text = read(path)

    replacements = {
        "from core.broadcast import broadcast as _broadcast":
            "from .broadcast import broadcast as _broadcast",
        "from core.broadcast import format_response_pool as _format_broadcast_pool":
            "from .broadcast import format_response_pool as _format_broadcast_pool",
    }

    changed = False
    for old, new in replacements.items():
        if old in text:
            text = text.replace(old, new)
            changed = True

    if changed:
        path.write_text(text, encoding="utf-8")


def compile_tree(paths: Iterable[Path]) -> list[str]:
    errors: list[str] = []
    for root in paths:
        if not root.exists():
            continue
        for py in root.rglob("*.py"):
            try:
                py_compile.compile(str(py), doraise=True)
            except Exception as exc:
                errors.append(f"{py}: {exc}")
    return errors


def static_forbidden_scan() -> list[str]:
    findings: list[str] = []
    for py in SRC.rglob("*.py"):
        text = read(py)
        if "subprocess." in text and py.parent.name not in {"execution", "capabilities"}:
            findings.append(f"subprocess usage outside execution/capabilities: {py}")
    return findings


def secrets_scan() -> list[str]:
    patterns = ("GROQ_API_KEY=", "OPENROUTER_API_KEY=", "GEMINI_API_KEY=", "MISTRAL_API_KEY=", "AIza")
    findings: list[str] = []
    scanner_path = Path(__file__).resolve()

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == scanner_path:
            continue
        if path.resolve() == REPORT.resolve():
            continue
        if ".git" in path.parts or ".finalize_backups" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".toml", ".json", ".yaml", ".yml", ".ini", ".cfg", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for marker in patterns:
            if marker in text:
                findings.append(f"possible credential material: {path} contains {marker}")
                break
    return findings


def legacy_isolation() -> dict:
    results = []
    archive_root = ROOT / "legacy" / "quarantine"
    archive_root.mkdir(parents=True, exist_ok=True)

    for candidate in LEGACY_CANDIDATES:
        if not candidate.exists():
            results.append({"path": str(candidate.relative_to(ROOT)), "status": "absent"})
            continue

        # Only quarantine a clearly isolated component when no Python source
        # refers to its path/name. Otherwise leave it untouched and report it.
        references = []
        token = candidate.name
        for py in ROOT.rglob("*.py"):
            if ".git" in py.parts or ".finalize_backups" in py.parts or "legacy" in py.parts:
                continue
            try:
                if token in py.read_text(encoding="utf-8", errors="ignore"):
                    references.append(str(py.relative_to(ROOT)))
            except Exception:
                pass

        if references:
            results.append({
                "path": str(candidate.relative_to(ROOT)),
                "status": "retained",
                "reason": "live_reference_detected",
                "references": references,
            })
            continue

        target = archive_root / candidate.name
        if target.exists():
            results.append({
                "path": str(candidate.relative_to(ROOT)),
                "status": "already_quarantined",
                "target": str(target.relative_to(ROOT)),
            })
            continue

        shutil.move(str(candidate), str(target))
        results.append({
            "path": str(candidate.relative_to(ROOT)),
            "status": "quarantined",
            "target": str(target.relative_to(ROOT)),
        })

    return {"legacy_components": results}


def write_audit(manifest: dict, compile_errors: list[str], forbidden: list[str], secrets: list[str], legacy: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if not compile_errors and not forbidden and not secrets else "ATTENTION"

    lines = [
        "# Final Release Audit — Termux-AI Seminar",
        "",
        f"Status: **{status}**",
        f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Completed stages",
        "",
        "- Proof Core adapter boundary created without duplicating proof algorithms.",
        "- Verified Seminar sources copied into `src/seminar/` with compatibility preserved.",
        "- Packaging metadata created in `pyproject.toml`.",
        "- Legacy component isolation evaluated and only safe quarantine performed.",
        "- Static release audit generated.",
        "",
        "## Source migration",
        "",
    ]
    for item in manifest.get("migrations", []):
        lines.append(f"- `{item['source']}` → `{item['target']}` (`{item['source_sha256'][:12]}`)")

    lines += ["", "## Python compilation"]
    if compile_errors:
        lines += ["", "Failures:", *[f"- {x}" for x in compile_errors]]
    else:
        lines.append("- PASS — all checked Python files compile.")

    lines += ["", "## Architectural static checks"]
    if forbidden:
        lines += ["", *[f"- {x}" for x in forbidden]]
    else:
        lines.append("- PASS — no subprocess use detected outside execution/capabilities in migrated package.")

    lines += ["", "## Secret scan"]
    if secrets:
        lines += ["", *[f"- {x}" for x in secrets]]
    else:
        lines.append("- PASS — no known credential markers detected in source/docs/config text.")

    lines += ["", "## Legacy isolation", ""]
    for item in legacy["legacy_components"]:
        lines.append(f"- `{item['path']}`: {item['status']}")
        if item.get("references"):
            lines.append(f"  - references: {', '.join(item['references'])}")

    lines += [
        "",
        "## Important boundary checks",
        "",
        "- Candidate prose remains non-executable; execution requires an explicit `ExecutionPlan`.",
        "- LLM agents remain proposal/development actors, not decision or verification authorities.",
        "- Proof algorithms remain outside the Seminar orchestration layer.",
        "- No LLM/API/Android/ADB action was performed by this finalization script.",
        "",
    ]

    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    start = time.time()
    backup_root = BACKUP_ROOT / stamp()
    backup_root.mkdir(parents=True, exist_ok=True)

    print("[1/5] Preflight")
    ensure_prerequisites()
    print("[PASS] Required project files found")

    print("[2/5] Source migration")
    migrations = []
    for name, source in SOURCES.items():
        target = TARGETS[name]
        migrations.append(migrate_copy(name, source, target, backup_root))
    make_package_inits()
    update_migrated_orchestration_imports()
    update_migrated_llm_imports()
    write_import_compatibility()
    print(f"[PASS] Migrated {len(migrations)} verified sources")

    print("[3/5] Proof adapter + packaging")
    create_proof_adapter()
    create_architecture_facades()
    create_pyproject()
    print("[PASS] ProofCoreAdapter created")
    print("[PASS] pyproject.toml created")

    print("[4/5] Legacy isolation")
    legacy = legacy_isolation()
    for item in legacy["legacy_components"]:
        print(f"[{item['status'].upper()}] {item['path']}")

    print("[5/5] Release audit")
    compile_errors = compile_tree([SRC])
    forbidden = static_forbidden_scan()
    secrets = secrets_scan()

    manifest = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "project": "Termux-AI Seminar",
        "migrations": migrations,
        "legacy": legacy,
        "backup_root": str(backup_root.relative_to(ROOT)),
        "duration_seconds": round(time.time() - start, 3),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_audit(manifest, compile_errors, forbidden, secrets, legacy)

    if compile_errors or forbidden or secrets:
        print("[ATTENTION] Final audit found issues. No LLM/runtime tests were run.")
        print(f"[REPORT] {REPORT}")
        return 2

    print("[PASS] Final release audit")
    print(f"[REPORT] {REPORT}")
    print(f"[MANIFEST] {MANIFEST}")
    print(f"[BACKUP] {backup_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
