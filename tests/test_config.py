from pathlib import Path

import pytest
import yaml

from privacy_service.core.config import (
    get_default_config_path,
    load_config,
    save_config,
    validate_config,
)
from privacy_service.core.models import PrivacyConfig


def test_load_config_from_dict_basic():
    cfg = load_config(
        {
            "recognizers": {
                "use_ai4privacy": False,
                "use_presidio_defaults": False,
                "ai4privacy": {"confidence_threshold": 0.5, "classify_pii": False},
            },
            "anonymization": {
                "default_strategy": "mask",
                "strategies": {"PERSON": "replace"},
            },
            "language": "fr",
            "custom_patterns": [],
        }
    )

    assert isinstance(cfg, PrivacyConfig)
    assert cfg.use_ai4privacy is False
    assert cfg.use_presidio_defaults is False
    assert cfg.ai4privacy_confidence_threshold == 0.5
    assert cfg.ai4privacy_classify_pii is False
    assert cfg.default_anonymization_strategy == "mask"
    assert cfg.entity_strategies["PERSON"] == "replace"
    assert cfg.language == "fr"


def test_load_config_from_file(temp_config_file: Path):
    cfg = load_config(temp_config_file)
    assert isinstance(cfg, PrivacyConfig)
    assert cfg.use_ai4privacy is False
    assert cfg.use_presidio_defaults is False
    assert cfg.ai4privacy_confidence_threshold == 0.5
    assert cfg.ai4privacy_classify_pii is True
    assert cfg.default_anonymization_strategy == "replace"
    assert cfg.entity_strategies["PERSON"] == "mask"
    assert cfg.language == "fr"


def test_load_config_missing_file_raises(tmp_path: Path):
    missing = tmp_path / "missing.yaml"
    with pytest.raises(FileNotFoundError):
        load_config(str(missing))


def test_save_and_reload_config_roundtrip(tmp_path: Path):
    cfg = PrivacyConfig(
        use_ai4privacy=False,
        use_presidio_defaults=True,
        ai4privacy_confidence_threshold=0.2,
        ai4privacy_classify_pii=False,
        default_anonymization_strategy="replace",
        entity_strategies={"EMAIL_ADDRESS": "hash"},
        custom_patterns=[],
        language="fr",
    )

    output_path = tmp_path / "out.yaml"
    save_config(cfg, output_path)
    assert output_path.exists()

    reloaded = load_config(output_path)
    assert reloaded.use_ai4privacy is False
    assert reloaded.use_presidio_defaults is True
    assert reloaded.ai4privacy_confidence_threshold == 0.2
    assert reloaded.ai4privacy_classify_pii is False
    assert reloaded.default_anonymization_strategy == "replace"
    assert reloaded.entity_strategies["EMAIL_ADDRESS"] == "hash"


def test_validate_config_invalid_threshold():
    cfg = PrivacyConfig()
    cfg.ai4privacy_confidence_threshold = 1.5

    with pytest.raises(ValueError):
        validate_config(cfg)


def test_validate_config_invalid_classify_flag():
    cfg = PrivacyConfig()
    cfg.ai4privacy_classify_pii = "yes"  # type: ignore[assignment]

    with pytest.raises(ValueError):
        validate_config(cfg)


def test_validate_config_invalid_strategies(monkeypatch: pytest.MonkeyPatch):
    from privacy_service.core import config as config_module

    class DummyFactory:
        @staticmethod
        def get_anonymizers():
            return {"replace": object()}

    monkeypatch.setattr(config_module, "OperatorsFactory", DummyFactory)

    cfg = PrivacyConfig()
    cfg.default_anonymization_strategy = "invalid"
    with pytest.raises(ValueError):
        validate_config(cfg)


def test_get_default_config_path_prefers_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("language: en\n")

    monkeypatch.chdir(tmp_path)

    found = get_default_config_path()
    assert found == config_path


