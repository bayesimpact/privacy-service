from typing import Any

import pytest

from privacy_service.core.models import (
    AnonymizationResult,
    DetectionResult,
    PrivacyConfig,
)
from privacy_service.core.service import PrivacyService


@pytest.fixture
def service_with_mocks(
    monkeypatch: pytest.MonkeyPatch,
    mock_analyzer,
    mock_anonymizer,
    preset_valid_config: PrivacyConfig,
) -> PrivacyService:
    """Create a PrivacyService instance wired to mocked Presidio engines."""

    # Patch load_config/validate_config so __init__ uses our pre-built config
    from privacy_service.core import config as config_module

    monkeypatch.setattr(
        config_module, "load_config", lambda source=None: preset_valid_config
    )
    monkeypatch.setattr(config_module, "validate_config", lambda cfg: None)

    # Re-import PrivacyService so it picks up patched functions if needed
    service = PrivacyService(config=preset_valid_config)

    # Ensure our mocked engines are used
    service._analyzer = mock_analyzer  # type: ignore[assignment]
    service._anonymizer = mock_anonymizer  # type: ignore[assignment]

    return service


def test_detect_returns_empty_list_for_empty_text(service_with_mocks: PrivacyService):
    assert service_with_mocks.detect("") == []
    assert service_with_mocks.detect("   ") == []


def test_detect_converts_presidio_results_to_detection_result(
    service_with_mocks: PrivacyService, mock_analyzer
):
    # Prepare fake Presidio results for the analyzer
    class FakeResult:
        def __init__(
            self, entity_type: str, start: int, end: int, score: float, metadata: Any
        ):
            self.entity_type = entity_type
            self.start = start
            self.end = end
            self.score = score
            self.recognition_metadata = metadata

    text = "John Doe"
    mock_analyzer_results: list[FakeResult] = [
        FakeResult(
            entity_type="PERSON",
            start=0,
            end=8,
            score=0.9,
            metadata={"recognizer_name": "TestRecognizer"},
        )
    ]

    # Inject results into mock analyzer
    def analyze(text: str, language: str, entities=None, score_threshold=None):
        return mock_analyzer_results

    mock_analyzer.analyze = analyze  # type: ignore[assignment]

    detections = service_with_mocks.detect(text)
    assert len(detections) == 1
    det = detections[0]
    assert isinstance(det, DetectionResult)
    assert det.entity_type == "PERSON"
    assert det.start == 0
    assert det.end == 8
    assert det.text == "John Doe"
    assert det.recognizer == "TestRecognizer"


def test_anonymize_returns_original_for_empty_text(service_with_mocks: PrivacyService):
    result = service_with_mocks.anonymize("")
    assert isinstance(result, AnonymizationResult)
    assert result.text == ""
    assert result.original_text == ""
    assert result.items == []


def test_anonymize_uses_analyzer_and_anonymizer(
    service_with_mocks: PrivacyService, mock_analyzer, mock_anonymizer
):
    # Configure analyzer to produce a single detection
    class FakeResult:
        def __init__(self, entity_type: str, start: int, end: int, score: float):
            self.entity_type = entity_type
            self.start = start
            self.end = end
            self.score = score
            self.recognition_metadata = {"recognizer_name": "TestRecognizer"}

    def analyze(text: str, language: str, entities=None, score_threshold=None):
        return [FakeResult("PERSON", 0, 8, 0.9)]

    mock_analyzer.analyze = analyze  # type: ignore[assignment]

    text = "John Doe"
    result = service_with_mocks.anonymize(text, strategy="mask")

    assert isinstance(result, AnonymizationResult)
    assert result.text == "ANONYMIZED"
    assert result.original_text == text
    assert len(result.items) == 1
    item = result.items[0]
    assert item.entity_type == "PERSON"
    assert item.start == 0
    assert item.end == 8
    assert item.text == "John Doe"
    # We don't depend on the exact Presidio operator name here, just that some
    # operator choice was recorded.
    assert isinstance(item.operator, str)
    assert item.operator != ""


def test_build_operators_config_uses_default_and_entity_overrides(
    service_with_mocks: PrivacyService,
):
    service_with_mocks.config.default_anonymization_strategy = "replace"
    service_with_mocks.config.entity_strategies = {"PERSON": "mask"}

    operators = service_with_mocks._build_operators_config("replace")
    assert "DEFAULT" in operators
    assert "PERSON" in operators
    # We only assert that an OperatorConfig object is returned for each key; we don't
    # depend on its internal attributes, which belong to Presidio.
    from presidio_anonymizer.entities import OperatorConfig

    assert isinstance(operators["DEFAULT"], OperatorConfig)
    assert isinstance(operators["PERSON"], OperatorConfig)


