PROVIDERS: dict[str, dict] = {
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1/",
    },
}


MODEL_SLOTS: list[dict] = [
    # Google
    {
        "provider_id": "google",
        "name": "gemini-3.8-flash",
        "max_tokens": None,
    },

    # Groq - production models first
    {
        "provider_id": "groq",
        "name": "openai/gpt-oss-120b",
        "max_tokens": 4096,
    },
    {
        "provider_id": "groq",
        "name": "openai/gpt-oss-20b",
        "max_tokens": 4096,
    },

    # Groq - preview fallback
    {
        "provider_id": "groq",
        "name": "qwen/qwen3.8-27b",
        "max_tokens": 4096,
    },

    # OpenRouter - free agentic/coding models
    {
        "provider_id": "openrouter",
        "name": "cohere/north-mini-code:free",
        "max_tokens": None,
    },
    {
        "provider_id": "openrouter",
        "name": "poolside/laguna-s-2.1:free",
        "max_tokens": None,
    },
    {
        "provider_id": "openrouter",
        "name": "nex-agi/nex-n2.5-pro:free",
        "max_tokens": None,
    },
    {
        "provider_id": "openrouter",
        "name": "thinkingmachines/inkling:free",
        "max_tokens": None,
    },
    {
        "provider_id": "openrouter",
        "name": "poolside/laguna-xs-2.1:free",
        "max_tokens": None,
    },
]


AGENT_MODEL_SLOTS: list[dict] = [
    # Google
    {
        "provider_id": "google",
        "name": "gemini-3.8-flash",
        "max_tokens": 4096,
    },

    # Groq
    {
        "provider_id": "groq",
        "name": "openai/gpt-oss-120b",
        "max_tokens": 4096,
    },
    {
        "provider_id": "groq",
        "name": "openai/gpt-oss-20b",
        "max_tokens": 4096,
    },
    {
        "provider_id": "groq",
        "name": "qwen/qwen3.8-27b",
        "max_tokens": 4096,
    },

    # OpenRouter
    {
        "provider_id": "openrouter",
        "name": "cohere/north-mini-code:free",
        "max_tokens": None,
    },
    {
        "provider_id": "openrouter",
        "name": "poolside/laguna-s-2.1:free",
        "max_tokens": None,
    },
    {
        "provider_id": "openrouter",
        "name": "nex-agi/nex-n2.5-pro:free",
        "max_tokens": None,
    },
    {
        "provider_id": "openrouter",
        "name": "thinkingmachines/inkling:free",
        "max_tokens": None,
    },
    {
        "provider_id": "openrouter",
        "name": "poolside/laguna-xs-2.1:free",
        "max_tokens": None,
    },
]
