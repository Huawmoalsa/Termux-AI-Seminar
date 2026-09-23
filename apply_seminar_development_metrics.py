from pathlib import Path

p = Path("orchestration/ai_seminar.py")
s = p.read_text()

# 1. Start timer immediately before agent.develop()
old = """            agent = self._agent(agent_id)

            try:
                content = agent.develop(
                    state.task,
                    parent,
                    round_number,
                )
"""

new = """            agent = self._agent(agent_id)

            started_at = time.perf_counter()

            try:
                content = agent.develop(
                    state.task,
                    parent,
                    round_number,
                )
"""

if old not in s:
    raise SystemExit("ABORT 1: development section not found")

s = s.replace(old, new, 1)

# 2. Render metrics before creating the Candidate
old = """            candidate = Candidate(
                candidate_id=self._new_id("candidate"),
                content=str(content).strip(),
                origin_agent_id=parent.origin_agent_id,
                developer_agent_id=agent_id,
                parent_candidate_id=parent.candidate_id,
                development_round=round_number,
            )
"""

new = """            elapsed = time.perf_counter() - started_at
            content_text = str(content).strip()

            self.console.agent_response(
                agent_id=agent_id,
                word_count=len(content_text.split()),
                elapsed=elapsed,
                round_number=round_number,
            )

            candidate = Candidate(
                candidate_id=self._new_id("candidate"),
                content=content_text,
                origin_agent_id=parent.origin_agent_id,
                developer_agent_id=agent_id,
                parent_candidate_id=parent.candidate_id,
                development_round=round_number,
            )
"""

if old not in s:
    raise SystemExit("ABORT 2: candidate construction not found")

s = s.replace(old, new, 1)

p.write_text(s)
print("OK: development metrics wired")
