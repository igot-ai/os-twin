# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app"
ENV DASHBOARD_PORT=8080

# Set the working directory
WORKDIR /app

# Install system dependencies
# Git is required for some agent skills/logic
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy requirements file first to leverage Docker cache
COPY dashboard/requirements.txt /app/dashboard/requirements.txt
RUN pip install --no-cache-dir -r /app/dashboard/requirements.txt

# Copy the rest of the application code
COPY . /app

# Create the .ostwin directory in the home folder for logs/config
RUN mkdir -p /root/.ostwin/dashboard

# Expose the port (GCP Cloud Run will override this with the $PORT env var)
EXPOSE 8080

# Start the dashboard using uvicorn
# We use 'exec' to ensure the process receives signals correctly
CMD ["sh", "-c", "uvicorn dashboard.api:app --host 0.0.0.0 --port ${PORT:-8080}"]
