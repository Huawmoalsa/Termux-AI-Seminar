import ast
from pathlib import Path


TARGET = Path(__file__).resolve().parent / "ai_seminar.py"


def check(condition, label):
    status = "PASS" if condition else "FAIL"
    print(f"  {status:<4} {label}")
    return condition


def main():
    print("=" * 72)
    print("AI SEMINAR — ARCHITECTURE AUDIT")
    print("=" * 72)

    if not TARGET.exists():
        print("\nFAIL: ai_seminar.py not found")
        return 1

    source = TARGET.read_text(encoding="utf-8")

    # ------------------------------------------------------------
    # 1. Python syntax
    # ------------------------------------------------------------

    print("\n[1] SYNTAX")

    try:
        tree = ast.parse(source, filename=str(TARGET))
        check(True, "ast.parse()")
    except SyntaxError as exc:
        check(False, f"Python syntax: {exc}")
        return 1

    # ------------------------------------------------------------
    # 2. Required classes
    # ------------------------------------------------------------

    print("\n[2] REQUIRED CLASSES")

    required_classes = [
        "SeminarPhase",
        "AgentBudget",
        "Proposal",
        "Candidate",
        "DevelopmentRecord",
        "ExecutionResult",
        "Evidence",
        "SeminarState",
        "SeminarAgent",
        "FunctionAgent",
        "CandidateEvaluator",
        "ExecutionAdapter",
        "EvidenceAdapter",
        "GuardAdapter",
        "SeminarManager",
    ]

    classes = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }

    class_ok = True

    for name in required_classes:
        if not check(name in classes, name):
            class_ok = False

    # ------------------------------------------------------------
    # 3. State machine
    # ------------------------------------------------------------

    print("\n[3] STATE MACHINE")

    required_phases = [
        "PROPOSAL",
        "SELECTION",
        "INDEPENDENT_DEVELOPMENT",
        "UPGRADE_SELECTION",
        "DEVELOPMENT",
        "FINAL_DECISION",
        "EXECUTION",
        "EVIDENCE",
        "GUARD",
        "COMPLETED",
        "FAILED",
    ]

    phase_names = set()

    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "SeminarPhase"
        ):
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            phase_names.add(target.id)

    phase_ok = True

    for name in required_phases:
        if not check(name in phase_names, name):
            phase_ok = False

    # ------------------------------------------------------------
    # 4. Core architecture markers
    # ------------------------------------------------------------

    print("\n[4] CORE ARCHITECTURE")

    architecture_checks = {
        "Maximum development rounds":
            "MAX_DEVELOPMENT_ROUNDS" in source,

        "Temporary exclusion":
            "temporarily_excluded_agent" in source,

        "Candidate lineage":
            "parent_candidate_id" in source,

        "Developer identity":
            "developer_agent_id" in source,

        "Development round":
            "development_round" in source,

        "Material improvement evaluator":
            "material_improvement" in source,

        "Pluggable selector":
            "CandidateSelector" in source,

        "Execution adapter":
            "ExecutionAdapter" in source,

        "Evidence adapter":
            "EvidenceAdapter" in source,

        "Guard adapter":
            "GuardAdapter" in source,
    }

    architecture_ok = True

    for label, condition in architecture_checks.items():
        if not check(condition, label):
            architecture_ok = False

    # ------------------------------------------------------------
    # 5. Forbidden execution mechanisms
    # ------------------------------------------------------------

    print("\n[5] FORBIDDEN EXECUTION PATTERNS")

    forbidden_ok = True

    # Inspect executable AST nodes instead of raw source text.
    # This avoids false positives from comments/docstrings/strings.
    for node in ast.walk(tree):

        # import subprocess
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    print("  FAIL subprocess import")
                    forbidden_ok = False

        # from subprocess import ...
        elif isinstance(node, ast.ImportFrom):
            if node.module == "subprocess":
                print("  FAIL subprocess import")
                forbidden_ok = False

        elif isinstance(node, ast.Call):

            # eval(...) / exec(...)
            if isinstance(node.func, ast.Name):
                if node.func.id == "eval":
                    print("  FAIL eval() call")
                    forbidden_ok = False
                elif node.func.id == "exec":
                    print("  FAIL exec() call")
                    forbidden_ok = False

            # os.system(...)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "system"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
            ):
                print("  FAIL os.system() call")
                forbidden_ok = False

            # ask_broadcast(...)
            if isinstance(node.func, ast.Name) and node.func.id == "ask_broadcast":
                print("  FAIL ask_broadcast() call")
                forbidden_ok = False

            # shell=True
            for keyword in node.keywords:
                if (
                    keyword.arg == "shell"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    print("  FAIL shell=True")
                    forbidden_ok = False

    if forbidden_ok:
        print("  PASS no forbidden executable mechanisms found")

    # 6. Candidate immutability design check
    # ------------------------------------------------------------

    print("\n[6] CANDIDATE VERSIONING")

    mutation_patterns = [
        "candidate.content =",
        "candidate.parent_candidate_id =",
        "candidate.developer_agent_id =",
        "candidate.development_round =",
    ]

    versioning_ok = True

    for pattern in mutation_patterns:
        count = source.count(pattern)

        if count == 0:
            print(f"  PASS no in-place mutation: {pattern}")
        else:
            print(f"  FAIL in-place mutation: {pattern}")
            versioning_ok = False

    # ------------------------------------------------------------
    # 7. Required manager methods
    # ------------------------------------------------------------

    print("\n[7] MANAGER METHODS")

    required_methods = [
        "collect_proposals",
        "select_candidate",
        "independent_development",
        "select_for_upgrade",
        "develop_round",
        "final_decision",
        "execute",
        "produce_evidence",
        "guard_result",
        "run",
    ]

    manager_methods = set()

    for node in tree.body:
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "SeminarManager"
        ):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    manager_methods.add(item.name)

    methods_ok = True

    for name in required_methods:
        if not check(name in manager_methods, name):
            methods_ok = False

    # ------------------------------------------------------------
    # 8. Final result
    # ------------------------------------------------------------

    all_ok = (
        class_ok
        and phase_ok
        and architecture_ok
        and forbidden_ok
        and versioning_ok
        and methods_ok
    )

    print("\n" + "=" * 72)

    if all_ok:
        print("RESULT: ARCHITECTURE STATIC AUDIT — PASS")
    else:
        print("RESULT: ARCHITECTURE STATIC AUDIT — FAIL")

    print("=" * 72)

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