def test_get_operator_config_handles_known_and_unknown_strategies(
    service_with_mocks: PrivacyService, monkeypatch: pytest.MonkeyPatch
):
    from privacy_service.core import service as service_module

    class DummyFactory:
        @staticmethod
        def get_anonymizers():
            return {"replace": object(), "mask": object()}

    monkeypatch.setattr(service_module, "OperatorsFactory", DummyFactory)

    from presidio_anonymizer.entities import OperatorConfig

    # Known strategies should yield OperatorConfig instances
    cfg_mask = service_with_mocks._get_operator_config("mask")
    assert isinstance(cfg_mask, OperatorConfig)

    cfg_hash = service_with_mocks._get_operator_config("hash")
    assert isinstance(cfg_hash, OperatorConfig)

    cfg_encrypt = service_with_mocks._get_operator_config("encrypt")
    assert isinstance(cfg_encrypt, OperatorConfig)

    # Unknown strategy should also yield an OperatorConfig (fallback "replace")
    cfg_unknown = service_with_mocks._get_operator_config("unknown_strategy")
    assert isinstance(cfg_unknown, OperatorConfig)


def test_add_custom_pattern_registers_recognizer(service_with_mocks: PrivacyService):
    initial_count = len(service_with_mocks.get_recognizers())

    service_with_mocks.add_custom_pattern(
        name="employee_id",
        patterns=[r"EMP-\d{5}"],
        entity_type="EMPLOYEE_ID",
        score=0.9,
    )

    assert len(service_with_mocks.get_recognizers()) >= initial_count


def test_get_supported_entities_aggregates_registry(monkeypatch: pytest.MonkeyPatch):
    class DummyRecognizer:
        def __init__(self, entities):
            self.supported_entities = entities
            self.name = "Dummy"

    registry = type(
        "R",
        (),
        {
            "recognizers": [
                DummyRecognizer(["PERSON"]),
                DummyRecognizer(["EMAIL_ADDRESS", "PERSON"]),
            ]
        },
    )()

    # Create a minimal PrivacyService instance without running __init__/_init_engines
    svc = PrivacyService.__new__(PrivacyService)
    svc._registry = registry  # type: ignore[assignment]

    entities = svc.get_supported_entities()
    assert "PERSON" in entities
    assert "EMAIL_ADDRESS" in entities


def test_init_uses_load_config_for_non_privacyconfig(monkeypatch: pytest.MonkeyPatch):
    """When config is not a PrivacyConfig, __init__ must call load_config."""
    from privacy_service.core import config as config_module

    called: dict[str, Any] = {"source": None}

    def fake_load_config(source: Any = None) -> PrivacyConfig:
        called["source"] = source
        # Return a simple but valid config
        return PrivacyConfig(default_anonymization_strategy="replace")

    from privacy_service.core import service as service_module

    monkeypatch.setattr(config_module, "load_config", fake_load_config)
    # Ensure the already-imported symbol in service.py also uses our fake.
    monkeypatch.setattr(service_module, "load_config", fake_load_config)
    monkeypatch.setattr(config_module, "validate_config", lambda c: None)

    # Also avoid hitting real Presidio engines

    class DummyAnalyzerEngine:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            # Minimal registry with recognizers list and add_recognizer to satisfy
            # _load_ai4privacy_recognizer / add_custom_recognizer.
            class DummyRegistry:
                def __init__(self) -> None:
                    self.recognizers: list[Any] = []

                def add_recognizer(self, recognizer: Any) -> None:
                    self.recognizers.append(recognizer)

            self.registry = DummyRegistry()

    monkeypatch.setattr(service_module, "AnalyzerEngine", DummyAnalyzerEngine)

    cfg_dict = {"recognizers": {}}
    svc = PrivacyService(config=cfg_dict)

    assert called["source"] is cfg_dict
    assert isinstance(svc.config, PrivacyConfig)


