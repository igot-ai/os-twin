# Use a slim Python 3.11 base image
FROM python:3.11-slim

# Force the installer to use /root/.ostwin instead of assuming $HOME
ENV OSTWIN_HOME=/root/.ostwin
ENV PATH="/root/.ostwin/.venv/bin:/root/.ostwin/.agents/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LARK_WEBHOOK_URL ""

# Set the working directory
WORKDIR /app

# 1. Install System Dependencies
# Includes nodejs for frontend builds and rsync for the installer
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    git \
    rsync \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2. Setup OSTwin Home & Virtual Environment
RUN mkdir -p /root/.ostwin \
    && python -m venv /root/.ostwin/.venv

# 3. Cache Heavy Python Dependencies (Torch CPU)
# Explicitly installing CPU version saves 1.5GB of image size and download time
RUN /root/.ostwin/.venv/bin/pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 4. Install other heavy dependencies
COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN /root/.ostwin/.venv/bin/pip install --no-cache-dir -r /app/dashboard/requirements.txt

# 5. Cache Node Dependencies (Frontend)
COPY dashboard/fe/package.json /app/dashboard/fe/package.json
RUN cd /app/dashboard/fe && npm install

# 6. Build Frontend
COPY dashboard/fe /app/dashboard/fe
RUN cd /app/dashboard/fe && npm run build

# 7. Copy remaining source
COPY . /app

# 8. Run Installer (Skip heavy steps already handled in layers)
# The installer supports --yes to skip prompts
RUN bash .agents/install.sh --dashboard-only --yes --dir /root/.ostwin

# Expose the default port (Cloud Run will override this via $PORT)
EXPOSE 3366

# Start the dashboard using the virtual environment
# Respect the PORT environment variable injected by Cloud Run
CMD ["sh", "-c", "uvicorn dashboard.api:app --host 0.0.0.0 --port ${PORT:-3366}"]
