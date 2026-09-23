#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import py_compile
import shutil
import sys
import time

ROOT = Path.home() / 'Termux-AI'
TARGET = ROOT / 'orchestration' / 'ai_seminar.py'

FAIL_PREFIXES = (
    '[ERROR]',
    '[EMPTY RESPONSE]',
    '[External delegation unavailable]',
    '[LLM Unreachable:',
    '[HTTP Error ',
)

HELPER = '''\n\n# ---------------------------------------------------------------------------\n# LLM boundary integrity\n# ---------------------------------------------------------------------------\n\n_AGENT_FAILURE_PREFIXES = (\n    "[ERROR]",\n    "[EMPTY RESPONSE]",\n    "[External delegation unavailable]",\n    "[LLM Unreachable:",\n    "[HTTP Error ",\n)\n\n\ndef _require_agent_content(result: Any, agent_id: str, operation: str) -> str:\n    """Convert an LLM result into valid Seminar content or fail closed.\n\n    Failure/status strings from the LLM layer are not proposals or\n    developments and must never enter Candidate content.\n    """\n    content = "" if result is None else str(result).strip()\n    if not content:\n        raise RuntimeError(\n            f"{agent_id}:{operation}:empty_response"\n        )\n\n    for prefix in _AGENT_FAILURE_PREFIXES:\n        if content.startswith(prefix):\n            raise RuntimeError(\n                f"{agent_id}:{operation}:llm_failure_response"\n            )\n\n    return content\n'''


def backup(path: Path) -> Path:
    stamp = time.strftime('%Y%m%d_%H%M%S')
    backup_path = path.with_name(f'{path.name}.bak_integrity_{stamp}')
    shutil.copy2(path, backup_path)
    return backup_path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)


def patch_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)

    original = path.read_text(encoding='utf-8')
    backup_path = backup(path)
    text = original

    # 1) Add the LLM -> Seminar boundary once.
    if '_require_agent_content' not in text:
        marker = '\ndef build_llm_agent(\n'
        if text.count(marker) != 1:
            raise RuntimeError('build_llm_agent marker not unique')
        text = text.replace(marker, HELPER + marker, 1)

    # 2) Replace both LLM return points with a fail-closed content contract.
    build_start = text.index('\ndef build_llm_agent(\n')
    build_end = text.index('\n# ---------------------------------------------------------------------------\n# Executable entry point', build_start)
    block = text[build_start:build_end]

    old_propose = '''            result = ask_agent(\n                prompt,\n                history=[],\n            )\n\n            return str(result)\n'''
    new_propose = '''            result = ask_agent(\n                prompt,\n                history=[],\n            )\n\n            return _require_agent_content(\n                result,\n                self.agent_id,\n                "proposal",\n            )\n'''

    old_develop = '''            result = ask_agent(\n                prompt,\n                history=[],\n            )\n\n            return str(result)\n'''
    new_develop = '''            result = ask_agent(\n                prompt,\n                history=[],\n            )\n\n            return _require_agent_content(\n                result,\n                self.agent_id,\n                "development",\n            )\n'''

    # The snippets are identical, so locate them in order rather than using a
    # broad replace that could modify unrelated functions.
    if block.count(old_propose) != 2:
        raise RuntimeError(
            'LLM adapter return pattern changed; refusing unsafe patch'
        )

    first = block.index(old_propose)
    block = block[:first] + block[first:].replace(old_propose, new_propose, 1)
    second = block.index(old_develop, first + len(new_propose))
    block = block[:second] + block[second:].replace(old_develop, new_develop, 1)
    text = text[:build_start] + block + text[build_end:]

    # 3) Wire only the real LLM Seminar builder to RuntimeExecutionAdapter.
    manager_start = text.index('\ndef _build_llm_manager() -> SeminarManager:\n')
    manager_end = text.index('\n\ndef _print_result(', manager_start)
    manager_block = text[manager_start:manager_end]

    if manager_block.count('executor=NoopExecutionAdapter(),') != 1:
        raise RuntimeError(
            'LLM manager executor anchor changed; refusing unsafe patch'
        )
    manager_block = manager_block.replace(
        'executor=NoopExecutionAdapter(),',
        'executor=RuntimeExecutionAdapter(),',
        1,
    )
    text = text[:manager_start] + manager_block + text[manager_end:]

    # 4) Make the CLI documentation truthful: --llm remains execution-plan
    # gated; it does not infer an execution plan from candidate prose.
    text = text.replace(
        'Execution remains behind ExecutionAdapter until the\n        Tool Runner / Evidence / Proof integration is added.',
        'Execution remains gated by an explicit ExecutionPlan; the CLI does not\n        infer executable actions from candidate prose.',
        1,
    )
    text = text.replace(
        'Android execution is not enabled by this CLI.',
        'Android execution is available only when an explicit ExecutionPlan is supplied.',
        1,
    )

    path.write_text(text, encoding='utf-8')
    return backup_path


def compile_check(path: Path) -> None:
    py_compile.compile(str(path), doraise=True)


def structural_test(path: Path) -> None:
    # Use compile + source-contract checks here. Full runtime tests belong on
    # the user's Termux project because this repair script is intended to
    # operate there and the local container does not contain its sibling
    # orchestration/runtime modules.
    source = path.read_text(encoding='utf-8')
    compile(source, str(path), 'exec')

    assert '_require_agent_content' in source
    assert source.count('return _require_agent_content(') == 2

    # The LLM boundary must reject the known failure/status sentinels.
    for marker in (
        '"[ERROR]"',
        '"[EMPTY RESPONSE]"',
        '"[External delegation unavailable]"',
        '"[LLM Unreachable:"',
        '"[HTTP Error "',
    ):
        assert marker in source, f'missing failure marker: {marker}'

    manager_start = source.index('def _build_llm_manager() -> SeminarManager:')
    manager_end = source.index('def _print_result(', manager_start)
    manager_block = source[manager_start:manager_end]
    assert 'executor=RuntimeExecutionAdapter(),' in manager_block
    assert 'executor=NoopExecutionAdapter(),' not in manager_block

    demo_start = source.index('def _build_demo_manager() -> SeminarManager:')
    demo_end = source.index('def _build_llm_manager() -> SeminarManager:', demo_start)
    demo_block = source[demo_start:demo_end]
    assert 'executor=NoopExecutionAdapter(),' in demo_block

    print('[PASS] Python syntax compile check')
    print('[PASS] LLM failure/status boundary present')
    print('[PASS] Both proposal/development returns are fail-closed')
    print('[PASS] LLM manager uses RuntimeExecutionAdapter')
    print('[PASS] Demo manager retains NoopExecutionAdapter')


def main() -> int:
    path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else TARGET
    backup_path = patch_file(path)
    try:
        compile_check(path)
        structural_test(path)
    except Exception:
        print('[FAIL] Repair was written, but validation failed.')
        print(f'[ROLLBACK] Restore: {backup_path}')
        raise

    print(f'[PASS] Backup: {backup_path}')
    print(f'[PASS] Patched: {path}')
    print('[PASS] Syntax compile check')
    print('[PASS] Integrity repair validation')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
