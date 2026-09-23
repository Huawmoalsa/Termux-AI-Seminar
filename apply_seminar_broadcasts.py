from pathlib import Path

p = Path("orchestration/ai_seminar.py")
s = p.read_text()

# 1. Proposal completed
old = """            self.collect_proposals(state)

            if not state.proposals:
"""

new = """            self.collect_proposals(state)

            self.console.broadcast(
                "Proposal phase completed"
            )

            if not state.proposals:
"""

if old not in s:
    raise SystemExit("ABORT 1: proposal boundary not found")

s = s.replace(old, new, 1)

# 2. Initial selection completed
old = """            if selected is None:
                state.phase = SeminarPhase.FAILED
                state.error = "initial_selection_failed"
                return state

            # ----------------------------------------------------------
            # 3. Development rounds
"""

new = """            if selected is None:
                state.phase = SeminarPhase.FAILED
                state.error = "initial_selection_failed"
                self.console.broadcast(
                    "Initial selection failed"
                )
                return state

            self.console.broadcast(
                "Initial selection completed"
            )

            # ----------------------------------------------------------
            # 3. Development rounds
"""

if old not in s:
    raise SystemExit("ABORT 2: selection boundary not found")

s = s.replace(old, new, 1)

# 3. Development + upgrade broadcast
old = """                upgraded = self.select_for_upgrade(
                    state,
                    variants,
                )

                # No material upgrade.
"""

new = """                upgraded = self.select_for_upgrade(
                    state,
                    variants,
                )

                self.console.broadcast(
                    f"Development round {state.development_round} "
                    "completed"
                )

                self.console.broadcast(
                    f"Upgrade selection completed — round "
                    f"{state.development_round}"
                )

                # No material upgrade.
"""

if old not in s:
    raise SystemExit("ABORT 3: development boundary not found")

s = s.replace(old, new, 1)

# 4. Final decision completed
old = """            self.final_decision(state)

            # ----------------------------------------------------------
            # 5. Execution
"""

new = """            self.final_decision(state)

            self.console.broadcast(
                "Final decision completed"
            )

            # ----------------------------------------------------------
            # 5. Execution
"""

if old not in s:
    raise SystemExit("ABORT 4: final decision boundary not found")

s = s.replace(old, new, 1)

# 5. Execution completed / failed
old = """            if not execution.success:
                state.phase = SeminarPhase.FAILED
                state.error = (
                    execution.error
                    or "execution_failed"
                )
                return state

            # ----------------------------------------------------------
            # 6. Evidence
"""

new = """            if not execution.success:
                state.phase = SeminarPhase.FAILED
                state.error = (
                    execution.error
                    or "execution_failed"
                )
                self.console.broadcast(
                    "Execution failed"
                )
                return state

            self.console.broadcast(
                "Execution completed"
            )

            # ----------------------------------------------------------
            # 6. Evidence
"""

if old not in s:
    raise SystemExit("ABORT 5: execution boundary not found")

s = s.replace(old, new, 1)

# 6. Evidence completed
old = """            self.produce_evidence(state)

            # ----------------------------------------------------------
            # 7. Guard
"""

new = """            self.produce_evidence(state)

            self.console.broadcast(
                "Evidence phase completed"
            )

            # ----------------------------------------------------------
            # 7. Guard
"""

if old not in s:
    raise SystemExit("ABORT 6: evidence boundary not found")

s = s.replace(old, new, 1)

# 7. Guard completed / failed
old = """            if not self.guard_result(state):
                state.phase = SeminarPhase.FAILED

                if not state.error:
                    state.error = (
                        state.guard_reason
                        or "guard_rejected_result"
                    )

                return state

            # ----------------------------------------------------------
            # 8. Complete
"""

new = """            if not self.guard_result(state):
                state.phase = SeminarPhase.FAILED

                if not state.error:
                    state.error = (
                        state.guard_reason
                        or "guard_rejected_result"
                    )

                self.console.broadcast(
                    "Guard rejected result"
                )

                return state

            self.console.broadcast(
                "Guard completed"
            )

            # ----------------------------------------------------------
            # 8. Complete
"""

if old not in s:
    raise SystemExit("ABORT 7: guard boundary not found")

s = s.replace(old, new, 1)

# 8. Completed
old = """            self._record(
                state,
                "seminar_completed",
                candidate_id=state.final_candidate_id,
            )

            return state
"""

new = """            self._record(
                state,
                "seminar_completed",
                candidate_id=state.final_candidate_id,
            )

            self.console.broadcast(
                "Seminar completed"
            )

            return state
"""

if old not in s:
    raise SystemExit("ABORT 8: completion boundary not found")

s = s.replace(old, new, 1)

p.write_text(s)
print("OK: Seminar broadcasts wired")
