from privacy_service.core.models import (
    AnonymizationItem,
    AnonymizationResult,
    DetectionResult,
    FileAnonymizationResult,
    FileDetectionResult,
    PrivacyConfig,
)


def test_detection_result_repr():
    result = DetectionResult(
        entity_type="EMAIL_ADDRESS",
        start=10,
        end=24,
        score=0.875,
        text="john@example.com",
        recognizer="TestRecognizer",
    )

    # __repr__ should contain key fields and truncate score to two decimals
    repr_str = repr(result)
    assert "DetectionResult" in repr_str
    assert "EMAIL_ADDRESS" in repr_str
    assert "john@example.com" in repr_str
    assert "0.88" in repr_str


def test_anonymization_result_repr_and_defaults():
    result = AnonymizationResult(text="anonymized", original_text="original")
    # items defaults to empty list
    assert result.items == []

    repr_str = repr(result)
    assert "AnonymizationResult" in repr_str
    assert "items_count=0" in repr_str


def test_anonymization_item_fields():
    item = AnonymizationItem(
        entity_type="PERSON",
        start=0,
        end=8,
        text="John Doe",
        operator="mask",
        anonymized_text="********",
    )

    assert item.entity_type == "PERSON"
    assert item.start == 0
    assert item.end == 8
    assert item.text == "John Doe"
    assert item.operator == "mask"
    assert item.anonymized_text == "********"


def test_file_detection_result_to_dict(sample_detections):
    result = FileDetectionResult(
        file_path="/tmp/example.txt",
        detections=sample_detections,
        file_type="text",
        metadata={"encoding": "utf-8"},
    )

    as_dict = result.to_dict()
    assert as_dict["file_path"] == "/tmp/example.txt"
    assert as_dict["file_type"] == "text"
    assert as_dict["detections_count"] == len(sample_detections)
    assert isinstance(as_dict["detections"], list)
    assert as_dict["detections"][0]["entity_type"] == sample_detections[0].entity_type
    assert as_dict["metadata"]["encoding"] == "utf-8"


def test_file_anonymization_result_to_dict():
    result = FileAnonymizationResult(
        input_path="/tmp/input.txt",
        output_path="/tmp/output.txt",
        anonymizations_count=3,
        file_type="text",
        success=True,
        error=None,
    )

    as_dict = result.to_dict()
    assert as_dict["input_path"] == "/tmp/input.txt"
    assert as_dict["output_path"] == "/tmp/output.txt"
    assert as_dict["anonymizations_count"] == 3
    assert as_dict["file_type"] == "text"
    assert as_dict["success"] is True
    assert as_dict["error"] is None


def test_privacy_config_defaults_and_overrides():
    cfg = PrivacyConfig()

    # Defaults
    assert cfg.use_ai4privacy is True
    assert cfg.use_presidio_defaults is True
    assert cfg.ai4privacy_confidence_threshold == 0.01
    assert cfg.ai4privacy_classify_pii is True
    assert cfg.default_anonymization_strategy == "replace"
    assert isinstance(cfg.entity_strategies, dict)
    assert isinstance(cfg.custom_patterns, list)
    assert cfg.language == "fr"

    # Override some values
    cfg.use_ai4privacy = False
    cfg.language = "fr"
    cfg.entity_strategies["PERSON"] = "mask"

    assert cfg.use_ai4privacy is False
    assert cfg.language == "fr"
    assert cfg.entity_strategies["PERSON"] == "mask"
