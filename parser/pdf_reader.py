import io
import pdfplumber


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

                grouped_lines = {}
                for word in word_items:
                    text = str(word.get("text", "")).strip()
                    if not text:
                        continue
                    row_key = round(word.get("top", 0), 1)
                    grouped_lines.setdefault(row_key, []).append(word)

                for row_words in grouped_lines.values():
                    row_words.sort(key=lambda item: item.get("x0", 0))
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