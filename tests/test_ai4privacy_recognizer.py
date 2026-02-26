import sys
import types

import pytest

from privacy_service.recognizers.ai4privacy_recognizer import AI4PrivacyRecognizer
from privacy_service.recognizers.entity_mapping import (
    AI4PRIVACY_TO_PRESIDIO_MAPPING,
    FRENCH_NER_TO_PRESIDIO_MAPPING,
    get_all_ai4privacy_entities,
    get_all_presidio_entities,
    map_ai4privacy_to_presidio,
)


def test_ai4privacy_recognizer_init_defaults():
    recognizer = AI4PrivacyRecognizer()
    assert recognizer.confidence_threshold == 0.01
    assert recognizer.language == "fr"
    assert recognizer.multilingual is True
    assert recognizer.classify_pii is True
    # Supported entities default to mapping values
    for entity in recognizer.supported_entities:
        assert entity in set(AI4PRIVACY_TO_PRESIDIO_MAPPING.values())


def test_ai4privacy_recognizer_multilingual_mode():
    recognizer = AI4PrivacyRecognizer(language="fr")
    assert recognizer.language == "fr"
    assert recognizer.multilingual is True


def test_ai4privacy_recognizer_analyze_uses_observe(monkeypatch: pytest.MonkeyPatch):
    # Build a fake observe function returning a minimal privacy_mask
    def fake_observe(
        text: str,
        score_threshold: float,
        multilingual: bool,
        classify_pii: bool,
        developer_verbose: bool,
    ):
        assert text == "John Doe"
        return {
            "privacy_mask": [
                {
                    "label": "NAME",
                    "activation": 0.9,
                    "start": 0,
                    "end": 8,
                    "value": "John Doe",
                }
            ]
        }

    fake_module = types.SimpleNamespace(observe=fake_observe)
    monkeypatch.setitem(sys.modules, "ai4privacy", fake_module)

    recognizer = AI4PrivacyRecognizer(confidence_threshold=0.5, language="fr")
    results = recognizer.analyze("John Doe", entities=["PERSON"])
    assert len(results) == 1
    r = results[0]
    assert r.entity_type == "PERSON"
    assert r.start == 0
    assert r.end == 8
    assert r.score == pytest.approx(0.9)
    assert r.recognition_metadata["recognizer_name"] == "AI4PrivacyRecognizer"
    assert r.recognition_metadata["original_entity"] == "NAME"


def test_ai4privacy_recognizer_analyze_filters_by_confidence(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_observe(
        text, score_threshold, multilingual, classify_pii, developer_verbose
    ):
        return {
            "privacy_mask": [
                {
                    "label": "NAME",
                    "activation": 0.1,
                    "start": 0,
                    "end": 4,
                    "value": "John",
                },
            ]
        }

    fake_module = types.SimpleNamespace(observe=fake_observe)
    monkeypatch.setitem(sys.modules, "ai4privacy", fake_module)

    recognizer = AI4PrivacyRecognizer(confidence_threshold=0.5)
    assert recognizer.analyze("John", entities=["PERSON"]) == []


def test_ai4privacy_recognizer_analyze_filters_by_entities(
    monkeypatch: pytest.MonkeyPatch,
):
    """Ensure that results are filtered out when mapped entity not in requested list."""

    def fake_observe(
        text, score_threshold, multilingual, classify_pii, developer_verbose
    ):
        return {
            "privacy_mask": [
                {
                    "label": "EMAIL",
                    "activation": 0.9,
                    "start": 0,
                    "end": 10,
                    "value": "john@x.com",
                },
            ]
        }

    fake_module = types.SimpleNamespace(observe=fake_observe)
    monkeypatch.setitem(sys.modules, "ai4privacy", fake_module)

    recognizer = AI4PrivacyRecognizer(confidence_threshold=0.5)
    # EMAIL -> EMAIL_ADDRESS, but we only request PERSON, so we should get no results.
    assert recognizer.analyze("john@x.com", entities=["PERSON"]) == []


def test_ai4privacy_recognizer_analyze_handles_observe_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    """If ai4privacy.observe raises, recognizer returns [] and warns."""
    import warnings

    def fake_observe(*args, **kwargs):
        raise RuntimeError("boom")

    fake_module = types.SimpleNamespace(observe=fake_observe)
    monkeypatch.setitem(sys.modules, "ai4privacy", fake_module)

    recognizer = AI4PrivacyRecognizer()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        results = recognizer.analyze("text", entities=["PERSON"])

    assert results == []
    assert any("Error during ai4privacy analysis" in str(w.message) for w in caught)


def test_ai4privacy_recognizer_get_supported_entities_and_to_dict_flags():
    recognizer = AI4PrivacyRecognizer()
    # get_supported_entities is a thin wrapper, but we still exercise it explicitly.
    entities = recognizer.get_supported_entities()
    assert entities == recognizer.supported_entities

    info = recognizer.to_dict()
    assert isinstance(info["is_loaded"], bool)


def test_ai4privacy_recognizer_analyze_handles_empty_text():
    recognizer = AI4PrivacyRecognizer()
    assert recognizer.analyze("", entities=["PERSON"]) == []
    assert recognizer.analyze("   ", entities=["PERSON"]) == []


def test_ai4privacy_recognizer_to_dict_contains_expected_keys():
    recognizer = AI4PrivacyRecognizer(
        confidence_threshold=0.3, language="fr", classify_pii=False
    )
    data = recognizer.to_dict()
    assert data["recognizer_name"] == "AI4PrivacyRecognizer"
    assert data["confidence_threshold"] == 0.3
    assert data["multilingual"] is True
    assert data["classify_pii"] is False
    assert isinstance(data["supported_entities"], list)


def test_map_ai4privacy_to_presidio_known_and_unknown_entities():
    # Known ai4privacy mapping
    assert map_ai4privacy_to_presidio("EMAIL") == "EMAIL_ADDRESS"

    # Known French NER mapping
    assert map_ai4privacy_to_presidio("PER") == "PERSON"

    # Unknown entity returns itself uppercased without spaces
    assert map_ai4privacy_to_presidio("Custom_Entity") == "CUSTOM_ENTITY"


def test_get_all_ai4privacy_entities_and_presidio_entities_consistency():
    ai4p_entities = get_all_ai4privacy_entities()
    assert set(ai4p_entities) == set(AI4PRIVACY_TO_PRESIDIO_MAPPING.keys())

    presidio_entities = get_all_presidio_entities()
    for v in AI4PRIVACY_TO_PRESIDIO_MAPPING.values():
        assert v in presidio_entities
    for v in FRENCH_NER_TO_PRESIDIO_MAPPING.values():
        assert v in presidio_entities
