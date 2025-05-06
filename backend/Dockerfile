FROM python:3.11

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    postgresql-client \
    curl \
    git \
    # OCR and document processing dependencies
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libmagic1 \
    libreoffice \
    # Add additional dependencies for markdown processing
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry using pip
RUN python3 -m pip install poetry==1.8.2

# Install Node.js packages
RUN npm install -g npx
RUN npm install -g @modelcontextprotocol/server-filesystem@0.6.2
# Install Quickchart MCP Server
RUN npm install -g @gongrzhe/quickchart-mcp-server@1.0.4

# Copy only files necessary for poetry install first to leverage Docker cache
# Files are now expected in the build context (backend/)
COPY pyproject.toml poetry.lock* /app/

# Configure Poetry and update lock file
RUN poetry config virtualenvs.create false && \
    poetry lock --no-update && \
    poetry install --no-root --no-interaction --no-ansi

# Copy application code (after installing dependencies)
COPY . .

# Make the main entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Expose the application port
EXPOSE 8001

# Set entrypoint to run using Poetry's virtual environment
ENTRYPOINT ["poetry", "run", "/app/docker-entrypoint.sh"] 