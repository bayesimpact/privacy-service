from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from privacy_service.core import config as config_module
from privacy_service.core import service as service_module
from privacy_service.core.models import DetectionResult


@pytest.fixture
def sample_text() -> str:
    return "John Doe's email is john.doe@example.com and his SSN is 123-45-6789."


@pytest.fixture
def sample_detections() -> list[Any]:
    return [
        DetectionResult(
            entity_type="PERSON",
            start=0,
            end=8,
            score=0.95,
            text="John Doe",
            recognizer="TestRecognizer",
        )
    ]


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    config_content = {
        "recognizers": {
            "use_ai4privacy": False,
            "use_presidio_defaults": False,
            "ai4privacy": {"confidence_threshold": 0.5, "classify_pii": True},
        },
        "anonymization": {
            "default_strategy": "replace",
            "strategies": {"PERSON": "mask"},
        },
        "language": "fr",
        "custom_patterns": [],
    }

    import yaml

    config_path = tmp_path / "config.yaml"
    with config_path.open("w") as f:
        yaml.safe_dump(config_content, f)
    return config_path


@pytest.fixture
def mock_analyzer(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    """Provide a mock AnalyzerEngine instance and patch it into PrivacyService."""
    mock_results: list[Any] = []

    def analyze(text: str, language: str, entities=None, score_threshold=None):
        return mock_results

    mock_engine = type(
        "MockAnalyzer",
        (),
        {
            "analyze": staticmethod(analyze),
            "registry": type("R", (), {"recognizers": []})(),
        },
    )()

    monkeypatch.setattr(service_module, "AnalyzerEngine", lambda *a, **k: mock_engine)

    yield mock_engine


@pytest.fixture
def mock_anonymizer(monkeypatch: pytest.MonkeyPatch) -> Generator[Any, None, None]:
    """Provide a mock AnonymizerEngine instance and patch it into PrivacyService."""

    class MockItem:
        def __init__(
            self, entity_type: str, start: int, end: int, text: str, operator: str
        ) -> None:
            self.entity_type = entity_type
            self.start = start
            self.end = end
            self.text = text
            self.operator = operator

    class MockResult:
        def __init__(self, text: str, items: list[MockItem]) -> None:
            self.text = text
            self.items = items

    def anonymize(text: str, analyzer_results, operators: dict[str, Any]):
        items = [
            MockItem(
                entity_type=getattr(r, "entity_type", "PERSON"),
                start=getattr(r, "start", 0),
                end=getattr(r, "end", 0),
                text=text[getattr(r, "start", 0) : getattr(r, "end", 0)],
                operator="DEFAULT" if "DEFAULT" in operators else "replace",
            )
            for r in analyzer_results
        ]
        return MockResult(text="ANONYMIZED", items=items)

    mock_engine = type("MockAnonymizer", (), {"anonymize": staticmethod(anonymize)})()

    monkeypatch.setattr(service_module, "AnonymizerEngine", lambda *a, **k: mock_engine)

    yield mock_engine


@pytest.fixture
def preset_valid_config(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a PrivacyConfig instance with validated values without touching disk."""
    cfg = config_module.PrivacyConfig(
        use_ai4privacy=False,
        use_presidio_defaults=False,
        ai4privacy_confidence_threshold=0.5,
        ai4privacy_classify_pii=True,
        default_anonymization_strategy="replace",
        entity_strategies={"PERSON": "mask"},
        custom_patterns=[],
        language="fr",
    )

    # Ensure validation uses only known anonymizers but do not hit the real
    # OperatorsFactory if not needed.
    class DummyFactory:
        @staticmethod
        def get_anonymizers() -> dict[str, Any]:
            return {"replace": object(), "mask": object()}

    monkeypatch.setattr(config_module, "OperatorsFactory", DummyFactory)
    config_module.validate_config(cfg)

    return cfg


@pytest.fixture(autouse=True)
def mock_nlp_engine_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid loading heavy spaCy models by mocking Presidio's NlpEngineProvider.

    This keeps tests fast and memory‑light while still exercising our own logic.
    """
    try:
        from presidio_analyzer import nlp_engine as nlp_engine_module
    except ImportError:
        # If Presidio isn't installed in the test environment, nothing to mock.
        return

    class DummyNlpEngine:
        """Minimal stand‑in for Presidio's NLP engine."""

        def __init__(self) -> None:
            pass

        def is_loaded(self) -> bool:
            """Check if NLP engine is loaded."""
            return True

        def get_supported_languages(self) -> list[str]:
            """Get list of supported languages."""
            return ["en", "fr"]

        def get_supported_entities(self) -> list[str]:
            """Get list of supported entity types."""
            return [
                "PERSON",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "LOCATION",
                "DATE_TIME",
            ]

        def process(
            self, text: str, *args: Any, **kwargs: Any
        ) -> Any:  # pragma: no cover
            return text

    class DummyProvider:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def create_engine(self) -> DummyNlpEngine:
            return DummyNlpEngine()

    # Patch both the Presidio module and our already‑imported service module.
    monkeypatch.setattr(
        nlp_engine_module,
        "NlpEngineProvider",
        DummyProvider,
        raising=False,
    )
    monkeypatch.setattr(
        service_module,
        "NlpEngineProvider",
        DummyProvider,
        raising=False,
    )
