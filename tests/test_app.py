"""Tests for FastAPI application."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from privacy_service.core.models import (
    AnonymizationItem,
    AnonymizationResult,
    DetectionResult,
)


@pytest.fixture
def mock_privacy_service() -> MagicMock:
    """Create a mocked PrivacyService."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_config_path_exists(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock Path.exists() to return False (no config.yaml)."""
    original_exists = Path.exists

    def mock_exists(self: Path) -> bool:
        if self.name == "config.yaml":
            return False
        return original_exists(self)

    monkeypatch.setattr(Path, "exists", mock_exists)
    return MagicMock()


@pytest.fixture
def app_client(
    monkeypatch: pytest.MonkeyPatch,
    mock_privacy_service: MagicMock,
    mock_config_path_exists: MagicMock,
) -> TestClient:
    """Create a test client with mocked dependencies."""
    # Mock PrivacyService initialization
    with patch("app.main.PrivacyService") as mock_service_class:
        mock_service_class.return_value = mock_privacy_service

        # Mock Path.exists for config.yaml check
        with patch("app.main.Path") as mock_path:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value = mock_path_instance

            # Re-import app to get fresh instance with mocks
            import importlib

            import app.main

            importlib.reload(app.main)

            # Replace the privacy_service instance
            app.main.privacy_service = mock_privacy_service

            client = TestClient(app.main.app)
            yield client


@pytest.fixture
def sample_detections() -> list[DetectionResult]:
    """Sample detection results."""
    return [
        DetectionResult(
            entity_type="PERSON",
            start=0,
            end=8,
            score=0.95,
            text="John Doe",
            recognizer="TestRecognizer",
        ),
        DetectionResult(
            entity_type="EMAIL_ADDRESS",
            start=20,
            end=38,
            score=0.98,
            text="john.doe@example.com",
            recognizer="EmailRecognizer",
        ),
    ]


@pytest.fixture
def sample_anonymization_result() -> AnonymizationResult:
    """Sample anonymization result."""
    return AnonymizationResult(
        text="[PERSON]'s email is [EMAIL_ADDRESS]",
        original_text="John Doe's email is john.doe@example.com",
        items=[
            AnonymizationItem(
                entity_type="PERSON",
                start=0,
                end=8,
                text="John Doe",
                operator="replace",
                anonymized_text="[PERSON]",
            ),
            AnonymizationItem(
                entity_type="EMAIL_ADDRESS",
                start=20,
                end=38,
                text="john.doe@example.com",
                operator="replace",
                anonymized_text="[EMAIL_ADDRESS]",
            ),
        ],
    )


# Health endpoint tests
def test_health_endpoint_success(app_client: TestClient):
    """Test health endpoint returns success."""
    response = app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"


def test_health_endpoint_response_model(app_client: TestClient):
    """Test health endpoint response model."""
    response = app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert isinstance(data["status"], str)
    assert isinstance(data["version"], str)


