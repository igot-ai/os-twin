            # variables when using Vertex AI, not via the api_key parameter.
            # If an API key is provided programmatically, we set it in the environment
            # temporarily for the Client initialization.

            # Normalize model name for Vertex AI - strip 'models/' prefix
            # Vertex AI expects model names without the prefix
            # (e.g., "gemini-2.5-flash") while Google AI accepts both formats
            if self.model.startswith("models/"):
                object.__setattr__(self, "model", self.model.replace("models/", "", 1))

            api_key_env_set = False

            if (
                google_api_key
                and not os.getenv("GOOGLE_API_KEY")
                and not os.getenv("GEMINI_API_KEY")
            ):
                # Set the API key in environment for Client initialization
                os.environ["GOOGLE_API_KEY"] = google_api_key
                api_key_env_set = True

            try:
                self.client = Client(
                    vertexai=True,
                    project=self.project,
                    location=self.location,
                    credentials=self.credentials,
                    http_options=http_options,
                )
            finally:
                # Clean up the temporary environment variable if we set it
                if api_key_env_set:
                    os.environ.pop("GOOGLE_API_KEY", None)
        else:
            # Gemini Developer API - requires API key
            if not google_api_key:
                msg = (
                    "API key required for Gemini Developer API. Provide api_key "
                    "parameter or set GOOGLE_API_KEY/GEMINI_API_KEY environment "
                    "variable."
                )
                raise ValueError(msg)
            self.client = Client(api_key=google_api_key, http_options=http_options)
        return self

    @model_validator(mode="after")
    def _set_model_profile(self) -> Self:
        """Set model profile if not overridden."""
        if self.profile is None:
            model_id = re.sub(r"-\d{3}$", "", self.model.replace("models/", ""))
            self.profile = _get_default_model_profile(model_id)
        return self

    def __del__(self) -> None:
        """Clean up the client on deletion."""
        if not hasattr(self, "client") or self.client is None:
            return

        try:
            # Close the sync client
            self.client.close()
