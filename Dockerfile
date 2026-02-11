# Dockerfile for Privacy Service FastAPI Application

FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./ 

# Install Python dependencies including app group
# Install all dependencies first, then add app group
RUN uv sync --frozen
RUN uv sync --group app --frozen

RUN uv run python -m ensurepip

# Download spaCy models (French and English)
RUN uv run python -m spacy download fr_core_news_lg && \
    uv run python -m spacy download en_core_web_lg

# Copy application code
COPY src/ ./src/
COPY app/ ./app/

RUN uv pip install .

# Copy config file if it exists (optional)
COPY config.yaml* ./

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Run the FastAPI application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

