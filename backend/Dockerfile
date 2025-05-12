# --- Builder Stage ---
FROM python:3.11 AS builder

WORKDIR /app

# Install system dependencies - with proper cleanup in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
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
    # Cleanup in the same layer to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install npm dependencies
RUN npm install -g @gongrzhe/quickchart-mcp-server@1.0.4

# Copy project configuration
COPY pyproject.toml poetry.lock* /app/

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Explicitly install CPU-only PyTorch first to prevent CUDA downloads
# Use pip to install the CPU-only version and prevent large CUDA package downloads
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu --no-cache-dir

# Install critical cryptography packages first to prevent pycrypto
RUN pip install cryptography>=3.4.0 pycryptodome>=3.20.0

# Install Python dependencies using Poetry - with proper options
RUN $HOME/.local/bin/poetry config virtualenvs.create false \
    && $HOME/.local/bin/poetry install --no-root --no-interaction --no-ansi \
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

# Start the application with PORT from environment variable
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} 