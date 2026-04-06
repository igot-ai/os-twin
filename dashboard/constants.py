ROLE_DEFAULTS = {
    "manager":   {"default_model": "google-vertex/gemini-3.1-pro-preview",  "timeout_seconds": 900},
    "engineer":  {"default_model": "google-vertex/gemini-3-flash-preview",  "timeout_seconds": 600},
    "qa":        {"default_model": "google-vertex/gemini-3-flash-preview",  "timeout_seconds": 600},
    "architect": {"default_model": "google-vertex/gemini-3-flash-preview",  "timeout_seconds": 900},
}

ACCESS_TOKEN_EXPIRE_MINUTES = 30
