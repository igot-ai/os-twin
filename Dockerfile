# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Force the installer to use /root/.ostwin instead of assuming $HOME
ENV OSTWIN_HOME=/root/.ostwin
ENV PATH="/root/.ostwin/.venv/bin:/root/.ostwin/.agents/bin:$PATH"

# Set the working directory
WORKDIR /app

# Install system dependencies required by the installer
# Node.js is required for building the frontend components
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    rsync \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project into the container
COPY . /app

# Run the official Agent OS installer
# --dashboard-only: excludes heavy CLI and background daemon components
# --yes: runs in non-interactive mode
# --dir: specifies the installation target directory
RUN bash .agents/install.sh --dashboard-only --yes --dir /root/.ostwin

# Ensure the .ostwin directory has the correct structure for the dashboard
RUN mkdir -p /root/.ostwin/dashboard

# Expose the default dashboard port
# Note: Cloud Run will override the actual listening port via the $PORT env var
EXPOSE 3366

# Start the dashboard using uvicorn from the installer's virtual environment
# We default to port 3366 but allow Cloud Run to override it via $PORT
CMD ["sh", "-c", "uvicorn dashboard.api:app --host 0.0.0.0 --port ${PORT:-3366}"]
