import io
import re
import pdfplumber


def _ocr_page(page):
    """Return OCR text for a page with no usable embedded text.

    Kept lazy so normal, digitally-generated policies do not pay the OCR cost.
    """
    try:
        import pytesseract
        image = page.to_image(resolution=250).original
        return pytesseract.image_to_string(image, config="--psm 6")
    except Exception:
        return ""


def extract_pdf_text(pdf_bytes: bytes):
    """Extract page text, lines, coordinate words, and tables from a PDF."""

    pages = []
    lines = []
    words = []
    tables = []
    raw_parts = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            # Many insurer PDFs are scanned images.  OCR only sparse pages,
            # rather than blindly OCR-ing every page and degrading native text.
            if len(re.sub(r"\s+", "", page_text)) < 40:
                page_text = _ocr_page(page) or page_text
            raw_parts.append(page_text)
            pages.append(page_text)

            word_items = page.extract_words(
                x_tolerance=2,
                y_tolerance=2,
                keep_blank_chars=False
            )

            if word_items:
                for word in word_items:
                    text = str(word.get("text", "")).strip()
                    if not text:
                        continue
                    words.append(
                        {
                            "page": page_number,
                            "text": text,
                            "x0": word.get("x0", 0),
                            "x1": word.get("x1", 0),
                            "top": word.get("top", 0),
                            "bottom": word.get("bottom", 0),
                        }
                    )

                groups = []
                for word in sorted(word_items, key=lambda item: (item.get("top", 0), item.get("x0", 0))):
                    top = word.get("top", 0)
                    if not groups:
                        groups.append({"top": top, "words": [word]})
                        continue

                    last = groups[-1]
                    if abs(top - last["top"]) <= 3:
                        last["words"].append(word)
                    else:
                        groups.append({"top": top, "words": [word]})

                for group in groups:
                    row_words = sorted(group["words"], key=lambda item: item.get("x0", 0))
                    line_text = " ".join(str(item.get("text", "")).strip() for item in row_words if str(item.get("text", "")).strip())
                    if line_text:
                        lines.append(clean_line(line_text))

            page_tables = page.extract_tables()
            if page_tables:
                for table in page_tables:
                    if table:
                        tables.append(table)

    raw_text = "\n".join(raw_parts)
    return pages, lines, words, tables, raw_text


def extract_words(pdf_bytes: bytes):
    """Extract every word with its position for coordinate-based matching."""

    words = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            for word in page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False):
                text = str(word.get("text", "")).strip()
                if not text:
                    continue
                words.append(
                    {
                        "page": page_number,
                        "text": text,
                        "x0": word.get("x0", 0),
                        "x1": word.get("x1", 0),
                        "top": word.get("top", 0),
                        "bottom": word.get("bottom", 0),
                    }
                )
    return words


def extract_tables(pdf_bytes: bytes):
    """Extract tables from the PDF."""

    tables = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                if table:
                    tables.append(table)
    return tables


def clean_line(line: str) -> str:
    """Remove unnecessary spaces from a single line."""

    if not line:
        return ""

    line = str(line).replace("\t", " ")
    while "  " in line:
        line = line.replace("  ", " ")
    return line.strip()
