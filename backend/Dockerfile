# --- Builder Stage ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies - only what's needed for cloud backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3.11-dev \
    postgresql-client \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==2.1.3

# Copy project configuration
COPY pyproject.toml poetry.lock* /app/

# Install Python dependencies using Poetry
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi \
    && pip cache purge

# --- Final Runtime Stage ---
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed pip packages from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy the application source code
COPY . /app/

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8001

# Copy and set entrypoint
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Expose the port the application runs on
EXPOSE ${PORT}