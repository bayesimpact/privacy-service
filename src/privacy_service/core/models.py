"""Data models for Privacy Service."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DetectionResult:
    """Result from PII detection.

    Attributes:
        entity_type: Type of PII entity (e.g., PERSON, EMAIL, SSN)
        start: Start position in text
        end: End position in text
        score: Confidence score (0.0 to 1.0)
        text: The actual PII text detected
        recognizer: Name of the recognizer that detected this entity
    """

    entity_type: str
    start: int
    end: int
    score: float
    text: str
    recognizer: str = "unknown"

    def __repr__(self) -> str:
        return (
            f"DetectionResult(entity_type='{self.entity_type}', "
            f"text='{self.text}', start={self.start}, end={self.end}, "
            f"score={self.score:.2f})"
        )


@dataclass
class AnonymizationResult:
    """Result from PII anonymization.

    Attributes:
        text: Anonymized text with PII replaced/redacted
        items: List of anonymization operations performed
        original_text: Original text before anonymization (optional)
    """

    text: str
    items: list["AnonymizationItem"] = field(default_factory=list)
    original_text: str | None = None

    def __repr__(self) -> str:
        return (
            f"AnonymizationResult(text='{self.text[:50]}...', "
            f"items_count={len(self.items)})"
        )


@dataclass
class AnonymizationItem:
    """Details of a single anonymization operation.

    Attributes:
        entity_type: Type of entity anonymized
        start: Original start position
        end: Original end position
        text: Original text before anonymization
        operator: Anonymization operator used
        anonymized_text: Replacement text
    """

    entity_type: str
    start: int
    end: int
    text: str
    operator: str
    anonymized_text: str


@dataclass
class ProcessedContent:
    """Content extracted from a file for processing.

    Attributes:
        text: Extracted text content
        metadata: Additional metadata (encoding, format-specific info)
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FileDetectionResult:
    """Result from detecting PII in a file.

    Attributes:
        file_path: Path to the file processed
        detections: List of PII detections found
        file_type: Type of file processed
        metadata: Additional metadata about processing
    """

    file_path: str
    detections: list[DetectionResult]
    file_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "file_type": self.file_type,
            "detections_count": len(self.detections),
            "detections": [
                {
                    "entity_type": d.entity_type,
                    "text": d.text,
                    "start": d.start,
                    "end": d.end,
                    "score": d.score,
                    "recognizer": d.recognizer,
                }
                for d in self.detections
            ],
            "metadata": self.metadata,
        }


@dataclass
class FileAnonymizationResult:
    """Result from anonymizing PII in a file.

    Attributes:
        input_path: Path to input file
        output_path: Path to output file
        anonymizations_count: Number of anonymizations performed
        file_type: Type of file processed
        success: Whether anonymization succeeded
        error: Error message if failed
    """

    input_path: str
    output_path: str
    anonymizations_count: int
    file_type: str
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_path": self.input_path,
            "output_path": self.output_path,
            "anonymizations_count": self.anonymizations_count,
            "file_type": self.file_type,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class PrivacyConfig:
    """Configuration for Privacy Service.

    Attributes:
        use_ai4privacy: Whether to use ai4privacy library for PII detection
        use_edsnlp: Whether to use EDS-NLP library for PII detection
        use_presidio_defaults: Whether to use Presidio default recognizers
        ai4privacy_confidence_threshold: Confidence threshold for ai4privacy
        ai4privacy_classify_pii: Whether to classify PII types or use generic labels
        edsnlp_model_name: Name of the EDS-NLP model to use
        edsnlp_confidence_threshold: Confidence threshold for EDS-NLP
        edsnlp_auto_update: Whether to auto-update the EDS-NLP model
        use_spacy_nlp: Whether to enable spaCy-based NLP in Presidio
        spacy_nlp_models: List of spaCy models (lang_code/model_name) to load
        default_anonymization_strategy: Default anonymization strategy
        entity_strategies: Per-entity anonymization strategies
        custom_patterns: Custom regex patterns for PII detection
        language: Default language for detection
    """

    use_ai4privacy: bool = True
    use_edsnlp: bool = False
    use_presidio_defaults: bool = True
    use_spacy_nlp: bool = True
    ai4privacy_confidence_threshold: float = 0.01
    ai4privacy_classify_pii: bool = True
    edsnlp_model_name: str = "AP-HP/eds-pseudo-public"
    edsnlp_confidence_threshold: float = 0.5
    edsnlp_auto_update: bool = True
    # By défaut, on privilégie un modèle français, avec un modèle anglais disponible.
    spacy_nlp_models: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"lang_code": "fr", "model_name": "fr_core_news_lg"},
            {"lang_code": "en", "model_name": "en_core_web_lg"},
        ]
    )
    default_anonymization_strategy: str = "replace"
    entity_strategies: dict[str, str] = field(default_factory=dict)
    custom_patterns: list[dict[str, Any]] = field(default_factory=list)
    language: str = "fr"
