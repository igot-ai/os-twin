            }
            # Add the base_image as build arg if provided
            if base_image:
                compose_dict["services"]["langgraph-api"]["build"]["args"] = {
                    "BASE_IMAGE": base_image
                }
            f.write(langgraph_cli.docker.dict_to_yaml(compose_dict))
            secho("✅ Created: docker-compose.yml", fg="green")

        # Check if the .env file exists in the same directory as the Dockerfile
        if not (save_path.parent / ".env").exists():
            # Also add an empty .env file
            with open(str(save_path.parent / ".env"), "w", encoding="utf-8") as f:
                f.writelines(
                    [
                        "# Uncomment the following line to add your LangSmith API key",
                        "\n",
                        "# LANGSMITH_API_KEY=your-api-key",
                        "\n",
                        "# Or if you have a LangSmith Deployment license key, "
                        "then uncomment the following line: ",
                        "\n",
                        "# LANGGRAPH_CLOUD_LICENSE_KEY=your-license-key",
                        "\n",
                        "# Add any other environment variables go below...",
                    ]
                )

            secho("✅ Created: .env", fg="green")
        else:
            # Do nothing since the .env file already exists. Not a great
            # idea to overwrite in case the user has added custom env vars set
            # in the .env file already.
            secho("➖ Skipped: .env. It already exists!", fg="yellow")

    secho(
        f"🎉 Files generated successfully at path {save_path.parent}!",
        fg="cyan",
        bold=True,
    )

