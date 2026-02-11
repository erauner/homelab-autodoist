FROM python:3.11-slim

LABEL org.opencontainers.image.source="https://github.com/erauner/homelab-autodoist"
LABEL org.opencontainers.image.description="Autodoist - GTD automation for Todoist"

# Create non-root user first
RUN useradd -r -u 1000 -m autodoist

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application package and set ownership
COPY --chown=autodoist:autodoist autodoist/ ./autodoist/
COPY --chown=autodoist:autodoist setup.py ./

# Create writable directory for logs and database
RUN mkdir -p /app/data && chown autodoist:autodoist /app/data

USER autodoist
WORKDIR /app/data

ENTRYPOINT ["python", "-m", "autodoist"]
