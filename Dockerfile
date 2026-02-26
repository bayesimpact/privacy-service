# Dockerfile for Privacy Service FastAPI Application
#
# Build args:
#   GPU=false (default) — installs the CPU-only torch wheel (from pytorch-cpu index,
#                         as pinned in the uv lockfile).
#   GPU=true            — after the frozen sync, reinstalls torch from the standard
#                         PyPI index, which ships CUDA support.
#                         Pair with an NVIDIA CUDA base image for actual GPU usage, e.g.:
#                         --build-arg BASE_IMAGE=nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04
#
# Example GPU build:
#   docker build --build-arg GPU=true --secret id=hf_token,env=HF_TOKEN -t privacy-service:gpu .

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

ARG GPU=false

RUN if [ "$GPU" = "true" ]; then \
    uv sync --no-dev --extra app --extra cu128; \
    else \
    uv sync --no-dev --extra app --extra cpu; \
    fi

RUN uv pip freeze

COPY scripts/ ./scripts/

# Download Hugging Face models at build time.
# Pass your token via:  docker build --secret id=hf_token,env=HF_TOKEN ...
RUN --mount=type=secret,id=hf_token \
    HF_TOKEN="$(cat /run/secrets/hf_token)" uv run --no-sync python scripts/preload_models.py

RUN --mount=type=secret,id=hf_token \
    HF_TOKEN=$(cat /run/secrets/hf_token) && \
    uv run python -c "\
    import huggingface_hub; \
    huggingface_hub.login(token='${HF_TOKEN}', new_session=False, add_to_git_credential=False)"
# Copy application code
COPY src/ ./src/
COPY app/ ./app/

RUN uv pip install .

# Copy config file if it exists (optional)
COPY config.yaml ./

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
# Prevent HuggingFace libraries from making network calls at runtime.
# All models are preloaded into the image cache during the build step above.
ENV HF_HUB_OFFLINE=1

# Run the FastAPI application
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