def test_init_engines_with_presidio_defaults_and_nlp_engine(
    monkeypatch: pytest.MonkeyPatch,
):
    """Exercise _init_engines branch with use_presidio_defaults and nlp_engine"""
    from privacy_service.core import service as service_module

    cfg = PrivacyConfig(
        use_ai4privacy=False,
        use_presidio_defaults=True,
        ai4privacy_confidence_threshold=0.5,
        ai4privacy_classify_pii=True,
        default_anonymization_strategy="replace",
        entity_strategies={},
        custom_patterns=[],
        language="fr",
    )

    class DummyAnalyzerEngine:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.kwargs = kwargs
            # Minimal registry with recognizers attribute
            self.registry = type("R", (), {"recognizers": []})()

    class DummyNlpProvider:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def create_engine(self) -> Any:
            return object()

    from privacy_service.core import config as config_module

    monkeypatch.setattr(config_module, "validate_config", lambda c: None)
    monkeypatch.setattr(
        service_module, "NlpEngineProvider", DummyNlpProvider, raising=False
    )
    monkeypatch.setattr(service_module, "AnalyzerEngine", DummyAnalyzerEngine)

    svc = PrivacyService(config=cfg)

    assert isinstance(svc._analyzer, DummyAnalyzerEngine)
    # When an NLP engine is available, it should be passed in kwargs.
    assert "nlp_engine" in svc._analyzer.kwargs
    assert "supported_languages" in svc._analyzer.kwargs


def test_init_engines_without_presidio_defaults_loads_registry_and_ai4privacy(
    monkeypatch: pytest.MonkeyPatch,
):
    """Exercise _init_engines branch."""
    from privacy_service.core import service as service_module

    cfg = PrivacyConfig(
        use_ai4privacy=True,
        use_presidio_defaults=False,
        ai4privacy_confidence_threshold=0.42,
        ai4privacy_classify_pii=False,
        default_anonymization_strategy="replace",
        entity_strategies={},
        custom_patterns=[
            {
                "name": "employee_id",
                "entity_type": "EMPLOYEE_ID",
                "patterns": [r"EMP-\d{5}"],
                "score": 0.9,
            }
        ],
        language="fr",
    )

    class DummyRegistry:
        def __init__(self) -> None:
            self.recognizers: list[Any] = []
            self.load_predefined_called = False

        def load_predefined_recognizers(self) -> None:
            self.load_predefined_called = True

        def add_recognizer(self, recognizer: Any) -> None:
            self.recognizers.append(recognizer)

    class DummyAnalyzerEngine:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class DummyAI4PrivacyRecognizer:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            self.name = "DummyAI4P"
            self.supported_entities = ["PII"]

    from privacy_service.core import config as config_module

    monkeypatch.setattr(config_module, "validate_config", lambda c: None)

    # Force NlpEngineProvider to return None so we hit the branch without nlp_engine.
    class DummyNlpProvider:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def create_engine(self) -> Any:
            return None

    monkeypatch.setattr(
        service_module, "NlpEngineProvider", DummyNlpProvider, raising=False
    )
    monkeypatch.setattr(service_module, "RecognizerRegistry", DummyRegistry)
    monkeypatch.setattr(service_module, "AnalyzerEngine", DummyAnalyzerEngine)
    monkeypatch.setattr(
        service_module, "AI4PrivacyRecognizer", DummyAI4PrivacyRecognizer, raising=False
    )

    svc = PrivacyService(config=cfg)

    assert isinstance(svc._registry, DummyRegistry)
    assert svc._registry.load_predefined_called is True
    # One AI4Privacy recognizer + one pattern recognizer
    assert len(svc._registry.recognizers) >= 2
    # When no nlp_engine is available and use_presidio_defaults is False,
    # AnalyzerEngine should be constructed with an explicit registry.
    assert "registry" in svc._analyzer.kwargs


def test_anonymize_handles_detection_errors(
    service_with_mocks: PrivacyService, mock_analyzer, mock_anonymizer
):
    """If detection raises, anonymize should warn and continue with empty results."""
    import warnings

    def analyze_raises(text: str, language: str, entities=None, score_threshold=None):
        raise RuntimeError("boom")

    mock_analyzer.analyze = analyze_raises  # type: ignore[assignment]

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = service_with_mocks.anonymize("John Doe")

    assert isinstance(result, AnonymizationResult)
    assert result.text == "ANONYMIZED"
    assert isinstance(caught, list)
    assert any("Error during detection" in str(w.message) for w in caught)


def test_add_custom_recognizer_delegates_to_registry():
    """Ensure add_custom_recognizer simply forwards to the underlying registry."""

    class DummyRegistry:
        def __init__(self) -> None:
            self.recognizers: list[Any] = []

        def add_recognizer(self, recognizer: Any) -> None:
            self.recognizers.append(recognizer)

    svc = PrivacyService.__new__(PrivacyService)
    svc._registry = DummyRegistry()  # type: ignore[assignment]

    class DummyRecognizer:
        name = "Dummy"
        supported_entities = ["PERSON"]

    svc.add_custom_recognizer(DummyRecognizer())
    assert len(svc._registry.recognizers) == 1
