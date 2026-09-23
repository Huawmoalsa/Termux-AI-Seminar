from pathlib import Path

p = Path("orchestration/ai_seminar.py")
s = p.read_text()

marker = """# ---------------------------------------------------------------------------
# Seminar Manager
# ---------------------------------------------------------------------------

class SeminarManager:
"""

insert = '''# ---------------------------------------------------------------------------
# Seminar Console
# ---------------------------------------------------------------------------

class SeminarConsole:
    """Presentation-only renderer for Seminar events."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def agent_response(
        self,
        agent_id: str,
        word_count: int,
        elapsed: float,
        round_number=None,
    ) -> None:
        if not self.enabled:
            return

        suffix = (
            f" — round {round_number}"
            if round_number is not None
            else ""
        )

        print(
            f"{agent_id} — {word_count} words — "
            f"{elapsed:.2f}s{suffix}"
        )

    def broadcast(self, message: str) -> None:
        if self.enabled:
            print(f"[BROADCAST] {message}")


# ---------------------------------------------------------------------------
# Seminar Manager
# ---------------------------------------------------------------------------

class SeminarManager:
'''

if "class SeminarConsole:" in s:
    raise SystemExit("ABORT: SeminarConsole already exists")

if marker not in s:
    raise SystemExit("ABORT: SeminarManager marker not found")

s = s.replace(marker, insert, 1)

p.write_text(s)
print("OK: SeminarConsole added")
