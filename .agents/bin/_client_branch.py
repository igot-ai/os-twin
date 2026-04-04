            else:
                google_api_key = self.google_api_key

        base_url = self.base_url
        if isinstance(self.base_url, dict):
            # Handle case where base_url is provided as a dict
            # (Backwards compatibility for deprecated client_options field)
            if keys := list(self.base_url.keys()):
                if "api_endpoint" in keys and len(keys) == 1:
                    base_url = self.base_url["api_endpoint"]
                elif "api_endpoint" in keys and len(keys) > 1:
                    msg = (
                        "When providing base_url as a dict, it can only contain the "
                        "api_endpoint key. Extra keys found: "
                        f"{[k for k in keys if k != 'api_endpoint']}"
                    )
                    raise ValueError(msg)
                else:
                    msg = (
                        "When providing base_url as a dict, it must only contain the "
                        "api_endpoint key."
                    )
                    raise ValueError(msg)
            else:
                msg = (
                    "base_url must be a string or a dict containing the "
                    "api_endpoint key."
                )
                raise ValueError(msg)

        http_options = HttpOptions(
            base_url=cast("str", base_url),
            headers=headers,
            client_args=self.client_args,
            async_client_args=self.client_args,
        )

        if self._use_vertexai:  # type: ignore[attr-defined]
            # Vertex AI backend - supports both API key and credentials
            # Note: The google-genai SDK requires API keys to be passed via environment
            # variables when using Vertex AI, not via the api_key parameter.
            # If an API key is provided programmatically, we set it in the environment
            # temporarily for the Client initialization.

            # Normalize model name for Vertex AI - strip 'models/' prefix
            # Vertex AI expects model names without the prefix
