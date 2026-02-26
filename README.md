## Privacy Service

**Privacy Service** is a Python library for **PII detection and anonymization** built on top of **Microsoft Presidio** and **ai4privacy**, with French-first defaults and support for custom regex-based patterns.

It exposes a simple `PrivacyService` class to detect and anonymize PII in strings, plus configuration helpers to control which recognizers and anonymization strategies are enabled.

---

## Installation

- **Python version**: **>= 3.10**

Install from source using `uv`:

```bash
uv sync --extra cpu
```

If you want to use GPUs:

```bash
uv sync --extra cu128
```

Then run:

```bash
uv pip install -e .
```

## Quick start

### Basic detection

```python
from privacy_service import PrivacyService

service = PrivacyService()  # Uses built-in defaults

text = "L'email de John Smith est john@example.com et son téléphone est +33 6 12 34 56 78."
detections = service.detect(text)

for det in detections:
    print(det.entity_type, det.text, det.start, det.end, f"score={det.score:.2f}")
```

### Basic anonymization

```python
from privacy_service import PrivacyService

service = PrivacyService()

text = "L'email de John Smith est john@example.com et son téléphone est +33 6 12 34 56 78."
result = service.anonymize(text)

print("Original:", result.original_text)
print("Anonymized:", result.text)

for item in result.items:
    print(
        f"{item.entity_type} [{item.start}:{item.end}] "
        f"'{item.text}' -> '{item.anonymized_text}' via {item.operator}"
    )
```

By default, the service:

- **Uses ai4privacy** (`use_ai4privacy=True`)
- **Keeps Presidio’s default recognizers** (`use_presidio_defaults=True`)
- **Uses spaCy NLP** with French and English large models
- Uses `replace` as the **default anonymization strategy**
- Assumes **French** (`language="fr"`) as the default language

---

## Configuration

Configuration is managed via the `PrivacyConfig` dataclass and helper functions in `privacy_service.core.config`.

You can configure the service in three ways:

- **Implicit defaults** (no config argument)
- **Dictionary** passed directly
- **YAML file** (recommended, using `config.example.yaml` as a template)

### Using a YAML config file

Copy `config.example.yaml` to `config.yaml` and adjust it to your needs:

```bash
cp config.example.yaml config.yaml
```

Then use:

```python
from privacy_service import PrivacyService

service = PrivacyService(config="config.yaml")
```

The example config controls:

- **Recognizers** (`recognizers` section)
  - `use_ai4privacy`: enable/disable ai4privacy recognizer
  - `use_presidio_defaults`: enable/disable Presidio’s built-in regex/statistical recognizers
  - `use_spacy_nlp`: enable/disable spaCy NLP engine
  - `spacy_nlp_model`: list of spaCy models to load, e.g.:

    ```yaml
    recognizers:
      use_spacy_nlp: true
      spacy_nlp_model:
        - lang_code: fr
          model_name: fr_core_news_lg
        - lang_code: en
          model_name: en_core_web_lg
    ```

  - `ai4privacy`:
    - `confidence_threshold`: float between 0.0 and 1.0
    - `classify_pii`: whether to map to specific entity types (`EMAIL_ADDRESS`, `PERSON`, …) or use a generic label

- **Anonymization** (`anonymization` section)
  - `default_strategy`: default Presidio operator name, e.g. `replace`, `mask`, `redact`, `hash`, `encrypt`, …
  - `strategies`: per-entity overrides, e.g.:

    ```yaml
    anonymization:
      default_strategy: replace
      strategies:
        EMAIL_ADDRESS: hash
        PHONE_NUMBER: mask
        PERSON: replace
        ORGANIZATION: replace
        LOCATION: replace
        CREDIT_CARD: redact
        US_SSN: redact
        IP_ADDRESS: hash
    ```

- **Custom regex patterns** (`custom_patterns` section)

  Example from `config.example.yaml`:

  ```yaml
  custom_patterns:
    - name: numero_benevole
      entity_type: NUMERO_BENEVOLE
      patterns:
        - "BEN-\\d{6}"
        - "BENEVOLE\\s+\\d{4}"
      score: 0.9
    - name: numero_dossier
      entity_type: NUMERO_DOSSIER
      patterns:
        - "DOS-\\d{4}-\\d{4}"
        - "DOSSIER[\\s-]\\d{6}"
      score: 0.9
  ```

  These are automatically registered as Presidio pattern recognizers by `PrivacyService._init_engines`.

- **Language**

  ```yaml
  language: fr
  ```

  This sets the default language for detection (`service.detect()` and `service.anonymize()`), and is also passed to the ai4privacy recognizer.

### Using a dictionary config

You can supply a Python `dict` instead of a YAML file:

