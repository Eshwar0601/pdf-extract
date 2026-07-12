from __future__ import annotations

import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.extractor import (
    ExtractionError,
    OCREngineUnavailableError,
    UnsupportedFileTypeError,
    extract_from_bytes,
    get_ocr_engine_status,
)
from app.models import (
    ExtractedPolicyData,
    ExtractionMetadata,
    ExtractionResponse,
    HealthResponse,
    OcrEngineStatusResponse,
)


app = FastAPI(
    title="OCR Policy Extraction API",
    version="1.0.0",
    description="Extract stable policy/customer fields from uploaded PDFs or images.",
)

allowed_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:4200,http://127.0.0.1:4200",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/ocr-status", response_model=OcrEngineStatusResponse)
def ocr_status() -> OcrEngineStatusResponse:
    return OcrEngineStatusResponse(**get_ocr_engine_status())


@app.post("/extract", response_model=ExtractionResponse)
async def extract_policy_data(
    file: UploadFile = File(...),
    force_ocr: bool = Form(default=False),
) -> ExtractionResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "25"))
    if len(content) > max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Upload is larger than the {max_upload_mb} MB limit.",
        )

    try:
        result = await run_in_threadpool(
            extract_from_bytes,
            content=content,
            filename=file.filename,
            content_type=file.content_type,
            force_ocr=force_ocr,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except OCREngineUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ExtractionResponse(
        success=True,
        data=ExtractedPolicyData(**result.data),
        metadata=ExtractionMetadata(
            filename=file.filename,
            content_type=file.content_type,
            source_type=result.source_type,
            used_ocr=result.used_ocr,
            pages_processed=result.pages_processed,
            missing_fields=result.missing_fields,
            warnings=result.warnings,
        ),
    )