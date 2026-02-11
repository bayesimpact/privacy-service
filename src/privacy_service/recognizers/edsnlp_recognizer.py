"""EDS-NLP recognizer for Presidio.

Integrates the EDS-NLP library as a Presidio recognizer for PII detection.
Uses the AP-HP/eds-pseudo-public model for French medical text.
"""

import warnings
from typing import Any

from presidio_analyzer import EntityRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpArtifacts

from privacy_service.recognizers.entity_mapping import (
    EDS_NLP_TO_PRESIDIO_MAPPING,
    map_edsnlp_to_presidio,
)


class EDSNLPRecognizer(EntityRecognizer):
    """Custom Presidio recognizer using EDS-NLP library.

    This recognizer uses the EDS-NLP library to detect PII entities in French
    medical text. The EDS-NLP library provides specialized models for healthcare
    PII detection, particularly the AP-HP/eds-pseudo-public model.

    Supported entity types:
    - ADRESSE: Street address
    - DATE: Any absolute date other than a birthdate
    - DATE_NAISSANCE: Birthdate
    - HOPITAL: Hospital name
    - IPP: Internal AP-HP identifier for patients
    - MAIL: Email address
    - NDA: Internal AP-HP identifier for visits
    - NOM: Last name
    - PRENOM: First name
    - SECU: Social security number (French SSN)
    - TEL: Phone number
    - VILLE: City
    - ZIP: Zip code

    Attributes:
        model_name: Name of the EDS-NLP model to use
        confidence_threshold: Minimum confidence score for detections
        auto_update: Whether to auto-update the model
    """

    # Supported entities are the Presidio entity types that can be mapped
    PRESIDIO_SUPPORTED_ENTITIES = sorted(set(EDS_NLP_TO_PRESIDIO_MAPPING.values()))

    def __init__(
        self,
        model_name: str = "AP-HP/eds-pseudo-public",
        confidence_threshold: float = 0.5,
        auto_update: bool = True,
        supported_entities: list[str] | None = None,
        language: str | None = "fr",
    ):
        """Initialize EDS-NLP recognizer.

        Args:
            model_name: Name of the EDS-NLP model to use
                (default: "AP-HP/eds-pseudo-public")
            confidence_threshold: Minimum score for entity detection (0.0 to 1.0)
            auto_update: Whether to auto-update the model
            supported_entities: List of entity types to detect (None = all)
            language: Language to use for detection (default: "fr")
        """
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self.auto_update = auto_update
        self.language = language or "fr"

        # Set supported entities
        if supported_entities is None:
            supported_entities = self.PRESIDIO_SUPPORTED_ENTITIES

        supported_language = self.language

        # Initialize NLP pipeline (will be loaded in load() method)
        self._nlp = None

        super().__init__(
            supported_entities=supported_entities,
            name="EDSNLPRecognizer",
            supported_language=supported_language,
        )

    def load(self) -> None:
        """Load the EDS-NLP model."""
        if self._nlp is None:
            try:
                import edsnlp

                self._nlp = edsnlp.load(
                    model=self.model_name,  # type: ignore[arg-type]
                    auto_update=self.auto_update,  # type: ignore[arg-type]
                )
            except ImportError:
                warnings.warn(
                    "edsnlp library not installed. Install it with: pip install edsnlp",
                    stacklevel=2,
                )
                self._nlp = None
            except Exception as e:
                warnings.warn(
                    f"Error loading EDS-NLP model {self.model_name}: {e}",
                    stacklevel=2,
                )
                self._nlp = None

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
    ) -> list[RecognizerResult]:
        """Analyze text for PII entities using EDS-NLP library.

        Args:
            text: Text to analyze (French medical text)
            entities: List of entity types to detect
            nlp_artifacts: NLP artifacts (not used by this recognizer)

        Returns:
            List of RecognizerResult objects with detected entities
        """

        # If text is empty, return empty results
        if not text or not text.strip():
            return []

        # Ensure model is loaded
        if self._nlp is None:
            self.load()

        if self._nlp is None:
            warnings.warn(
                "EDS-NLP model not loaded. Cannot analyze text.",
                stacklevel=2,
            )
            return []

        results = []

        try:
            # Process text with EDS-NLP
            doc = self._nlp(text)

            # Extract entities from doc.ents
            for ent in doc.ents:
                # Get entity label
                entity_type_raw = ent.label_

                # Get entity text and positions
                entity_text = ent.text
                start = ent.start_char
                end = ent.end_char

                # Map EDS-NLP entity type to Presidio entity type
                entity_type = map_edsnlp_to_presidio(entity_type_raw)

                # Filter by requested entities (if specified)
                if entities and entity_type not in entities:
                    continue

                # Create RecognizerResult
                result = RecognizerResult(
                    entity_type=entity_type,
                    start=start,
                    end=end,
                    score=0.85,
                    recognition_metadata={
                        "recognizer_name": self.name,
                        "recognizer_identifier": self.id,
                        "original_entity": entity_type_raw,
                        "detected_value": entity_text,
                        "model_name": self.model_name,
                    },
                )
                results.append(result)

        except Exception as e:
            warnings.warn(f"Error during EDS-NLP analysis: {e}", stacklevel=2)
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
            "recognizer_name": getattr(self, "name", "EDSNLPRecognizer"),
            "model_name": getattr(self, "model_name", "AP-HP/eds-pseudo-public"),
            "confidence_threshold": getattr(self, "confidence_threshold", 0.5),
            "auto_update": getattr(self, "auto_update", True),
            "supported_entities": getattr(self, "supported_entities", []),
            "is_loaded": self._nlp is not None,
        }
