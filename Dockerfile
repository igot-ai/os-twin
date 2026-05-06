# Use a pinned stable image (Bookworm) to avoid "Testing" distribution (Trixie) policy changes
FROM python:3.11-slim-bookworm

# Force the installer to use /root/.ostwin instead of assuming $HOME
ENV OSTWIN_HOME=/root/.ostwin
ENV PATH="/root/.local/bin:/root/.cargo/bin:/root/.ostwin/.venv/bin:/root/.ostwin/.agents/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LARK_WEBHOOK_URL ""

# Set the working directory
WORKDIR /app

# 1. Install System Dependencies
# Includes nodejs 20.x and PowerShell 7.4.x
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    rsync \
    wget \
    ca-certificates \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update \
    && apt-get install -y nodejs \
    # Install PowerShell directly from Microsoft (Stable)
    && wget -q -O /tmp/powershell.deb https://github.com/PowerShell/PowerShell/releases/download/v7.4.2/powershell_7.4.2-1.deb_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/powershell.deb \
    && rm -f /tmp/powershell.deb \
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
# The installer supports --yes to skip prompts
RUN bash .agents/install.sh --yes --dir /root/.ostwin

# Expose the default port (Cloud Run will override this via $PORT)
EXPOSE 3366

# Start the dashboard using the virtual environment
# Respect the PORT environment variable injected by Cloud Run
CMD ["sh", "-c", "uvicorn dashboard.api:app --host 0.0.0.0 --port ${PORT:-3366}"]