def test_load_config_from_dict_and_file(tmp_path):
    """Config can be loaded from dict and round-tripped via YAML file."""
    config_dict = {
        "recognizers": {
            "use_ai4privacy": False,
            "use_presidio_defaults": True,
            "ai4privacy": {
                "confidence_threshold": 0.5,
                "classify_pii": False,
            },
        },
        "anonymization": {
            "default_strategy": "mask",
            "strategies": {"EMAIL_ADDRESS": "hash"},
        },
        "custom_patterns": [
            {
                "name": "employee_id",
                "entity_type": "EMPLOYEE_ID",
                "patterns": [r"EMP-\d{6}"],
                "score": 0.9,
            }
        ],
        "language": "fr",
    }

    # Load directly from dict
    config = load_config(config_dict)
    assert isinstance(config, PrivacyConfig)
    assert config.use_ai4privacy is False
    assert config.ai4privacy_confidence_threshold == 0.5
    assert config.default_anonymization_strategy == "mask"
    assert config.entity_strategies["EMAIL_ADDRESS"] == "hash"
    assert config.language == "fr"
    assert config.custom_patterns[0]["name"] == "employee_id"

    # Save to file and load again to exercise YAML path
    config_path = tmp_path / "config.yaml"
    save_config(config, config_path)

    with config_path.open() as f:
        loaded_yaml = yaml.safe_load(f)
    assert loaded_yaml["recognizers"]["ai4privacy"]["confidence_threshold"] == 0.5

    config_from_file = load_config(str(config_path))
    assert isinstance(config_from_file, PrivacyConfig)
    assert config_from_file.ai4privacy_confidence_threshold == 0.5
    assert config_from_file.default_anonymization_strategy == "mask"
    assert config_from_file.entity_strategies["EMAIL_ADDRESS"] == "hash"
    assert config_from_file.language == "fr"


def test_validate_config_invalid_classify_pii_type():
    """ai4privacy_classify_pii must be a boolean."""
    config = PrivacyConfig()
    config.ai4privacy_classify_pii = "yes"  # type: ignore[assignment]

    try:
        validate_config(config)
        raise AssertionError("Expected ValueError for invalid classify_pii type")
    except ValueError as exc:
        assert "ai4privacy_classify_pii" in str(exc)


def test_validate_config_invalid_default_strategy():
    """default_anonymization_strategy must be in allowed list."""
    config = PrivacyConfig()
    config.default_anonymization_strategy = "not-a-strategy"

    try:
        validate_config(config)
        raise AssertionError("Expected ValueError for invalid default strategy")
    except ValueError as exc:
        assert "default_anonymization_strategy" in str(exc)


def test_validate_config_invalid_entity_strategy():
    """Entity-specific strategies must be in allowed list."""
    config = PrivacyConfig()
    config.entity_strategies = {"EMAIL_ADDRESS": "unknown"}

    try:
        validate_config(config)
        raise AssertionError("Expected ValueError for invalid entity strategy")
    except ValueError as exc:
        assert "Strategy for entity 'EMAIL_ADDRESS'" in str(exc)


def test_validate_config_invalid_custom_patterns():
    """Custom patterns must be a list of dicts with required fields."""
    # Non-dict pattern
    config = PrivacyConfig()
    config.custom_patterns = ["not-a-dict"]  # type: ignore[list-item]
    try:
        validate_config(config)
        raise AssertionError("Expected ValueError for non-dict custom pattern")
    except ValueError as exc:
        assert "Custom pattern must be a dictionary" in str(exc)

    # Missing required fields
    config.custom_patterns = [
        {"name": "id_without_patterns"},
    ]
    try:
        validate_config(config)
        raise AssertionError("Expected ValueError for missing fields")
    except ValueError as exc:
        assert "missing required field" in str(exc)

    # patterns field must be list
    config.custom_patterns = [
        {"name": "id", "entity_type": "ID", "patterns": "not-a-list"},
    ]  # type: ignore[list-item]
    try:
        validate_config(config)
        raise AssertionError("Expected ValueError for non-list patterns")
    except ValueError as exc:
        assert "patterns' must be a list of regex strings" in str(exc)
