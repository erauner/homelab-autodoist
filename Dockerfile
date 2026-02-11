FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/erauner/homelab-autodoist"
LABEL org.opencontainers.image.description="Autodoist - GTD automation for Todoist"

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY autodoist.py ./

# Run as non-root user
RUN useradd -r -u 1000 autodoist
USER autodoist

ENTRYPOINT ["python", "autodoist.py"]
