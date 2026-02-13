#!/usr/bin/env python3
"""Benchmark script for Open PII Masking 500k dataset.

This script evaluates different recognizer combinations on the French subset
of the ai4privacy/open-pii-masking-500k-ai4privacy dataset.

Recognizer combinations tested:
- Only spacy (Presidio defaults)
- Only ai4privacy
- Only edsnlp
- spacy + ai4privacy
- spacy + edsnlp
- ai4privacy + edsnlp
- All three together
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset

# Add parent directory to path to import privacy_service
sys.path.insert(0, str(Path(__file__).parent.parent))

from privacy_service import PrivacyService
from privacy_service.core.config import load_config
from privacy_service.core.models import PrivacyConfig
from privacy_service.recognizers.entity_mapping import map_ai4privacy_to_presidio


def tokenize_with_spans(text: str) -> list[dict]:
    """Split text into tokens with character spans."""
    tokens: list[dict] = []
    for m in re.finditer(r"\w+|\S", text):
        tokens.append({"text": m.group(0), "start": m.start(), "end": m.end()})
    return tokens


def map_gt_label_to_common(label: str) -> str:
    """Map HuggingFace ground-truth label to a common entity space."""
    return map_ai4privacy_to_presidio(label)


def map_detected_to_common(entity_type: str) -> str:
    """Map PrivacyService entity type to the same common entity space."""
    return entity_type


def pick_detection_for_token(token_start: int, token_end: int, detections) -> str:
    """Choose a single detected entity type for a token."""
    # Collect overlapping detections
    overlapping = [
        d for d in detections if not (d.end <= token_start or d.start >= token_end)
    ]

    if not overlapping:
        return "O"

    if len(overlapping) == 1:
        return map_detected_to_common(overlapping[0].entity_type)

    # Eliminate detections that are strictly contained in another
    def is_contained(inner, outer) -> bool:
        return (
            outer.start <= inner.start
            and outer.end >= inner.end
            and (outer.start < inner.start or outer.end > inner.end)
        )

    pruned: list = []
    for d in overlapping:
        contained = any(
            is_contained(d, other) for other in overlapping if other is not d
        )
        if not contained:
            pruned.append(d)

    if not pruned:
        pruned = overlapping

    # Pick highest scoring detection
    best = max(pruned, key=lambda d: d.score)
    return map_detected_to_common(best.entity_type)


def label_tokens_for_row(row: pd.Series) -> list[dict]:
    """Produce word-level ground truth and detected labels for a row."""
    text: str = row["source_text"]
    privacy_mask = row["privacy_mask"]
    detections = row["detected_entities"]

    tokens = tokenize_with_spans(text)

    # Pre-compute ground-truth spans in common space
    gt_spans: list[dict] = []
    for item in privacy_mask:
        gt_spans.append(
            {
                "start": item["start"],
                "end": item["end"],
                "label": map_gt_label_to_common(item["label"]),
            }
        )

    labeled_tokens: list[dict] = []
    for tok in tokens:
        t_start, t_end = tok["start"], tok["end"]

        # Ground-truth label for this token
        gt_label = "O"
        for gt in gt_spans:
            if t_start >= gt["start"] and t_end <= gt["end"]:
                gt_label = gt["label"]
                break

        # Detected label for this token
        det_label = pick_detection_for_token(t_start, t_end, detections)

        labeled_tokens.append(
            {
                "text": tok["text"],
                "start": t_start,
                "end": t_end,
                "gt_label": gt_label,
                "det_label": det_label,
            }
        )

    return labeled_tokens


def compute_entity_aware_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute entity-aware metrics: TP if gt_label == E and det_label == E."""
    entity_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )

    for _, row in df.iterrows():
        labeled_tokens = label_tokens_for_row(row)
        for tok in labeled_tokens:
            gt = tok["gt_label"]
            det = tok["det_label"]

            if gt == det and gt != "O":
                entity_counts[gt]["tp"] += 1
            elif gt != "O" and det != gt:
                entity_counts[gt]["fn"] += 1
            elif det != "O" and gt != det:
                entity_counts[det]["fp"] += 1

    # Build metrics DataFrame
    rows = []
    for ent, c in entity_counts.items():
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        rows.append(
            {
                "entity_type": ent,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": prec,
                "recall": rec,
                "f1": f1,
            }
        )

    return pd.DataFrame(rows).sort_values("f1", ascending=False)