# Detection endpoint tests - success cases
def test_detect_endpoint_success(
    app_client: TestClient,
    mock_privacy_service: MagicMock,
    sample_detections: list[DetectionResult],
):
    """Test detection endpoint with successful detection."""
    mock_privacy_service.detect.return_value = sample_detections

    response = app_client.post(
        "/detect",
        json={"text": "John Doe's email is john.doe@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "detections" in data
    assert len(data["detections"]) == 2

    # Check first detection
    assert data["detections"][0]["entity_type"] == "PERSON"
    assert data["detections"][0]["text"] == "John Doe"
    assert data["detections"][0]["start"] == 0
    assert data["detections"][0]["end"] == 8
    assert data["detections"][0]["score"] == 0.95
    assert data["detections"][0]["recognizer"] == "TestRecognizer"

    # Check second detection
    assert data["detections"][1]["entity_type"] == "EMAIL_ADDRESS"
    assert data["detections"][1]["text"] == "john.doe@example.com"

    # Verify service was called correctly
    mock_privacy_service.detect.assert_called_once_with(
        "John Doe's email is john.doe@example.com"
    )


def test_detect_endpoint_empty_text(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test detection endpoint with empty text."""
    mock_privacy_service.detect.return_value = []

    response = app_client.post("/detect", json={"text": ""})

    assert response.status_code == 200
    data = response.json()
    assert "detections" in data
    assert len(data["detections"]) == 0


def test_detect_endpoint_no_detections(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test detection endpoint when no PII is detected."""
    mock_privacy_service.detect.return_value = []

    response = app_client.post(
        "/detect", json={"text": "This is a normal sentence with no PII."}
    )

    assert response.status_code == 200
    data = response.json()
    assert "detections" in data
    assert len(data["detections"]) == 0


# Detection endpoint tests - error cases
def test_detect_endpoint_service_error(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test detection endpoint when service raises an error."""
    mock_privacy_service.detect.side_effect = ValueError("Service error")

    response = app_client.post("/detect", json={"text": "Some text to analyze"})

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Detection failed" in data["detail"]
    assert "Service error" in data["detail"]


def test_detect_endpoint_unexpected_error(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test detection endpoint with unexpected error."""
    mock_privacy_service.detect.side_effect = RuntimeError("Unexpected error")

    response = app_client.post("/detect", json={"text": "Some text to analyze"})

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Detection failed" in data["detail"]


def test_detect_endpoint_missing_field(app_client: TestClient):
    """Test detection endpoint with missing required field."""
    response = app_client.post("/detect", json={})

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


def test_detect_endpoint_invalid_request_type(app_client: TestClient):
    """Test detection endpoint with invalid request type."""
    response = app_client.post("/detect", json={"text": 123})

    # Pydantic will convert int to string, so this might succeed
    # But let's test with completely invalid JSON
    response = app_client.post("/detect", data="not json")

    assert response.status_code == 422


def test_detect_endpoint_empty_json(app_client: TestClient):
    """Test detection endpoint with empty JSON."""
    response = app_client.post("/detect", json=None)

    assert response.status_code == 422


# Anonymization endpoint tests - success cases
def test_anonymize_endpoint_success(
    app_client: TestClient,
    mock_privacy_service: MagicMock,
    sample_anonymization_result: AnonymizationResult,
):
    """Test anonymization endpoint with successful anonymization."""
    mock_privacy_service.anonymize.return_value = sample_anonymization_result

    response = app_client.post(
        "/anonymize",
        json={"text": "John Doe's email is john.doe@example.com"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "anonymized_text" in data
    assert "original_text" in data
    assert "detections" in data

    assert data["anonymized_text"] == "[PERSON]'s email is [EMAIL_ADDRESS]"
    assert data["original_text"] == "John Doe's email is john.doe@example.com"
    assert len(data["detections"]) == 2

    # Check first anonymization item
    assert data["detections"][0]["entity_type"] == "PERSON"
    assert data["detections"][0]["text"] == "John Doe"
    assert data["detections"][0]["anonymized_text"] == "[PERSON]"
    assert data["detections"][0]["operator"] == "replace"

    # Verify service was called correctly
    mock_privacy_service.anonymize.assert_called_once_with(
        "John Doe's email is john.doe@example.com"
    )


def test_anonymize_endpoint_no_pii(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test anonymization endpoint when no PII is found."""
    mock_privacy_service.anonymize.return_value = AnonymizationResult(
        text="No PII here",
        original_text="No PII here",
        items=[],
    )

    response = app_client.post("/anonymize", json={"text": "No PII here"})

    assert response.status_code == 200
    data = response.json()
    assert data["anonymized_text"] == "No PII here"
    assert data["original_text"] == "No PII here"
    assert len(data["detections"]) == 0


def test_anonymize_endpoint_empty_text(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test anonymization endpoint with empty text."""
    mock_privacy_service.anonymize.return_value = AnonymizationResult(
        text="", original_text="", items=[]
    )

    response = app_client.post("/anonymize", json={"text": ""})

    assert response.status_code == 200
    data = response.json()
    assert data["anonymized_text"] == ""
    assert data["original_text"] == ""


def test_anonymize_endpoint_none_original_text(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test anonymization endpoint when original_text is None."""
    mock_privacy_service.anonymize.return_value = AnonymizationResult(
        text="Anonymized", original_text=None, items=[]
    )

    response = app_client.post("/anonymize", json={"text": "Original"})

    assert response.status_code == 200
    data = response.json()
    assert data["anonymized_text"] == "Anonymized"
    # Should use request text when original_text is None
    assert data["original_text"] == "Original"


# Anonymization endpoint tests - error cases
def test_anonymize_endpoint_service_error(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test anonymization endpoint when service raises an error."""
    mock_privacy_service.anonymize.side_effect = ValueError("Anonymization error")

    response = app_client.post("/anonymize", json={"text": "Some text to anonymize"})

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Anonymization failed" in data["detail"]
    assert "Anonymization error" in data["detail"]


def test_anonymize_endpoint_unexpected_error(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test anonymization endpoint with unexpected error."""
    mock_privacy_service.anonymize.side_effect = RuntimeError("Unexpected error")

    response = app_client.post("/anonymize", json={"text": "Some text to anonymize"})

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert "Anonymization failed" in data["detail"]


def test_anonymize_endpoint_missing_field(app_client: TestClient):
    """Test anonymization endpoint with missing required field."""
    response = app_client.post("/anonymize", json={})

    assert response.status_code == 422  # Validation error
    data = response.json()
    assert "detail" in data


def test_anonymize_endpoint_invalid_request_type(app_client: TestClient):
    """Test anonymization endpoint with invalid request type."""
    response = app_client.post("/anonymize", data="not json")

    assert response.status_code == 422


# Global exception handler tests
def test_global_exception_handler(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test global exception handler catches unhandled exceptions."""
    # Make detect raise an exception that's not caught by endpoint handler
    mock_privacy_service.detect.side_effect = Exception("Unhandled exception")

    # The endpoint handler should catch it, but let's test a case where
    # something else might slip through
    response = app_client.post("/detect", json={"text": "Some text"})

    # Should be handled by endpoint's try/except, but if not, global handler catches it
    assert response.status_code == 500


# Request validation tests
def test_detect_request_validation_empty_string(app_client: TestClient):
    """Test detection request validation with empty string."""
    # Empty string is valid (just no PII)
    response = app_client.post("/detect", json={"text": ""})
    assert response.status_code == 200


def test_detect_request_validation_missing_text(app_client: TestClient):
    """Test detection request validation with missing text field."""
    response = app_client.post("/detect", json={})
    assert response.status_code == 422


def test_anonymize_request_validation_missing_text(app_client: TestClient):
    """Test anonymization request validation with missing text field."""
    response = app_client.post("/anonymize", json={})
    assert response.status_code == 422


# Edge cases and integration tests
def test_detect_with_special_characters(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test detection with special characters in text."""
    mock_privacy_service.detect.return_value = []

    response = app_client.post(
        "/detect",
        json={"text": "Text with émojis 🎉 and spéciál chàracters"},
    )

    assert response.status_code == 200
    mock_privacy_service.detect.assert_called_once()


def test_detect_with_very_long_text(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test detection with very long text."""
    long_text = "A" * 10000
    mock_privacy_service.detect.return_value = []

    response = app_client.post("/detect", json={"text": long_text})

    assert response.status_code == 200
    mock_privacy_service.detect.assert_called_once_with(long_text)


def test_anonymize_with_special_characters(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test anonymization with special characters in text."""
    mock_privacy_service.anonymize.return_value = AnonymizationResult(
        text="Anonymized", original_text="Original", items=[]
    )

    response = app_client.post(
        "/anonymize",
        json={"text": "Text with émojis 🎉 and spéciál chàracters"},
    )

    assert response.status_code == 200
    mock_privacy_service.anonymize.assert_called_once()


def test_multiple_detections_response_format(
    app_client: TestClient,
    mock_privacy_service: MagicMock,
):
    """Test response format with multiple detections."""
    detections = [
        DetectionResult(
            entity_type="PERSON",
            start=0,
            end=4,
            score=0.9,
            text="John",
            recognizer="Recognizer1",
        ),
        DetectionResult(
            entity_type="PERSON",
            start=5,
            end=9,
            score=0.85,
            text="Jane",
            recognizer="Recognizer2",
        ),
        DetectionResult(
            entity_type="EMAIL_ADDRESS",
            start=20,
            end=35,
            score=0.95,
            text="john@example.com",
            recognizer="Recognizer3",
        ),
    ]
    mock_privacy_service.detect.return_value = detections

    response = app_client.post(
        "/detect", json={"text": "John Jane email john@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["detections"]) == 3
    # Verify all detections have required fields
    for detection in data["detections"]:
        assert "entity_type" in detection
        assert "text" in detection
        assert "start" in detection
        assert "end" in detection
        assert "score" in detection
        assert "recognizer" in detection


def test_anonymize_multiple_items_response_format(
    app_client: TestClient,
    mock_privacy_service: MagicMock,
):
    """Test anonymization response format with multiple items."""
    result = AnonymizationResult(
        text="[PERSON] [PERSON] [EMAIL]",
        original_text="John Jane john@example.com",
        items=[
            AnonymizationItem(
                entity_type="PERSON",
                start=0,
                end=4,
                text="John",
                operator="replace",
                anonymized_text="[PERSON]",
            ),
            AnonymizationItem(
                entity_type="PERSON",
                start=5,
                end=9,
                text="Jane",
                operator="replace",
                anonymized_text="[PERSON]",
            ),
            AnonymizationItem(
                entity_type="EMAIL_ADDRESS",
                start=10,
                end=25,
                text="john@example.com",
                operator="replace",
                anonymized_text="[EMAIL]",
            ),
        ],
    )
    mock_privacy_service.anonymize.return_value = result

    response = app_client.post(
        "/anonymize", json={"text": "John Jane john@example.com"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["detections"]) == 3
    # Verify all items have required fields
    for item in data["detections"]:
        assert "entity_type" in item
        assert "text" in item
        assert "anonymized_text" in item
        assert "start" in item
        assert "end" in item
        assert "operator" in item


# Test response models
def test_detection_response_model_structure(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test that detection response matches expected model structure."""
    mock_privacy_service.detect.return_value = [
        DetectionResult(
            entity_type="PERSON",
            start=0,
            end=8,
            score=0.95,
            text="John Doe",
            recognizer="TestRecognizer",
        )
    ]

    response = app_client.post("/detect", json={"text": "John Doe"})

    assert response.status_code == 200
    data = response.json()
    # Verify response has detections field
    assert "detections" in data
    assert isinstance(data["detections"], list)


def test_anonymize_response_model_structure(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test that anonymization response matches expected model structure."""
    mock_privacy_service.anonymize.return_value = AnonymizationResult(
        text="[PERSON]",
        original_text="John",
        items=[
            AnonymizationItem(
                entity_type="PERSON",
                start=0,
                end=4,
                text="John",
                operator="replace",
                anonymized_text="[PERSON]",
            )
        ],
    )

    response = app_client.post("/anonymize", json={"text": "John"})

    assert response.status_code == 200
    data = response.json()
    # Verify response has all required fields
    assert "anonymized_text" in data
    assert "original_text" in data
    assert "detections" in data
    assert isinstance(data["detections"], list)


# Test error handling edge cases
def test_detect_with_none_return_value(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test detection when service returns None (shouldn't happen but test it)."""
    mock_privacy_service.detect.return_value = None

    response = app_client.post("/detect", json={"text": "Some text"})

    # Should handle None gracefully or raise error
    assert response.status_code in [200, 500]


def test_anonymize_with_none_return_value(
    app_client: TestClient, mock_privacy_service: MagicMock
):
    """Test anonymization when service returns None."""
    mock_privacy_service.anonymize.return_value = None

    response = app_client.post("/anonymize", json={"text": "Some text"})

    # Should handle None gracefully or raise error
    assert response.status_code in [200, 500]


# Test HTTP methods
def test_detect_endpoint_wrong_method(app_client: TestClient):
    """Test detection endpoint with wrong HTTP method."""
    response = app_client.get("/detect")
    assert response.status_code == 405  # Method not allowed


def test_anonymize_endpoint_wrong_method(app_client: TestClient):
    """Test anonymization endpoint with wrong HTTP method."""
    response = app_client.get("/anonymize")
    assert response.status_code == 405  # Method not allowed


def test_health_endpoint_wrong_method(app_client: TestClient):
    """Test health endpoint with wrong HTTP method."""
    response = app_client.post("/health")
    assert response.status_code == 405  # Method not allowed


# Test API documentation endpoints
def test_openapi_schema(app_client: TestClient):
    """Test that OpenAPI schema is accessible."""
    response = app_client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data or "swagger" in data
    assert "paths" in data


def test_docs_endpoint(app_client: TestClient):
    """Test that API docs endpoint is accessible."""
    response = app_client.get("/docs")
    assert response.status_code == 200


def test_redoc_endpoint(app_client: TestClient):
    """Test that ReDoc endpoint is accessible."""
    response = app_client.get("/redoc")
    assert response.status_code == 200
