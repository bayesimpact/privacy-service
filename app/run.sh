#!/bin/bash
# Script to run the FastAPI application locally

# Activate uv environment and run uvicorn
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload


