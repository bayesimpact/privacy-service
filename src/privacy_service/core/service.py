"""Main Privacy Service class."""

from pathlib import Path
from typing import Any

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerRegistry,
)
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.operators import OperatorsFactory

from privacy_service.core.config import load_config, validate_config
from privacy_service.core.models import (
    AnonymizationItem,
    AnonymizationResult,
    DetectionResult,
    PrivacyConfig,
)


class PrivacyService:
    """Main service for PII detection and anonymization.

    This class orchestrates Presidio's AnalyzerEngine and AnonymizerEngine,
    along with custom recognizers like AI4Privacy and EDS-NLP.

    Example:
        >>> service = PrivacyService()
        >>> results = service.detect("My SSN is 123-45-6789")
        >>> anonymized = service.anonymize("My SSN is 123-45-6789", strategy="redact")
    """

    def __init__(
        self, config: str | Path | dict[str, Any] | PrivacyConfig | None = None
    ):
        """Initialize Privacy Service.

        Args:
            config: Configuration source. Can be:
                - Path to YAML config file (e.g., "config.yaml")
                - Dictionary with config values
                - PrivacyConfig object
                - None to use defaults

        Example:
            >>> # Use default configuration
            >>> service = PrivacyService()
            >>>
            >>> # Load from YAML file (see config.example.yaml for template)
            >>> service = PrivacyService(config="config.yaml")
            >>>
            >>> # Use dictionary configuration
            >>> config = {
            ...     "recognizers": {
            ...         "use_ai4privacy": True
            ...     }
            ... }
            >>> service = PrivacyService(config=config)
        """
        # Load configuration
        if isinstance(config, PrivacyConfig):
            self.config = config
        else:
            self.config = load_config(config)

        validate_config(self.config)

        # Initialize recognizer registry
        self._registry = RecognizerRegistry()

        # Initialize Presidio engines
        self._analyzer: AnalyzerEngine | None = None
        self._anonymizer: AnonymizerEngine | None = None

        # Initialize engines (deferred to allow customization)
        self._init_engines()

    def _init_engines(self) -> None:
        """Initialize Presidio Analyzer and Anonymizer engines."""
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        models = self.config.spacy_nlp_models or [
            {"lang_code": "fr", "model_name": "fr_core_news_lg"},
            {"lang_code": "en", "model_name": "en_core_web_lg"},
        ]

        nlp_engine = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": models,
            }
        ).create_engine()

        supported_languages = [self.config.language]

        # Initialize Analyzer with custom registry
        if self.config.use_presidio_defaults:
            # Use default recognizers
            self._analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine, supported_languages=supported_languages
            )
            self._registry = self._analyzer.registry
        else:
            # Start with empty registry
            self._registry = RecognizerRegistry()
            self._registry.load_predefined_recognizers()
            self._analyzer = AnalyzerEngine(
                registry=self._registry,
                nlp_engine=nlp_engine,
                supported_languages=supported_languages,
            )

        # Add AI4Privacy recognizer if enabled
        if self.config.use_ai4privacy:
            self._load_ai4privacy_recognizer()

        # Add EDS-NLP recognizer if enabled
        if self.config.use_edsnlp:
            self._load_edsnlp_recognizer()

        if not self.config.use_spacy_nlp:
            self._registry.remove_recognizer("SpacyRecognizer")

        # Add custom pattern recognizers
        for pattern_config in self.config.custom_patterns:
            self.add_custom_pattern(
                name=pattern_config["name"],
                patterns=pattern_config["patterns"],
                entity_type=pattern_config["entity_type"],
                score=pattern_config.get("score", 0.5),
                language=pattern_config.get("language", self.config.language),
            )

        # Initialize Anonymizer
        self._anonymizer = AnonymizerEngine()

    def _load_ai4privacy_recognizer(self) -> None:
        """Load AI4Privacy recognizer."""
        from privacy_service.recognizers.ai4privacy_recognizer import (
            AI4PrivacyRecognizer,
        )

        ai4privacy_recognizer = AI4PrivacyRecognizer(
            confidence_threshold=self.config.ai4privacy_confidence_threshold,
            language=self.config.language,
            classify_pii=self.config.ai4privacy_classify_pii,
        )
        self._registry.add_recognizer(ai4privacy_recognizer)

    def _load_edsnlp_recognizer(self) -> None:
        """Load EDS-NLP recognizer."""
        from privacy_service.recognizers.edsnlp_recognizer import EDSNLPRecognizer

        edsnlp_recognizer = EDSNLPRecognizer(
            model_name=self.config.edsnlp_model_name,
            confidence_threshold=self.config.edsnlp_confidence_threshold,
            auto_update=self.config.edsnlp_auto_update,
            language=self.config.language,
        )
        # Load the model (this will download it if needed)
        edsnlp_recognizer.load()
        self._registry.add_recognizer(edsnlp_recognizer)

    def detect(
        self,
        text: str,
        language: str | None = None,
        entities: list[str] | None = None,
        score_threshold: float | None = None,
    ) -> list[DetectionResult]:
        """Detect PII entities in text.

        Args:
            text: Text to analyze
            language: Language code (default: from config)
            entities: Specific entity types to detect (None = all)
            score_threshold: Minimum confidence score (None = no filter)

        Returns:
            List of detected PII entities

        Example:
            >>> service = PrivacyService()
            >>> results = service.detect("John Smith's email is john@example.com")
            >>> for result in results:
            ...     print(f"{result.entity_type}: {result.text}")
        """
        if not text:
            return []

        language = language or self.config.language

        if self._analyzer is None:
            raise ValueError("Analyzer engine not initialized")

        analyzer_results = self._analyzer.analyze(
            text=text,
            language=language,
            entities=entities,
            score_threshold=score_threshold,
        )

        # Convert to our DetectionResult format
        detections = []
        for result in analyzer_results:
            detection = DetectionResult(
                entity_type=result.entity_type,
                start=result.start,
                end=result.end,
                score=result.score,
                text=text[result.start : result.end],
                recognizer=result.recognition_metadata.get("recognizer_name", "unknown")
                if result.recognition_metadata
                else "unknown",
            )
            detections.append(detection)

        return detections

    def anonymize(
        self,
        text: str,
        language: str | None = None,
        strategy: str | None = None,
        entities: list[str] | None = None,
        score_threshold: float | None = None,
    ) -> AnonymizationResult:
        """Anonymize PII entities in text.

        Args:
            text: Text to anonymize
            language: Language code (default: from config)
            strategy: Anonymization strategy (default: from config)
            entities: Specific entity types to anonymize (None = all)
            score_threshold: Minimum confidence score (None = no filter)

        Returns:
            AnonymizationResult with anonymized text and details

        Example:
            >>> service = PrivacyService()
            >>> result = service.anonymize(
            ...     text="John's SSN is 123-45-6789",
            ...     strategy="redact"
            ... )
            >>> print(result.text)
            "John's SSN is "
        """
        if not text:
            return AnonymizationResult(text=text, original_text=text)

        language = language or self.config.language
        strategy = strategy or self.config.default_anonymization_strategy

        if self._analyzer is None:
            raise ValueError("Analyzer engine not initialized")

        if self._anonymizer is None:
            raise ValueError("Anonymizer engine not initialized")

        # Detect PII first
        # Handle case where NLP engine doesn't have the requested language model
        try:
            analyzer_results = self._analyzer.analyze(
                text=text,
                language=language,
                entities=entities,
                score_threshold=score_threshold,
            )
        except Exception as e:
            # For any other error, log and return empty results
            import warnings

            warnings.warn(f"Error during detection: {e}", stacklevel=2)
            analyzer_results = []

        # Build operators config
        operators = self._build_operators_config(strategy)

        print(f"Operators: {operators}")

        # Anonymize
        anonymizer_result = self._anonymizer.anonymize(
            text=text,
            analyzer_results=analyzer_results,  # type: ignore[arg-type]
            operators=operators,
        )

        # Convert to our format
        items = []
        for item in anonymizer_result.items:
            anon_item = AnonymizationItem(
                entity_type=item.entity_type,
                start=item.start,
                end=item.end,
                text=item.text or "",
                operator=item.operator,
                anonymized_text=text[item.start : item.end]
                if hasattr(item, "start")
                else "",
            )
            items.append(anon_item)

        return AnonymizationResult(
            text=anonymizer_result.text,
            items=items,
            original_text=text,
        )

    def _build_operators_config(
        self, default_strategy: str
    ) -> dict[str, OperatorConfig]:
        """Build operators configuration for anonymization.

        Args:
            default_strategy: Default anonymization strategy

        Returns:
            Dictionary mapping entity types to operator configs
        """
        operators = {}

        # Get strategy for each entity type (use default if not specified)
        entity_strategies = self.config.entity_strategies or {}

        # Build operator for default
        default_operator = self._get_operator_config(default_strategy)

        # Add any custom entity strategies
        for entity, strategy in entity_strategies.items():
            operators[entity] = self._get_operator_config(strategy)

        # Fallback default
        operators["DEFAULT"] = default_operator

        return operators

    def _get_operator_config(self, strategy: str) -> OperatorConfig:
        """Get OperatorConfig for a strategy.

        Args:
            strategy: Strategy name (replace, mask, redact, hash, encrypt, etc.)

        Returns:
            OperatorConfig for the strategy
        """
        if strategy == "mask":
            return OperatorConfig(
                "mask", {"masking_char": "*", "chars_to_mask": 1000, "from_end": True}
            )
        elif strategy == "hash":
            return OperatorConfig("hash", {"hash_type": "sha256"})
        elif strategy == "encrypt":
            return OperatorConfig("encrypt", {"key": "WmZq4t7w!z%C*F-J"})  # Default key
        else:
            # For any other valid Presidio anonymizer, keep the configuration "clear"
            # and just pass the operator name through. This keeps behavior simple
            # while still supporting operators like "replace", "keep", "custom", etc.
            valid_strategies = OperatorsFactory().get_anonymizers().keys()
            if strategy in valid_strategies:
                return OperatorConfig(strategy)

            # Unknown strategy: fall back to replace to preserve backward compatibility.
            return OperatorConfig("replace")

    def add_custom_recognizer(self, recognizer) -> None:
        """Add a custom entity recognizer.

        Args:
            recognizer: Presidio EntityRecognizer instance

        Example:
            >>> from presidio_analyzer import EntityRecognizer
            >>> class MyRecognizer(EntityRecognizer):
            ...     pass
            >>> service = PrivacyService()
            >>> service.add_custom_recognizer(MyRecognizer())
        """
        self._registry.add_recognizer(recognizer)

    def add_custom_pattern(
        self,
        name: str,
        patterns: list[str],
        entity_type: str,
        score: float = 0.5,
        language: str = "fr",
    ) -> None:
        """Add a custom regex pattern recognizer.

        Args:
            name: Name of the recognizer
            patterns: List of regex patterns
            entity_type: Entity type to assign
            score: Confidence score for matches
            language: Language of the patterns
        Example:
            >>> service = PrivacyService()
            >>> service.add_custom_pattern(
            ...     name="employee_id",
            ...     patterns=[r"EMP-\\d{6}"],
            ...     entity_type="EMPLOYEE_ID",
            ...     score=0.9
            ... )
        """
        # Create Pattern objects
        pattern_objects = [
            Pattern(name=f"{name}_{i}", regex=pattern, score=score)
            for i, pattern in enumerate(patterns)
        ]

        # Create PatternRecognizer
        recognizer = PatternRecognizer(
            supported_entity=entity_type,
            name=name,
            patterns=pattern_objects,
            supported_language=language,
        )

        self._registry.add_recognizer(recognizer)

    def get_supported_entities(self) -> list[str]:
        """Get list of supported entity types.

        Returns:
            List of entity type names
        """
        entities = set()
        for recognizer in self._registry.recognizers:
            entities.update(recognizer.supported_entities)
        return sorted(entities)

    def get_recognizers(self) -> list[str]:
        """Get list of loaded recognizers.

        Returns:
            List of recognizer names
        """
        return [recognizer.name for recognizer in self._registry.recognizers]  # type: ignore[has-type]