def compute_entity_unaware_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute entity-unaware metrics: TP if gt_label == E and det_label != 'O'."""
    entity_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )

    for _, row in df.iterrows():
        labeled_tokens = label_tokens_for_row(row)
        for tok in labeled_tokens:
            gt = tok["gt_label"]
            det = tok["det_label"]

            # Ground truth-driven counts (TP/FN)
            if gt != "O":
                if det != "O":
                    # Any detection on a token whose GT is E counts as TP_E
                    entity_counts[gt]["tp"] += 1
                else:
                    # No detection on a token whose GT is E → FN_E
                    entity_counts[gt]["fn"] += 1

            # Detection-driven counts (FP)
            if det != "O" and gt == "O":
                # Detection of E while GT is O → FP_E
                entity_counts[det]["fp"] += 1

    # Build metrics DataFrame
    rows = []
    for ent, c in entity_counts.items():
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        rows.append(
            {
                "entity_type": ent,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": prec,
                "recall": rec,
                "f1": f1,
            }
        )

    return pd.DataFrame(rows).sort_values("f1", ascending=False)


def create_config(
    use_spacy: bool = False,
    use_ai4privacy: bool = False,
    use_edsnlp: bool = False,
) -> PrivacyConfig:
    """Create a PrivacyConfig with specified recognizers enabled."""
    config = load_config("config.benchmark.yaml")
    if use_spacy:
        config.use_spacy_nlp = True
    if use_ai4privacy:
        config.use_ai4privacy = True
    if use_edsnlp:
        config.use_edsnlp = True
    return config


def run_benchmark(
    df: pd.DataFrame,
    config_name: str,
    config: PrivacyConfig,
    max_rows: int | None = None,
    output_dir: Path | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Run benchmark with a specific configuration.

    Returns:
        Tuple of (results_dict, dataframe_with_detections)
    """
    print(f"\n{'=' * 60}")
    print(f"Running benchmark: {config_name}")
    print(f"{'=' * 60}")

    # Limit rows if specified
    test_df = df.head(max_rows) if max_rows else df
    print(f"Processing {len(test_df)} rows...")

    # Initialize service
    print("Initializing PrivacyService...")
    service = PrivacyService(config=config)
    print(f"Loaded recognizers: {service.get_recognizers()}")

    # Run detection
    print("Running detection...")
    test_df = test_df.copy()
    test_df["detected_entities"] = test_df["source_text"].apply(
        lambda x: service.detect(x)
    )

    # Save dataframe immediately after detection (before metrics computation)
    if output_dir is not None:
        print("Saving dataframe after detection...")
        # Convert DetectionResult objects to JSON strings for CSV storage
        df_after_detection = test_df.copy()

        def detections_to_json(detections):
            """Convert list of DetectionResult objects to JSON string."""
            if not detections:
                return "[]"
            detections_dict = [
                {
                    "entity_type": d.entity_type,
                    "start": d.start,
                    "end": d.end,
                    "score": d.score,
                    "text": d.text,
                    "recognizer": d.recognizer,
                }
                for d in detections
            ]
            return json.dumps(detections_dict, ensure_ascii=False)

        def detections_to_string(detections):
            """Convert list of DetectionResult objects to readable string."""
            if not detections:
                return ""
            return "; ".join(
                [
                    f"{d.entity_type}({d.text[:30]}{'...' if len(d.text) > 30 else ''})"
                    for d in detections
                ]
            )

        df_after_detection["detected_entities_json"] = df_after_detection[
            "detected_entities"
        ].apply(detections_to_json)
        df_after_detection["detected_entities_str"] = df_after_detection[
            "detected_entities"
        ].apply(detections_to_string)

        csv_path = output_dir / f"{config_name}_detections.csv"
        df_after_detection.drop(columns=["detected_entities"]).to_csv(
            csv_path, index=False, encoding="utf-8"
        )
        print(f"  Saved {csv_path} ({len(df_after_detection)} rows)")

    # Compute metrics
    print("Computing entity-aware metrics...")
    entity_aware_metrics = compute_entity_aware_metrics(test_df)

    print("Computing entity-unaware metrics...")
    entity_unaware_metrics = compute_entity_unaware_metrics(test_df)

    result = {
        "config_name": config_name,
        "recognizers": service.get_recognizers(),
        "num_rows": len(test_df),
        "entity_aware": entity_aware_metrics.to_dict("records"),
        "entity_unaware": entity_unaware_metrics.to_dict("records"),
    }

    return result, test_df


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark PrivacyService on Open PII Masking 500k dataset"
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Maximum number of rows to process (for testing)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="validation",
        choices=["train", "validation"],
        help="Dataset split to use",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_results.json",
        help="Output JSON file for results",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory to save CSV files with detections",
    )
    parser.add_argument(
        "--configs",
        nargs="+",
        choices=[
            "spacy",
            "ai4privacy",
            "edsnlp",
            "spacy+ai4privacy",
            "spacy+edsnlp",
            "ai4privacy+edsnlp",
            "all",
        ],
        default=[
            "spacy",
            "ai4privacy",
            "edsnlp",
            "spacy+ai4privacy",
            "spacy+edsnlp",
            "ai4privacy+edsnlp",
            "all",
        ],
        help="Which configurations to run",
    )

    args = parser.parse_args()

    # Load dataset
    print("Loading dataset...")
    ds = load_dataset("ai4privacy/open-pii-masking-500k-ai4privacy")
    test_df = ds[args.split].to_pandas()
    french_test_df = test_df[test_df["language"] == "fr"]
    print(f"Loaded {len(french_test_df)} French rows from {args.split} split")

    # Define configurations
    configs = {
        "spacy": create_config(use_spacy=True),
        "ai4privacy": create_config(use_ai4privacy=True),
        "edsnlp": create_config(use_edsnlp=True),
        "spacy+ai4privacy": create_config(use_spacy=True, use_ai4privacy=True),
        "spacy+edsnlp": create_config(use_spacy=True, use_edsnlp=True),
        "ai4privacy+edsnlp": create_config(use_ai4privacy=True, use_edsnlp=True),
        "all": create_config(use_spacy=True, use_ai4privacy=True, use_edsnlp=True),
    }

    # Create output directory if it doesn't exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run benchmarks
    results = []
    dataframes = {}
    for config_name in args.configs:
        if config_name not in configs:
            print(f"Warning: Unknown configuration '{config_name}', skipping")
            continue

        try:
            result, df_with_detections = run_benchmark(
                french_test_df,
                config_name,
                configs[config_name],
                max_rows=args.max_rows,
                output_dir=output_dir,
            )
            results.append(result)
            dataframes[config_name] = df_with_detections
        except Exception as e:
            print(f"Error running benchmark '{config_name}': {e}")
            import traceback

            traceback.print_exc()

    # Save results
    output_path = Path(args.output)
    print(f"\n{'=' * 60}")
    print(f"Saving results to {output_path}")
    print(f"{'=' * 60}")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # CSV files are already saved during benchmark execution
    # (right after detection, before metrics computation)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for result in results:
        print(f"\n{result['config_name']}:")
        print(f"  Recognizers: {', '.join(result['recognizers'])}")
        print(f"  Rows processed: {result['num_rows']}")
        print("\n  Entity-aware metrics (top 5 by F1):")
        entity_aware_df = pd.DataFrame(result["entity_aware"])
        for _, row in entity_aware_df.head(5).iterrows():
            print(
                f"    {row['entity_type']:20s} "
                f"P:{row['precision']:.4f} R:{row['recall']:.4f} F1:{row['f1']:.4f}"
            )
        print("\n  Entity-unaware metrics (top 5 by F1):")
        entity_unaware_df = pd.DataFrame(result["entity_unaware"])
        for _, row in entity_unaware_df.head(5).iterrows():
            print(
                f"    {row['entity_type']:20s} "
                f"P:{row['precision']:.4f} R:{row['recall']:.4f} F1:{row['f1']:.4f}"
            )

    print(f"\nFull results saved to {output_path}")
    print(f"CSV files saved to {output_dir}")


if __name__ == "__main__":
    main()
