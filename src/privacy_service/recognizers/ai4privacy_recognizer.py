"""AI4Privacy recognizer for Presidio.

Integrates the ai4privacy library as a Presidio recognizer for PII detection.
Supports both English and multilingual models.
"""

import warnings
from typing import Any

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from privacy_service.recognizers.entity_mapping import (
    AI4PRIVACY_TO_PRESIDIO_MAPPING,
    map_ai4privacy_to_presidio,
)


class AI4PrivacyRecognizer(EntityRecognizer):
    """Custom Presidio recognizer using ai4privacy library.

    This recognizer uses the ai4privacy library to detect PII entities.
    The ai4privacy library provides state-of-the-art PII detection using
    specialized language models.

    Supports both English and multilingual models:
    - English: ai4privacy/llama-ai4privacy-english-anonymiser-openpii (default)
    - Multilingual: 7 languages including French

    Attributes:
        confidence_threshold: Minimum confidence score for detections
        multilingual: Whether to use multilingual model
        classify_pii: Whether to classify PII types (vs generic PRIVATE label)
    """

    # Supported entities are the Presidio entity types that can be mapped
    PRESIDIO_SUPPORTED_ENTITIES = sorted(set(AI4PRIVACY_TO_PRESIDIO_MAPPING.values()))

    def __init__(
        self,
        model_name: str | None = None,  # Kept for compatibility but not used
        confidence_threshold: float = 0.01,
        device: str | None = None,  # Kept for compatibility but not used
        supported_entities: list[str] | None = None,
        language: str | None = "fr",
        classify_pii: bool = True,
    ):
        """Initialize AI4Privacy recognizer.

        Args:
            model_name: Ignored - kept for backward compatibility
            confidence_threshold: Minimum score for entity detection (0.0 to 1.0)
            device: Ignored - ai4privacy handles device selection automatically
            supported_entities: List of entity types to detect (None = all)
            language: Language to use for detection (None = auto-detect)
            classify_pii: Whether to classify PII types (True)
                or use generic labels (False)
        """
        self.confidence_threshold = confidence_threshold
        self.language = language or "fr"
        self.multilingual = self.language != "en"
        self.classify_pii = classify_pii

        # Set supported entities
        if supported_entities is None:
            supported_entities = self.PRESIDIO_SUPPORTED_ENTITIES

        supported_language = self.language

        super().__init__(
            supported_entities=supported_entities,
            name="AI4PrivacyRecognizer",
            supported_language=supported_language,
        )

    def load(self) -> None:
        """Load the recognizer."""
        pass

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        """Analyze text for PII entities using ai4privacy library.

        Uses the `observe` method which returns detection results without masking.

        Args:
            text: Text to analyze (English or multilingual based on config)
            entities: List of entity types to detect
            nlp_artifacts: NLP artifacts (not used by this recognizer)

        Returns:
            List of RecognizerResult objects with detected entities
        """

        # If text is empty, return empty results
        if not text or not text.strip():
            return []

        results = []

        try:
            # Import ai4privacy
            from ai4privacy import observe

            detection_result = observe(
                text,
                score_threshold=self.confidence_threshold,
                multilingual=self.multilingual,
                classify_pii=self.classify_pii,
                developer_verbose=False,
            )

            # Process detections from privacy_mask
            privacy_mask = detection_result.get("privacy_mask", [])

            for detection in privacy_mask:
                # Extract detection details
                entity_type_raw = detection.get("label", "PRIVATE")
                score = detection.get("activation", 0.0)
                start = detection.get("start", 0)
                end = detection.get("end", 0)
                value = detection.get("value", "")

                # Filter by confidence threshold
                if score < self.confidence_threshold:
                    continue

                # Map ai4privacy entity type to Presidio entity type
                entity_type = map_ai4privacy_to_presidio(entity_type_raw)

                # Filter by requested entities (if specified)
                if entities and entity_type not in entities:
                    continue

                # Create RecognizerResult
                result = RecognizerResult(
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    score=score,
                    recognition_metadata={
                        "recognizer_name": self.name,  # type: ignore[has-type]
                        "recognizer_identifier": self.id,
                        "original_entity": entity_type_raw,
                        "detected_value": value,
                        "multilingual": self.multilingual,
                        "classify_pii": self.classify_pii,
                    },
                )
                results.append(result)

        except Exception as e:
            warnings.warn(f"Error during ai4privacy analysis: {e}", stacklevel=2)
            return []

        return results

    def get_supported_entities(self) -> list[str]:
        """Get list of supported entity types.

        Returns:
            List of Presidio entity types that this recognizer can detect
        """
        return self.supported_entities

    def to_dict(self) -> dict[str, Any]:
        """Convert recognizer to dictionary representation.

        Returns:
            Dictionary with recognizer configuration
        """
        return {
            "recognizer_name": getattr(self, "name", "AI4PrivacyRecognizer"),
            "confidence_threshold": getattr(self, "confidence_threshold", 0.01),
            "multilingual": getattr(self, "multilingual", False),
            "classify_pii": getattr(self, "classify_pii", True),
            "supported_entities": getattr(self, "supported_entities", []),
            "is_loaded": getattr(self, "_is_loaded", False),
        }
