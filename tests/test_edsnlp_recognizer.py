import sys
import types

import pytest

from privacy_service.recognizers.edsnlp_recognizer import EDSNLPRecognizer
from privacy_service.recognizers.entity_mapping import (
    EDS_NLP_TO_PRESIDIO_MAPPING,
    map_edsnlp_to_presidio,
)


def test_edsnlp_recognizer_init_defaults():
    recognizer = EDSNLPRecognizer()
    assert recognizer.model_name == "AP-HP/eds-pseudo-public"
    assert recognizer.confidence_threshold == 0.5
    assert recognizer.language == "fr"
    # Supported entities default to mapping values
    for entity in recognizer.supported_entities:
        assert entity in set(EDS_NLP_TO_PRESIDIO_MAPPING.values())


def test_edsnlp_recognizer_load_uses_edsnlp(monkeypatch: pytest.MonkeyPatch):
    loaded_args = {}

    def fake_load(*args, **kwargs):
        loaded_args["args"] = args
        loaded_args["kwargs"] = kwargs

        # Return a dummy nlp callable
        def fake_nlp(text: str):
            return types.SimpleNamespace(ents=[])

        return fake_nlp

    fake_module = types.SimpleNamespace(load=fake_load)
    monkeypatch.setitem(sys.modules, "edsnlp", fake_module)

    recognizer = EDSNLPRecognizer(
        model_name="AP-HP/eds-pseudo-public", confidence_threshold=0.5, auto_update=True
    )
    recognizer.load()

    assert recognizer._nlp is not None
    assert loaded_args["kwargs"]["model"] == "AP-HP/eds-pseudo-public"
    assert loaded_args["kwargs"]["auto_update"] is True


def test_edsnlp_recognizer_analyze_basic(monkeypatch: pytest.MonkeyPatch):
    # Fake EDS-NLP pipeline returning one entity
    def fake_nlp(text: str):
        ent = types.SimpleNamespace(
            label_="ADRESSE",
            text="33 boulevard de Picpus",
            start_char=0,
            end_char=23,
        )
        return types.SimpleNamespace(ents=[ent])

    def fake_load(*args, **kwargs):
        return fake_nlp

    fake_module = types.SimpleNamespace(load=fake_load)
    monkeypatch.setitem(sys.modules, "edsnlp", fake_module)

    recognizer = EDSNLPRecognizer(confidence_threshold=0.5)
    results = recognizer.analyze(
        "33 boulevard de Picpus",
        entities=["LOCATION"],  # mapped from ADRESSE
    )

    assert len(results) == 1
    r = results[0]
    assert r.entity_type == "LOCATION"
    assert r.start == 0
    assert r.end == 23
    assert r.score == pytest.approx(0.9)
    assert r.recognition_metadata["recognizer_name"] == "EDSNLPRecognizer"
    assert r.recognition_metadata["original_entity"] == "ADRESSE"
    assert r.recognition_metadata["detected_value"] == "33 boulevard de Picpus"


def test_edsnlp_recognizer_analyze_filters_by_entities(
    monkeypatch: pytest.MonkeyPatch,
):
    # Fake EDS-NLP pipeline returning a LOCATION mapped entity
    def fake_nlp(text: str):
        ent = types.SimpleNamespace(
            label_="ADRESSE",
            text="33 boulevard de Picpus",
            start_char=0,
            end_char=23,
        )
        return types.SimpleNamespace(ents=[ent])

    def fake_load(*args, **kwargs):
        return fake_nlp

    fake_module = types.SimpleNamespace(load=fake_load)
    monkeypatch.setitem(sys.modules, "edsnlp", fake_module)

    recognizer = EDSNLPRecognizer(confidence_threshold=0.5)
    # ADRESSE -> LOCATION, but we only request PERSON, so we should get no results.
    assert recognizer.analyze("33 boulevard de Picpus", entities=["PERSON"]) == []


def test_edsnlp_recognizer_analyze_handles_empty_text():
    recognizer = EDSNLPRecognizer()
    assert recognizer.analyze("", entities=["LOCATION"]) == []
    assert recognizer.analyze("   ", entities=["LOCATION"]) == []


def test_edsnlp_recognizer_analyze_handles_errors(monkeypatch: pytest.MonkeyPatch):
    """If EDS-NLP pipeline raises, recognizer returns [] and warns."""
    import warnings

    def fake_nlp(text: str):
        raise RuntimeError("boom")

    def fake_load(*args, **kwargs):
        return fake_nlp

    fake_module = types.SimpleNamespace(load=fake_load)
    monkeypatch.setitem(sys.modules, "edsnlp", fake_module)

    recognizer = EDSNLPRecognizer()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        results = recognizer.analyze("some text", entities=["LOCATION"])

    assert results == []
    assert any("Error during EDS-NLP analysis" in str(w.message) for w in caught)


def test_edsnlp_recognizer_get_supported_entities_and_to_dict_flags():
    recognizer = EDSNLPRecognizer()
    entities = recognizer.get_supported_entities()
    assert entities == recognizer.supported_entities

    info = recognizer.to_dict()
    assert isinstance(info["is_loaded"], bool)
    assert info["recognizer_name"] == "EDSNLPRecognizer"
    assert info["model_name"] == "AP-HP/eds-pseudo-public"


def test_map_edsnlp_to_presidio_known_and_unknown_entities():
    # Known EDS-NLP mapping
    assert map_edsnlp_to_presidio("ADRESSE") == "LOCATION"

    # Unknown entity returns itself uppercased without spaces
    assert map_edsnlp_to_presidio("Custom_Entity") == "CUSTOM_ENTITY"