```python
from privacy_service import PrivacyService

config = {
    "recognizers": {
        "use_ai4privacy": True,
        "use_presidio_defaults": True,
        "use_spacy_nlp": True,
        "ai4privacy": {
            "confidence_threshold": 0.01,
            "classify_pii": True,
        },
    },
    "anonymization": {
        "default_strategy": "replace",
        "strategies": {
            "EMAIL_ADDRESS": "hash",
            "PHONE_NUMBER": "mask",
        },
    },
    "custom_patterns": [],
    "language": "fr",
}

service = PrivacyService(config=config)
```

Behind the scenes this goes through `privacy_service.core.config.load_config` and `PrivacyConfig`.

### Default config lookup

If you pass `config=None` and do not specify a file, `PrivacyService` will load built-in defaults. The lower-level `get_default_config_path()` helper (used in CLI tooling) searches for a `config.yaml` in:

1. `./config.yaml`
2. `~/.privacy-service/config.yaml`
3. `/etc/privacy-service/config.yaml`

You can use `save_config` / `load_config` yourself:

```python
from privacy_service.core.config import load_config, save_config
from privacy_service.core.models import PrivacyConfig

cfg = load_config("config.yaml")
save_config(cfg, "config-out.yaml")
```

---

## Advanced usage

### Get supported entities and recognizers

```python
from privacy_service import PrivacyService

service = PrivacyService()

print("Entities:", service.get_supported_entities())
print("Recognizers:", service.get_recognizers())
```

### Adding a custom regex pattern at runtime

```python
from privacy_service import PrivacyService

service = PrivacyService()

service.add_custom_pattern(
    name="employee_id",
    patterns=[r"EMP-\\d{5}"],
    entity_type="EMPLOYEE_ID",
    score=0.9,
)
```

### Using the dataclasses directly

For some integrations, you may want to work with the result models defined in `privacy_service.core.models`:

- `DetectionResult`
- `AnonymizationResult`
- `AnonymizationItem`
- `FileDetectionResult`
- `FileAnonymizationResult`
- `PrivacyConfig`

All of these are standard `@dataclass` classes and work well with JSON serialization.

---

## Docker

The provided `Dockerfile` builds a self-contained image with the FastAPI service.
All heavy assets (spaCy models, HuggingFace models) are downloaded **at build time** and baked into the image.
At runtime the container has **no internet access** to HuggingFace (`HF_HUB_OFFLINE=1`).

### Prerequisites

#### 1. Docker with BuildKit enabled

BuildKit is required for the `--secret` flag used to pass the HuggingFace token without leaking it into the image layers.

```bash
# BuildKit is the default backend since Docker 23.
# If you are on an older version, enable it explicitly:
export DOCKER_BUILDKIT=1
```

#### 2. A Hugging Face account and access token

The `AP-HP/eds-pseudo-public` model is gated and requires authentication.

1. Create a free account at <https://huggingface.co>
2. Go to <https://huggingface.co/settings/tokens> and create a token with **read** access
3. Accept the model's terms of use at <https://huggingface.co/AP-HP/eds-pseudo-public>

Export the token in your shell:

```bash
export HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
```

#### 3. A `config.yaml` present at the repository root

The Dockerfile copies `config.yaml` into the image (see the `COPY config.yaml ./` step).
If you do not have one yet, create it from the example template:

```bash
cp config.example.yaml config.yaml
```

---

### Build

```bash
docker build \
  --secret id=hf_token,env=HF_TOKEN \
  -t privacy-service:latest \
  .
```

The build will:

1. Install all Python dependencies (including `app` group)
2. Download spaCy models `fr_core_news_lg` and `en_core_web_lg`
3. Log in to HuggingFace Hub and download:
   - `ai4privacy/llama-ai4privacy-multilingual-categorical-anonymiser-openpii`
   - `AP-HP/eds-pseudo-public`
4. Copy application code and `config.yaml`

The token is passed via a BuildKit secret and is **never written into any image layer**.

---

### Run

```bash
docker run --rm -p 8000:8000 privacy-service:latest
```

The API is then available at <http://localhost:8000>.

To mount a custom config at runtime instead of the one baked into the image:

```bash
docker run --rm -p 8000:8000 \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  privacy-service:latest
```

---

## Development

Clone the repository and set up the development environment (using `uv` groups defined in `pyproject.toml`):

```bash
make dev
```

Once dependencies are installed you can run:

- **Tests**:

  ```bash
  make test
  ```

- **Lint (ruff)**:

  ```bash
  make lint
  ```

- **Format (black)**:

  ```bash
  make format
  ```

- **Type-check (mypy)**:

  ```bash
  make type-check
  ```

To enable pre-commit hooks (see `.pre-commit-config.yaml`):

```bash
make pre-commit-install
```

To run all pre-commit checks on the whole codebase:

```bash
make pre-commit
```

With hooks installed, these checks will run automatically on each commit.

---

## License

This project is licensed under the **MIT License**. See `LICENSE` for details.

