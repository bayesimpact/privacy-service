"""FastAPI application for Privacy Service."""

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from privacy_service import PrivacyService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Privacy Service API",
    description="PII detection and anonymization service",
    version="0.1.0",
)

# Initialize PrivacyService (can be configured via environment variable or default)
_config_path = Path("config.yaml") if Path("config.yaml").exists() else None
privacy_service = PrivacyService(config=_config_path)


# Request/Response models
class DetectRequest(BaseModel):
    """Request model for detection endpoint."""

    text: str = Field(..., description="Text to analyze for PII detection")


class DetectionResponse(BaseModel):
    """Response model for detection endpoint."""

    detections: list[dict[str, Any]] = Field(
        ..., description="List of detected PII entities"
    )


class AnonymizeRequest(BaseModel):
    """Request model for anonymization endpoint."""

    text: str = Field(..., description="Text to anonymize")


class AnonymizeResponse(BaseModel):
    """Response model for anonymization endpoint."""

    anonymized_text: str = Field(..., description="Anonymized text")
    original_text: str = Field(..., description="Original text")
    detections: list[dict[str, Any]] = Field(
        ..., description="List of detected and anonymized PII entities"
    )


class HealthResponse(BaseModel):
    """Response model for health endpoint."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Health check endpoint."""
    logger.info("Health check requested")
    return HealthResponse(status="healthy", version="0.1.0")


@app.post("/detect", response_model=DetectionResponse, tags=["detection"])
async def detect(request: DetectRequest) -> DetectionResponse:
    """Detect PII entities in text.

    Args:
        request: Request containing text to analyze

    Returns:
        DetectionResponse with list of detected PII entities
    """
    logger.info(f"Detection request received for text length: {len(request.text)}")
    try:
        detections = privacy_service.detect(request.text)
        logger.info(f"Detected {len(detections)} PII entities")

        # Convert DetectionResult objects to dictionaries
        detections_dict = [
            {
                "entity_type": det.entity_type,
                "text": det.text,
                "start": det.start,
                "end": det.end,
                "score": det.score,
                "recognizer": det.recognizer,
            }
            for det in detections
        ]

        return DetectionResponse(detections=detections_dict)
    except Exception as e:
        logger.error(f"Error during detection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@app.post("/anonymize", response_model=AnonymizeResponse, tags=["anonymization"])
async def anonymize(request: AnonymizeRequest) -> AnonymizeResponse:
    """Anonymize PII entities in text.

    Args:
        request: Request containing text to anonymize

    Returns:
        AnonymizeResponse with anonymized text and detection details
    """
    logger.info(f"Anonymization request received for text length: {len(request.text)}")
    try:
        result = privacy_service.anonymize(request.text)
        logger.info(f"Anonymized text, {len(result.items)} entities processed")

        # Convert AnonymizationItem objects to dictionaries
        detections_dict = [
            {
                "entity_type": item.entity_type,
                "text": item.text,
                "anonymized_text": item.anonymized_text,
                "start": item.start,
                "end": item.end,
                "operator": item.operator,
            }
            for item in result.items
        ]

        return AnonymizeResponse(
            anonymized_text=result.text,
            original_text=result.original_text or request.text,
            detections=detections_dict,
        )
    except Exception as e:
        logger.error(f"Error during anonymization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Anonymization failed: {str(e)}")


@app.exception_handler(Exception)
async def global_exception_handler(request: Any, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
