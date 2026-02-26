# Benchmark Scripts

## benchmark_open_pii.py

Benchmark script for evaluating PrivacyService on the Open PII Masking 500k dataset.

### Usage

```bash
# Run all configurations (default)
python scripts/benchmark_open_pii.py

# Run specific configurations only
python scripts/benchmark_open_pii.py --configs spacy ai4privacy edsnlp

# Limit number of rows for quick testing
python scripts/benchmark_open_pii.py --max-rows 100

# Use training split instead of validation
python scripts/benchmark_open_pii.py --split train

# Specify output file
python scripts/benchmark_open_pii.py --output my_results.json

# Specify output directory for CSV files
python scripts/benchmark_open_pii.py --output-dir ./results
```

### Available Configurations

- `spacy`: Only Presidio default recognizers (with spaCy NLP)
- `ai4privacy`: Only AI4Privacy recognizer
- `edsnlp`: Only EDS-NLP recognizer
- `spacy+ai4privacy`: Presidio defaults + AI4Privacy
- `spacy+edsnlp`: Presidio defaults + EDS-NLP
- `ai4privacy+edsnlp`: AI4Privacy + EDS-NLP
- `all`: All three together

### Output

The script generates two types of output:

1. **JSON file** (`--output`): Detailed metrics for each configuration:
   - Entity-aware metrics: TP if ground truth entity type matches detected entity type
   - Entity-unaware metrics: TP if ground truth is an entity and any entity is detected
   - Each configuration includes:
     - List of loaded recognizers
     - Number of rows processed
     - Per-entity metrics (precision, recall, F1) for both evaluation modes

2. **CSV files** (`--output-dir`): One CSV file per configuration containing:
   - All original dataset columns (`source_text`, `masked_text`, `privacy_mask`, etc.)
   - `detected_entities_json`: JSON string with full detection details (entity_type, start, end, score, text, recognizer)
   - `detected_entities_str`: Human-readable string representation of detections
   - Files are named `{config_name}_detections.csv` (e.g., `spacy_detections.csv`, `all_detections.csv`)

### Example Output

```json
[
  {
    "config_name": "spacy",
    "recognizers": ["CryptoRecognizer", "DateRecognizer", ...],
    "num_rows": 22466,
    "entity_aware": [
      {
        "entity_type": "EMAIL_ADDRESS",
        "tp": 14138,
        "fp": 1686,
        "fn": 196,
        "precision": 0.8934,
        "recall": 0.9863,
        "f1": 0.9376
      },
      ...
    ],
    "entity_unaware": [...]
  },
  ...
]
```

