#!/usr/bin/env python3

from pathlib import Path
import shutil

ROOT = Path.home() / "Termux-AI"
LLM = ROOT / "core" / "llm_client.py"
BACKUP = ROOT / "core" / "llm_client.py.before_broadcast_router"

if not LLM.exists():
    raise SystemExit(f"ERROR: {LLM} not found")

source = LLM.read_text(encoding="utf-8")

# ------------------------------------------------------------
# Backup
# ------------------------------------------------------------

if not BACKUP.exists():
    shutil.copy2(LLM, BACKUP)

# ------------------------------------------------------------
# Replace ask_ai() with a bounded intelligent router.
#
# Important:
# - Normal/simple questions keep the existing path.
# - Verification / comparison / analysis questions use broadcast.
# - Explicit execution requests stay on the normal agent path.
# - Broadcast itself calls _ask_with_slots() directly, so there
#   is no recursive routing.
# ------------------------------------------------------------

start = source.find("\ndef ask_ai(\n")

if start == -1:
    raise SystemExit("ERROR: ask_ai() start not found")

end = source.find("\ndef run_agent_step(", start)

if end == -1:
    raise SystemExit("ERROR: run_agent_step() boundary not found")

old_block = source[start:end]

new_block = r'''
def _broadcast_requested(prompt: str) -> bool:
    """
    Decide whether a question benefits from parallel independent
    model responses.

    This is deliberately conservative.

    Broadcast is intended for:
      - verification
      - comparison
      - multi-perspective analysis
      - explicit epistemic questions
      - questions where independent answers are useful

    It is NOT used for:
      - file modification
      - command execution
      - device control
      - tool execution
      - simple conversation
    """

    text = (prompt or "").strip().lower()

    if not text:
        return False

    # --------------------------------------------------------
    # Never broadcast obvious side-effecting operations.
    # --------------------------------------------------------

    execution_terms = (
        "run ",
        "execute ",
        "write file",
        "edit file",
        "modify file",
        "delete file",
        "install ",
        "uninstall ",
        "create file",
        "change file",
        "open terminal",
        "adb ",
        "termux ",
        "send message",
        "send whatsapp",
        "whatsapp ",
        "camera ",
        "screenshot",
        "take screenshot",
    )

    if any(term in text for term in execution_terms):
        return False

    # --------------------------------------------------------
    # Strong epistemic / verification signals.
    # --------------------------------------------------------

    strong_terms = (
        "how do you know",
        "how do u know",
        "why is that",
        "why do you say",
        "verify",
        "verified",
        "is this true",
        "is that true",
        "are you sure",
        "prove ",
        "proof",
        "evidence",
        "source",
        "sources",
        "fact check",
        "fact-check",
        "compare ",
        "comparison",
        "compare the",
        "pros and cons",
        "different opinions",
        "multiple perspectives",
        "analyze ",
        "analysis",
        "deep analysis",
        "cross-check",
        "cross check",
        "independent",
    )

    if any(term in text for term in strong_terms):
        return True

    # --------------------------------------------------------
    # Arabic equivalents.
    # --------------------------------------------------------

    arabic_terms = (
        "كيف تعرف",
        "كيف عرفت",
        "من أين عرفت",
        "ما دليلك",
        "هل هذا صحيح",
        "هل أنت متأكد",
        "تحقق",
        "تحقق من",
        "تأكد من",
        "الدليل",
        "الأدلة",
        "المصدر",
        "المصادر",
        "قارن",
        "مقارنة",
        "حلل",
        "تحليل",
        "تحليل عميق",
        "وجهات النظر",
        "آراء متعددة",
        "هل يمكنك إثبات",
        "اثبت",
    )

    if any(term in text for term in arabic_terms):
        return True

    return False


def ask_ai(
    prompt: str,
    history: list[dict] | None = None,
    voice: bool = False,
) -> str:
    """
    Main AI entry point.

    Routing policy:

        simple question
            -> normal Orion path

        epistemic / comparison / verification question
            -> bounded parallel broadcast

    Broadcast responses remain observations. They do not become
    PROVEN facts merely because multiple models agree.
    """

    if _broadcast_requested(prompt):
        try:
            return ask_broadcast(
                prompt,
                history=history,
                voice=voice,
                timeout=12.0,
                min_responses=1,
            )
        except Exception as exc:
            print(
                f"{YELLOW}[BROADCAST] unavailable: {exc}. "
                f"Falling back to primary agent.{RESET}"
            )

    return _ask_with_slots(
        prompt,
        history,
        voice,
        _AGENT_SYSTEM_PROMPT,
        MODEL_SLOTS,
    )

'''

# ------------------------------------------------------------
# Ensure ask_ai replacement is actually the expected one.
# ------------------------------------------------------------

if "def ask_broadcast(" not in source:
    raise SystemExit(
        "ERROR: ask_broadcast() is missing; previous broadcast "
        "integration is not present."
    )

source = source[:start] + "\n" + new_block + source[end:]

# ------------------------------------------------------------
# Structural validation
# ------------------------------------------------------------

required = (
    "def _broadcast_requested(prompt: str) -> bool:",
    "def ask_ai(",
    "ask_broadcast(",
    "return _ask_with_slots(",
    "timeout=12.0",
    "min_responses=1",
)

for anchor in required:
    if anchor not in source:
        raise SystemExit(
            f"ERROR: validation failed: missing {anchor}"
        )

# ------------------------------------------------------------
# Write
# ------------------------------------------------------------

LLM.write_text(source, encoding="utf-8")

print()
print("BROADCAST ROUTER INSTALLED")
print()
print(f"Modified: {LLM}")
print(f"Backup:   {BACKUP}")
print()
print("Routing:")
print("Simple question -> normal Orion agent")
print("Verification/comparison/analysis -> parallel Broadcast")
print("Execution/device/file tasks -> normal Orion path")
print("Broadcast timeout -> bounded fallback")
print("Broadcast responses -> observations, NOT proof")
print()
print("Trust layer preserved.")
print("No additional test is required at this stage.")
