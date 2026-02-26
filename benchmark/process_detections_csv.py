#!/usr/bin/env python3
"""Process detection CSV files to create word-level labeled dataframes.

This script takes a CSV file with detection results (like spacy_detections.csv)
and creates a dataframe with columns [word, gt_label, det_label, source_text]
where each row represents a word from the source text with its ground truth
and detected labels.
"""

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from datasets import load_dataset

# Add parent directory to path to import privacy_service
sys.path.insert(0, str(Path(__file__).parent.parent))

from privacy_service.recognizers.entity_mapping import map_ai4privacy_to_presidio


@dataclass
class Detection:
    """Simple detection object with required attributes."""

    entity_type: str
    start: int
    end: int
    score: float
    text: str
    recognizer: str = "unknown"


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


def pick_detection_for_token(
    token_start: int, token_end: int, detections: list[Detection]
) -> str:
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
    def is_contained(inner: Detection, outer: Detection) -> bool:
        return (
            outer.start <= inner.start
            and outer.end >= inner.end
            and (outer.start < inner.start or outer.end > inner.end)
        )

    pruned: list[Detection] = []
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


def label_tokens_for_row(
    text: str, privacy_mask: list[dict], detections: list[Detection]
) -> list[dict]:
    """Produce word-level ground truth and detected labels for a row."""
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


# def parse_privacy_mask(privacy_mask: list[dict]) -> list[dict]:
#     """Parse privacy_mask column from CSV (string representation of list).

#     Handles multi-line strings that may span multiple lines in the CSV.
#     """
#     re
#     if pd.isna(privacy_mask_str) or not privacy_mask_str:
#         return []

#     # Convert to string and strip whitespace/newlines from edges
#     privacy_mask_str = str(privacy_mask_str).strip()

#     # Handle empty list
#     if privacy_mask_str == "[]":
#         return []

#     try:
#         # Try parsing as Python literal (ast.literal_eval)
#         # This handles multi-line strings correctly
#         return ast.literal_eval(privacy_mask_str)
#     except (ValueError, SyntaxError) as e:
#         # Fallback: try JSON parsing (but privacy_mask is usually Python format)
#         try:
#             return json.loads(privacy_mask_str)
#         except json.JSONDecodeError:
#             # Try to fix common issues: remove leading/trailing whitespace
#             cleaned = privacy_mask_str.strip()
#             # If it starts with [ but might have issues, try to fix
#             if cleaned.startswith("[") and cleaned.endswith("]"):
#                 try:
#                     return ast.literal_eval(cleaned)
#                 except (ValueError, SyntaxError):
#                     pass
#             print(
#                 f"Warning: Could not parse privacy_mask (error: {e}): "
#                 f"{privacy_mask_str[:200]}"
#             )
#             return []


def parse_detected_entities(detected_entities_json: str) -> list[Detection]:
    """Parse detected_entities_json column from CSV."""
    if pd.isna(detected_entities_json) or not detected_entities_json:
        return []

    try:
        detections_list = json.loads(detected_entities_json)
        detections = []
        for d in detections_list:
            detections.append(
                Detection(
                    entity_type=d.get("entity_type", "UNKNOWN"),
                    start=d.get("start", 0),
                    end=d.get("end", 0),
                    score=d.get("score", 0.0),
                    text=d.get("text", ""),
                    recognizer=d.get("recognizer", "unknown"),
                )
            )
        return detections
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Warning: Could not parse detected_entities_json: {e}")
        return []


