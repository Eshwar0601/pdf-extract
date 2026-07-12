from fastapi import FastAPI, UploadFile, File
import uvicorn

from parser.pdf_reader import extract_pdf_text
from parser.extractor import extract_policy_data

app = FastAPI(
    title="Universal Insurance PDF Extraction API",
    description="Keyword-based Insurance PDF Parser",
    version="2.0.0"
)


@app.get("/")
def home():
    return {
        "status": "running",
        "message": "Universal Insurance PDF Parser API"
    }


@app.post("/extract-policy")
async def extract_policy(file: UploadFile = File(...)):
    """
    Upload any Insurance Policy PDF
    """

    pdf_bytes = await file.read()

    pages, lines, words, tables, raw_text = extract_pdf_text(pdf_bytes)

    result = extract_policy_data(
        pages=pages,
        lines=lines,
        raw_text=raw_text,
        words=words,
        tables=tables
    )

    return result


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8080,
        reload=True
    )