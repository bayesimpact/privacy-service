"""Configuration management for Privacy Service."""

from pathlib import Path
from typing import Any

import yaml
from presidio_anonymizer.operators import OperatorsFactory

from privacy_service.core.models import PrivacyConfig


def load_config(
    config_source: str | Path | dict[str, Any] | None = None,
) -> PrivacyConfig:
    """Load configuration from file, dict, or use defaults.

    Args:
        config_source: Can be:
            - Path to YAML config file (str or Path)
            - Dictionary with config values
            - None to use defaults

    Returns:
        PrivacyConfig object with loaded configuration

    Raises:
        FileNotFoundError: If config file path provided but doesn't exist
        yaml.YAMLError: If config file is invalid YAML
        ValueError: If config contains invalid values
    """
    # Default configuration
    config_dict = {}

    # Load from file if provided
    if isinstance(config_source, (str, Path)):
        config_path = Path(config_source)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            file_config = yaml.safe_load(f)
            if file_config:
                config_dict = _flatten_config(file_config)

    # Load from dict if provided
    elif isinstance(config_source, dict):
        config_dict = _flatten_config(config_source)

    # Create PrivacyConfig with defaults, then update with provided values
    config = PrivacyConfig()

    # Update with provided values from config_dict (loaded from file or passed as dict)
    if "recognizers" in config_dict:
        recognizers = config_dict["recognizers"]
        config.use_ai4privacy = recognizers.get("use_ai4privacy", config.use_ai4privacy)
        config.use_edsnlp = recognizers.get("use_edsnlp", config.use_edsnlp)
        config.use_presidio_defaults = recognizers.get(
            "use_presidio_defaults", config.use_presidio_defaults
        )
        config.use_spacy_nlp = recognizers.get("use_spacy_nlp", config.use_spacy_nlp)
        if "spacy_nlp_model" in recognizers:
            config.spacy_nlp_models = recognizers["spacy_nlp_model"]

        if "ai4privacy" in recognizers:
            ai4p = recognizers["ai4privacy"]
            config.ai4privacy_confidence_threshold = ai4p.get(
                "confidence_threshold", config.ai4privacy_confidence_threshold
            )
            config.ai4privacy_classify_pii = ai4p.get(
                "classify_pii", config.ai4privacy_classify_pii
            )

        if "edsnlp" in recognizers:
            edsnlp_config = recognizers["edsnlp"]
            config.edsnlp_model_name = edsnlp_config.get(
                "model_name", config.edsnlp_model_name
            )
            config.edsnlp_confidence_threshold = edsnlp_config.get(
                "confidence_threshold", config.edsnlp_confidence_threshold
            )
            config.edsnlp_auto_update = edsnlp_config.get(
                "auto_update", config.edsnlp_auto_update
            )

    if "anonymization" in config_dict:
        anon = config_dict["anonymization"]
        config.default_anonymization_strategy = anon.get(
            "default_strategy", config.default_anonymization_strategy
        )
        config.entity_strategies = anon.get("strategies", config.entity_strategies)

    if "custom_patterns" in config_dict:
        config.custom_patterns = config_dict["custom_patterns"]

    if "language" in config_dict:
        config.language = config_dict["language"]

    return config