def process_csv_to_word_level(
    csv_path: Path,
    output_path: Path | None = None,
    split: str = "validation",
) -> pd.DataFrame:
    """Process CSV file to create word-level labeled dataframe.

    Args:
        csv_path: Path to input CSV file
        output_path: Optional path to save output CSV
        split: Dataset split to use ('train' or 'validation')

    Returns:
        DataFrame with columns: word, gt_label, det_label, source_text
    """
    print(f"Loading CSV from {csv_path}...")
    # Use quoting=csv.QUOTE_ALL and on_bad_lines='skip' to handle multi-line fields
    # The CSV has quoted fields that may contain newlines
    df = pd.read_csv(
        csv_path, quoting=csv.QUOTE_ALL, on_bad_lines="skip", engine="python"
    )

    print("Loading dataset from HuggingFace...")
    ds = load_dataset("ai4privacy/open-pii-masking-500k-ai4privacy")
    dataset_df = ds[split].to_pandas()
    french_dataset_df = dataset_df[dataset_df["language"] == "fr"]
    print(f"Loaded {len(french_dataset_df)} French rows from {split} split")

    # Join CSV with dataset on uid to get proper privacy_mask
    print("Joining CSV with dataset on uid...")
    df_joined = df.merge(
        french_dataset_df[["uid", "privacy_mask", "source_text"]],
        on="uid",
        how="inner",
        suffixes=("_csv", "_dataset"),
    )
    print(f"Joined {len(df_joined)} rows (matched on uid)")

    # Use source_text from dataset (more reliable)
    if "source_text_dataset" in df_joined.columns:
        df_joined["source_text"] = df_joined["source_text_dataset"]
    if "privacy_mask_dataset" in df_joined.columns:
        df_joined["privacy_mask"] = df_joined["privacy_mask_dataset"]

    print(f"Processing {len(df_joined)} rows...")
    all_rows = []
    for idx, row in df_joined.iterrows():
        if idx % 1000 == 0:
            print(f"  Processing row {idx}/{len(df_joined)}...")

        source_text = row["source_text"]
        # Use privacy_mask from dataset (already a list, not a string)
        privacy_mask = row["privacy_mask"]
        # Ensure privacy_mask is a list (handle None or empty cases)
        if privacy_mask is None or (
            isinstance(privacy_mask, float) and pd.isna(privacy_mask)
        ):
            privacy_mask = []

        detected_entities_json = row.get("detected_entities_json", "")

        # Parse detected entities
        detections = parse_detected_entities(detected_entities_json)

        # Label tokens
        labeled_tokens = label_tokens_for_row(source_text, privacy_mask, detections)

        # Add to results
        for tok in labeled_tokens:
            all_rows.append(
                {
                    "word": tok["text"],
                    "gt_label": tok["gt_label"],
                    "det_label": tok["det_label"],
                    "source_text": source_text,
                }
            )

    result_df = pd.DataFrame(all_rows)
    print(f"Created dataframe with {len(result_df)} word-level rows")

    if output_path:
        print(f"Saving to {output_path}...")
        result_df.to_csv(output_path, index=False, encoding="utf-8")
        print(f"Saved {len(result_df)} rows to {output_path}")

    return result_df


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Process detection CSV files to create word-level labeled dataframes"
        )
    )
    parser.add_argument(
        "input_csv",
        type=str,
        help="Input CSV file path (e.g., spacy_detections.csv)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Output CSV file path (default: input_csv with '_word_level' suffix)",
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
        help="Dataset split to use (default: validation)",
    )

    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist")
        sys.exit(1)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = input_path.parent / f"{input_path.stem}_word_level.csv"

    # Process CSV
    # Use quoting to properly handle multi-line fields
    df = pd.read_csv(input_path, engine="python")
    if args.max_rows:
        df = df.head(args.max_rows)
        print(f"Limiting to {args.max_rows} rows for testing")

    # Create temporary CSV if we limited rows
    if args.max_rows:
        temp_csv = input_path.parent / f"{input_path.stem}_temp_{args.max_rows}.csv"
        df.to_csv(temp_csv, index=False, encoding="utf-8", quoting=csv.QUOTE_ALL)
        input_path = temp_csv

    result_df = process_csv_to_word_level(input_path, output_path, split=args.split)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total words processed: {len(result_df)}")
    print("\nGround truth label distribution:")
    print(result_df["gt_label"].value_counts())
    print("\nDetected label distribution:")
    print(result_df["det_label"].value_counts())
    print("\nLabel agreement (gt_label == det_label):")
    agreement = (result_df["gt_label"] == result_df["det_label"]).sum()
    print(f"  {agreement}/{len(result_df)} ({100 * agreement / len(result_df):.2f}%)")


if __name__ == "__main__":
    main()
