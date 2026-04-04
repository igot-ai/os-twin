        # Detect API keys (normalize empty strings to None)
        openai_key = os.environ.get("OPENAI_API_KEY") or None
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY") or None
        google_key = os.environ.get("GOOGLE_API_KEY") or None
        nvidia_key = os.environ.get("NVIDIA_API_KEY") or None
        tavily_key = os.environ.get("TAVILY_API_KEY") or None
        google_cloud_project = os.environ.get("GOOGLE_CLOUD_PROJECT")

        # Detect LangSmith configuration
        # DEEPAGENTS_LANGSMITH_PROJECT: Project for deepagents agent tracing
        # user_langchain_project: User's ORIGINAL LANGSMITH_PROJECT (before override)
        # Note: LANGSMITH_PROJECT was already overridden at module import time (above)
        # so we use the saved original value, not the current os.environ value
        deepagents_langchain_project = os.environ.get("DEEPAGENTS_LANGSMITH_PROJECT")
        user_langchain_project = _original_langsmith_project  # Use saved original!

