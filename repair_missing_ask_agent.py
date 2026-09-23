from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
current = ROOT / "core" / "llm_client.py"
backup = ROOT / "core" / "llm_client.py.before_broadcast_router"

if not backup.exists():
    raise SystemExit(f"Backup not found: {backup}")

current_text = current.read_text(encoding="utf-8")
backup_text = backup.read_text(encoding="utf-8")

# If ask_agent already exists, do nothing.
try:
    current_tree = ast.parse(current_text)
    if any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "ask_agent"
        for n in current_tree.body
    ):
        print("ask_agent already exists. No change made.")
        raise SystemExit(0)
except SyntaxError as e:
    raise SystemExit(f"Current llm_client.py has syntax error: {e}")

# Extract the exact original ask_agent() from the backup.
tree = ast.parse(backup_text)

target = None
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "ask_agent":
        target = node
        break

if target is None:
    raise SystemExit("Could not find ask_agent() in the router backup.")

lines = backup_text.splitlines(keepends=True)
ask_agent_text = "".join(lines[target.lineno - 1:target.end_lineno])

marker = "\ndef run_agent_step("
pos = current_text.find(marker)

if pos == -1:
    raise SystemExit("Could not find run_agent_step() insertion point.")

patched = current_text[:pos] + "\n\n" + ask_agent_text.rstrip() + "\n" + current_text[pos:]

# Final structural validation before writing.
ast.parse(patched)

current.write_text(patched, encoding="utf-8")

print("ASK_AGENT RESTORED")
print(f"Source: {backup}")
print(f"Updated: {current}")
print("The Broadcast Router was preserved.")
