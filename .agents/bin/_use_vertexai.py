
    @model_validator(mode="after")
    def _determine_backend(self) -> Self:
        """Determine which backend (Vertex AI or Gemini Developer API) to use.

        The backend is determined by the following priority:
        1. Explicit `vertexai` parameter value (if not None)
        2. `GOOGLE_GENAI_USE_VERTEXAI` environment variable
        3. Presence of `credentials` parameter (forces Vertex AI)
        4. Presence of `project` parameter (implies Vertex AI)
        5. Default to Gemini Developer API (False)

        Stores result in `_use_vertexai` attribute for use in client initialization.
        """
        use_vertexai = self.vertexai

        if use_vertexai is None:
            # Check environment variable
            env_var = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower()
            if env_var in ("true", "1", "yes"):
                use_vertexai = True
            elif env_var in ("false", "0", "no"):
                use_vertexai = False
            # Check for credentials (forces Vertex AI)
            elif self.credentials is not None:
                use_vertexai = True
            # Check for project (implies Vertex AI)
            elif self.project is not None:
                use_vertexai = True
            else:
                # Default to Gemini Developer API
                use_vertexai = False

        # Store the determined backend in a private attribute
        object.__setattr__(self, "_use_vertexai", use_vertexai)
        return self

    @property
    def lc_secrets(self) -> dict[str, str]:
        # Either could contain the API key
        return {
            "google_api_key": "GOOGLE_API_KEY",
            "gemini_api_key": "GEMINI_API_KEY",
        }

    @property
    def _identifying_params(self) -> dict[str, Any]:
        """Get the identifying parameters."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "max_output_tokens": self.max_output_tokens,
            "candidate_count": self.n,
            "image_config": self.image_config,
