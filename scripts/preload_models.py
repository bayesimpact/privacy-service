#!/usr/bin/env python3
"""Preload Hugging Face models during Docker build.

This script downloads and caches:
  - ai4privacy/llama-ai4privacy-multilingual-categorical-anonymiser-openpii
    (via the ai4privacy library's internal model runner)
  - AP-HP/eds-pseudo-public
    (via edsnlp, requires a Hugging Face token)

Usage:
    HF_TOKEN=<your_token> python scripts/preload_models.py
"""

import os
import sys


def login(token: str) -> None:
    """Login to Hugging Face Hub."""
    from huggingface_hub import login

    print("[preload] Logging in to Hugging Face Hub...")
    login(token=token)
    print("[preload] Login successful.")


def preload_ai4privacy() -> None:
    """Download the ai4privacy categorical model."""
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    model_name = (
        "ai4privacy/llama-ai4privacy-multilingual-categorical-anonymiser-openpii"
    )
    print(f"[preload] Downloading {model_name}...")
    AutoTokenizer.from_pretrained(model_name)
    AutoModelForTokenClassification.from_pretrained(model_name)
    print(f"[preload] {model_name} cached.")


def preload_edsnlp() -> None:
    """Download the AP-HP/eds-pseudo-public model via edsnlp."""
    import edsnlp

    model_name = "AP-HP/eds-pseudo-public"
    print(f"[preload] Downloading {model_name}...")
    edsnlp.load(model=model_name, auto_update=False)
    print(f"[preload] {model_name} cached.")


def main() -> None:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        print(
            "[preload] ERROR: HF_TOKEN environment variable is not set. "
            "It is required to download AP-HP/eds-pseudo-public.",
            file=sys.stderr,
        )
        sys.exit(1)

    login(token)
    preload_ai4privacy()
    preload_edsnlp()

    print("[preload] All models downloaded and cached successfully.")


if __name__ == "__main__":
    main()