def _flatten_config(nested_dict: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested configuration dictionary.

    Args:
        nested_dict: Nested dictionary from YAML

    Returns:
        Flattened dictionary
    """
    # For now, just return as-is since we handle nesting in load_config
    return nested_dict


def save_config(config: PrivacyConfig, output_path: str | Path) -> None:
    """Save configuration to YAML file.

    Args:
        config: PrivacyConfig object to save
        output_path: Path to output YAML file

    Raises:
        IOError: If file cannot be written
    """
    output_path = Path(output_path)

    # Convert to nested dict for better YAML structure
    config_dict = {
        "recognizers": {
            "use_ai4privacy": config.use_ai4privacy,
            "use_edsnlp": config.use_edsnlp,
            "use_presidio_defaults": config.use_presidio_defaults,
            "use_spacy_nlp": config.use_spacy_nlp,
            "spacy_nlp_model": config.spacy_nlp_models,
            "ai4privacy": {
                "confidence_threshold": config.ai4privacy_confidence_threshold,
                "classify_pii": config.ai4privacy_classify_pii,
            },
            "edsnlp": {
                "model_name": config.edsnlp_model_name,
                "confidence_threshold": config.edsnlp_confidence_threshold,
                "auto_update": config.edsnlp_auto_update,
            },
        },
        "anonymization": {
            "default_strategy": config.default_anonymization_strategy,
            "strategies": config.entity_strategies,
        },
        "custom_patterns": config.custom_patterns,
        "language": config.language,
    }

    with open(output_path, "w") as f:
        yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)


def get_default_config_path() -> Path | None:
    """Get default configuration file path if it exists.

    Checks for config in:
    1. ./config.yaml
    2. ~/.privacy-service/config.yaml
    3. /etc/privacy-service/config.yaml

    Returns:
        Path to config file if found, None otherwise
    """
    possible_paths = [
        Path.cwd() / "config.yaml",
        Path.home() / ".privacy-service" / "config.yaml",
        Path("/etc/privacy-service/config.yaml"),
    ]

    for path in possible_paths:
        if path.exists():
            return path

    return None


def validate_config(config: PrivacyConfig) -> None:
    """Validate configuration values.

    Args:
        config: PrivacyConfig to validate

    Raises:
        ValueError: If any config values are invalid
    """
    # Validate confidence threshold
    if not 0.0 <= config.ai4privacy_confidence_threshold <= 1.0:
        raise ValueError(
            f"ai4privacy_confidence_threshold must be between 0.0 and 1.0, "
            f"got {config.ai4privacy_confidence_threshold}"
        )

    # Validate classify_pii flag
    if not isinstance(config.ai4privacy_classify_pii, bool):
        raise ValueError(
            f"ai4privacy_classify_pii must be a boolean,"
            f" got {type(config.ai4privacy_classify_pii)}"
        )

    # Validate EDS-NLP confidence threshold
    if not 0.0 <= config.edsnlp_confidence_threshold <= 1.0:
        raise ValueError(
            f"edsnlp_confidence_threshold must be between 0.0 and 1.0, "
            f"got {config.edsnlp_confidence_threshold}"
        )

    # Validate EDS-NLP auto_update flag
    if not isinstance(config.edsnlp_auto_update, bool):
        raise ValueError(
            f"edsnlp_auto_update must be a boolean,"
            f" got {type(config.edsnlp_auto_update)}"
        )

    # Validate anonymization strategies
    # Derive the list of valid strategies from Presidio's registered anonymizers
    # so we always stay in sync with the underlying engine.
    valid_strategies = list(OperatorsFactory().get_anonymizers().keys())
    if config.default_anonymization_strategy not in valid_strategies:
        raise ValueError(
            f"default_anonymization_strategy must be one of {valid_strategies}, "
            f"got {config.default_anonymization_strategy}"
        )

    if config.entity_strategies:
        for entity, strategy in config.entity_strategies.items():
            if strategy not in valid_strategies:
                raise ValueError(
                    f"Strategy for entity '{entity}' must be one "
                    f"of {valid_strategies}, "
                    f", got {strategy}"
                )

    # Validate custom patterns
    for i, pattern in enumerate(config.custom_patterns):
        if not isinstance(pattern, dict):
            raise ValueError("Custom pattern must be a dictionary")

        required_fields = ["name", "entity_type", "patterns"]
        for field in required_fields:
            if field not in pattern:
                raise ValueError(f"Custom pattern {i} missing required field: {field}")

        if not isinstance(pattern["patterns"], list):
            raise ValueError(
                f"Custom pattern {i} 'patterns' must be a list of regex strings"
            )
