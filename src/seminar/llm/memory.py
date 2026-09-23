import os
import re

import paths


_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by",
    "for", "from", "has", "have", "how", "i", "in",
    "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "was", "what", "when", "where", "which", "who",
    "why", "with", "you", "your",
}


_STRUCT_RE = re.compile(
    r"^\[(?P<type>[^\]]*)\]\[(?P<tags>[^\]]*)\]"
    r"\[(?P<priority>\d+)\]\s*(?P<text>.*)$"
)


def retrieve_memory(query: str, top_k: int = 5) -> str:
    mem_file = paths.MEMORY_FILE

    if not os.path.exists(mem_file):
        return "No relevant memory found."

    with open(mem_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return "No relevant memory found."

    q_words = set(re.findall(r"\w+", query.lower())) - _STOP_WORDS
    results = []

    for line in lines:
        match = _STRUCT_RE.match(line)

        if match:
            text = match.group("text")
            priority = int(match.group("priority"))
        else:
            text = line
            priority = 5

        t_words = set(re.findall(r"\w+", text.lower())) - _STOP_WORDS
        overlap = len(q_words & t_words)

        if overlap > 0:
            score = overlap * 10 + priority
            results.append((score, text))

    if not results:
        top_lines = lines[:top_k]
        return "\n".join(f"- {line}" for line in top_lines)

    results.sort(key=lambda item: item[0], reverse=True)
    top_res = results[:top_k]

    return "\n".join(
        f"- {text}"
        for score, text in top_res
    )


def build_memory_block(prompt: str) -> str:
    memories = retrieve_memory(
        query=prompt,
        top_k=5,
    )

    if not memories or "No relevant memory" in memories:
        return ""

    return (
        "## Long-Term Memory & Project Context\n"
        f"{memories}"
    )
