from pathlib import Path

p = Path("orchestration/ai_seminar.py")
s = p.read_text()

# 1. Add console parameter.
old = """        guard: Optional[GuardAdapter] = None,
        max_development_rounds: int = MAX_DEVELOPMENT_ROUNDS,
    ):
"""

new = """        guard: Optional[GuardAdapter] = None,
        max_development_rounds: int = MAX_DEVELOPMENT_ROUNDS,
        console: Optional[SeminarConsole] = None,
    ):
"""

if old not in s:
    raise SystemExit("ABORT 1: init marker not found")

s = s.replace(old, new, 1)

# 2. Store console.
old = """        self.max_development_rounds = (
            max_development_rounds
        )

    # ------------------------------------------------------------------
"""

new = """        self.max_development_rounds = (
            max_development_rounds
        )

        self.console = console or SeminarConsole()

    # ------------------------------------------------------------------
"""

if old not in s:
    raise SystemExit("ABORT 2: console storage marker not found")

s = s.replace(old, new, 1)

# 3. Proposal timing.
old = """            agent = self._agent(agent_id)

            try:
                content = agent.propose(state.task)
"""

new = """            agent = self._agent(agent_id)

            started_at = time.perf_counter()

            try:
                content = agent.propose(state.task)
"""

if old not in s:
    raise SystemExit("ABORT 3: proposal section not found")

s = s.replace(old, new, 1)

# 4. Proposal rendering.
old = """            proposal = Proposal(
                proposal_id=self._new_id("proposal"),
                agent_id=agent_id,
                content=str(content).strip(),
            )
"""

new = """            elapsed = time.perf_counter() - started_at
            content_text = str(content).strip()

            self.console.agent_response(
                agent_id=agent_id,
                word_count=len(content_text.split()),
                elapsed=elapsed,
            )

            proposal = Proposal(
                proposal_id=self._new_id("proposal"),
                agent_id=agent_id,
                content=content_text,
            )
"""

if old not in s:
    raise SystemExit("ABORT 4: proposal construction not found")

s = s.replace(old, new, 1)

p.write_text(s)
print("OK: proposal metrics wired")
