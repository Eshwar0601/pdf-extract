from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedPolicyData(BaseModel):
    policy_holder_name: str | None = Field(default=None)
    mobile_number: str | None = Field(default=None)
    date_of_birth: str | None = Field(default=None)
    email: str | None = Field(default=None)
    insurance_company_name: str | None = Field(default=None)
    vehicle_registration_number: str | None = Field(default=None)
    vehicle_make: str | None = Field(default=None)
    vehicle_model_variant_subtype: str | None = Field(default=None)
    seating_capacity: str | None = Field(default=None)
    fuel_type: str | None = Field(default=None)
    registration_year: str | None = Field(default=None)
    manufacturing_year: str | None = Field(default=None)
    cubic_capacity: str | None = Field(default=None)
    engine_number: str | None = Field(default=None)
    chassis_number: str | None = Field(default=None)
    idv: str | None = Field(default=None)
    sum_insured: str | None = Field(default=None)
    net_premium: str | None = Field(default=None)
    gst: str | None = Field(default=None)
    gross_premium: str | None = Field(default=None)
    policy_type: Literal["motor", "health", "life"] | None = Field(default=None)


class ExtractionMetadata(BaseModel):
    filename: str | None
    content_type: str | None
    source_type: Literal["pdf", "image", "unknown"]
    used_ocr: bool
    pages_processed: int
    missing_fields: list[str]
    warnings: list[str] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    success: bool = True
    data: ExtractedPolicyData
    metadata: ExtractionMetadata


class HealthResponse(BaseModel):
    status: str


class OcrEngineStatusResponse(BaseModel):
    tesseract_available: bool
    pdftoppm_available: bool
    tesseract_cmd: str | None
    pdftoppm_cmd: str | None
    ready_for_image_ocr: bool
    ready_for_pdf_ocr: bool