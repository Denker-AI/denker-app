# --- Builder Stage ---
FROM python:3.11 AS builder

WORKDIR /app

# Install system dependencies - with proper cleanup in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3.11-dev \
    nodejs \
    npm \
    ffmpeg \
    git \
    postgresql-client \
    libpq-dev \
    curl \
    # OCR and document processing BUILD dependencies
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    default-jre \
    libreoffice \
    # Add additional dependencies for markdown processing
    pandoc \
    wkhtmltopdf \
    xvfb \
    # Cleanup in the same layer to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install npm dependencies
RUN npm install -g @gongrzhe/quickchart-mcp-server@1.0.4
RUN npm install -g @modelcontextprotocol/server-filesystem@0.6.2

# Install Poetry
RUN pip install poetry==2.1.3

# Explicitly install CPU-only PyTorch first to prevent CUDA downloads
# Use pip to install the CPU-only version and prevent large CUDA package downloads
RUN pip install torch==2.7.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --no-cache-dir

# Copy project configuration
COPY pyproject.toml poetry.lock* /app/

# Install Python dependencies using Poetry - with proper options
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --no-interaction --no-ansi \
    # Cleanup pip cache in the same layer
    && pip cache purge

# --- Final Runtime Stage ---
FROM python:3.11

WORKDIR /app

# Install runtime dependencies in a single layer with proper cleanup
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    # OCR and document processing RUNTIME dependencies
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    default-jre \
    libreoffice \
    pandoc \
    wkhtmltopdf \
    xvfb \
    # Node.js runtime if needed for the globally installed npm packages
    nodejs \
    # Cleanup in the same layer to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the installed pip packages from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy the installed npm global packages from the builder stage
COPY --from=builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=builder /usr/local/bin /usr/local/bin

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

# Run as a non-root user for better security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser