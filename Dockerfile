# Use a slim Python 3.11 base image
FROM python:3.11-slim

# Force the installer to use /root/.ostwin instead of assuming $HOME
ENV OSTWIN_HOME=/root/.ostwin
ENV PATH="/root/.local/bin:/root/.cargo/bin:/root/.ostwin/.venv/bin:/root/.ostwin/.agents/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LARK_WEBHOOK_URL ""

# Set the working directory
WORKDIR /app

# 1. Install System Dependencies & PowerShell (pwsh)
# Includes nodejs for frontend builds and rsync for the installer
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    rsync \
    wget \
    apt-transport-https \
    software-properties-common \
    build-essential \
    && wget -q https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get install -y powershell nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Install OpenCode CLI
RUN curl -fsSL https://opencode.ai/install | bash

# 3. Setup OSTwin Home & Virtual Environment
RUN mkdir -p /root/.ostwin \
    && python -m venv /root/.ostwin/.venv

# 4. Cache Heavy Python Dependencies (Torch CPU)
# Explicitly installing CPU version saves 1.5GB of image size and download time
RUN /root/.ostwin/.venv/bin/pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 5. Install other heavy dependencies
COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN /root/.ostwin/.venv/bin/pip install --no-cache-dir -r /app/dashboard/requirements.txt

# 6. Cache Node Dependencies (Frontend)
COPY dashboard/fe/package.json /app/dashboard/fe/package.json
RUN cd /app/dashboard/fe && npm install

# 7. Build Frontend
COPY dashboard/fe /app/dashboard/fe
RUN cd /app/dashboard/fe && npm run build

# 8. Copy remaining source
COPY . /app

# 9. Run Installer (Full install to enable agent orchestration)
# Removed --dashboard-only to ensure opencode/mcp/agents are correctly synced
RUN bash .agents/install.sh --yes --dir /root/.ostwin

# Expose the default port (Cloud Run will override this via $PORT)
EXPOSE 3366

# Start the dashboard using the virtual environment
# Respect the PORT environment variable injected by Cloud Run
CMD ["sh", "-c", "uvicorn dashboard.api:app --host 0.0.0.0 --port ${PORT:-3366}"]
