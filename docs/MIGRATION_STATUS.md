# Seminar Migration Status

## Completed

Repository baseline, security baseline, architecture mapping, and initial internal import migration are complete.

Seminar agents use allow_tools=False and do not receive direct device tool execution capability.

The src/seminar/ tree is the future source of truth. Legacy components remain until their roles and dependencies are understood.

Internal imports in ai_seminar.py and runtime_adapter.py were redirected to the Seminar package and syntax-validated.

Git checkpoint: a772016 Redirect Seminar internal imports

## Next Step

Separate Seminar LLM responsibilities from legacy responsibilities in src/seminar/llm/client.py without unnecessary rewriting or deletion.

## Migration Rule

Each completed migration stage is documented and committed before proceeding to the next stage.

## Memory Adapter Extraction

The read-only memory retrieval functions used by Seminar LLM agents were extracted from the legacy tools module into:

`src/seminar/llm/memory.py`

The extracted component contains:

- `retrieve_memory()`
- `build_memory_block()`

The Seminar LLM client now imports `build_memory_block()` from the new Seminar memory module.

The extraction preserves the existing memory file and retrieval behavior while preventing this specific Seminar dependency from being obtained through the legacy wildcard tools import.

The legacy `tools` dependency remains temporarily because `llm/client.py` still contains other direct-agent and tool-execution responsibilities.

The new memory adapter was syntax-validated successfully.

