"""Privacy Service - PII detection and anonymization library."""

__version__ = "0.1.0"

from privacy_service.core.models import AnonymizationResult, DetectionResult
from privacy_service.core.service import PrivacyService

__all__ = ["PrivacyService", "DetectionResult", "AnonymizationResult", "__version__"]
