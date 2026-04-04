            Added in `langchain-google-genai` 4.0.0.

            `ChatGoogleGenerativeAI` now supports both the **Gemini Developer API** and
            **Vertex AI Platform** as backend options.

        **For Gemini Developer API** (simplest):

        1. Set the `GOOGLE_API_KEY` environment variable (recommended), or
        2. Pass your API key using the [`api_key`][langchain_google_genai.ChatGoogleGenerativeAI.google_api_key]
            parameter

        ```python
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", api_key="...")
        ```

        **For Vertex AI Platform with API key**:

        ```bash
        export GEMINI_API_KEY='your-api-key'
        export GOOGLE_GENAI_USE_VERTEXAI=true
        export GOOGLE_CLOUD_PROJECT='your-project-id'
        ```

        ```python
        model = ChatGoogleGenerativeAI(model="gemini-3-pro-preview")
        # Or explicitly:
        model = ChatGoogleGenerativeAI(
            model="gemini-3-pro-preview",
            api_key="...",
            project="your-project-id",
            vertexai=True,
        )
        ```

        **For Vertex AI with credentials**:

        ```python
        model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            project="your-project-id",
            # Uses Application Default Credentials (ADC)
        )
        ```

        **Automatic backend detection** (when `vertexai=None` / unspecified):

        1. If `GOOGLE_GENAI_USE_VERTEXAI` env var is set, uses that value
        2. If `credentials` parameter is provided, uses Vertex AI
        3. If `project` parameter is provided, uses Vertex AI
        4. Otherwise, uses Gemini Developer API

    Environment variables:
        | Variable | Purpose | Backend |
        |----------|---------|---------|
        | `GOOGLE_API_KEY` | API key (primary) | Both (see `GOOGLE_GENAI_USE_VERTEXAI`) |
        | `GEMINI_API_KEY` | API key (fallback) | Both (see `GOOGLE_GENAI_USE_VERTEXAI`) |
        | `GOOGLE_GENAI_USE_VERTEXAI` | Force Vertex AI backend (`true`/`false`) | Vertex AI |
        | `GOOGLE_CLOUD_PROJECT` | GCP project ID | Vertex AI |
        | `GOOGLE_CLOUD_LOCATION` | GCP region (default: `global`) | Vertex AI |
