from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterable, Literal

import pdfplumber
from PIL import Image

OUTPUT_KEYS = (
    "policy_holder_name",
    "mobile_number",
    "date_of_birth",
    "email",
    "insurance_company_name",
    "vehicle_registration_number",
    "vehicle_make",
    "vehicle_model_variant_subtype",
    "seating_capacity",
    "fuel_type",
    "registration_year",
    "manufacturing_year",
    "cubic_capacity",
    "engine_number",
    "chassis_number",
    "idv",
    "sum_insured",
    "net_premium",
    "gst",
    "gross_premium",
    "policy_type",
)

SourceType = Literal["pdf", "image", "unknown"]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_OCR_BIN = PROJECT_ROOT / ".local" / "ocr-tools" / "bin"

MIN_IDV_AMOUNT = 10000

ENGINE_LABEL_PATTERN = (
    r"\b(?:"
    r"(?:engine|eng\.?)\s*(?:no|n[o0]|number|num|#)\.?\s*(?:[/&-]|\band\b)\s*motor\s*(?:no|n[o0]|number|num|#)\.?"
    r"|(?:engine|eng\.?)\s*(?:(?:[/&-]|\band\b)\s*motor|\(\s*motor\s*\))\s*(?:no|n[o0]|number|num|#)\.?"
    r"|motor\s*(?:[/&-]|\band\b)\s*(?:engine|eng\.?)\s*(?:no|n[o0]|number|num|#)\.?"
    r"|(?:engine|eng\.?|motor)\s*(?:(?:sr|s)\.?\s*)?(?:serial\s*)?(?:no|n[o0]|number|num|#)\.?"
    r"|(?:engine|eng\.?|motor)\s*(?:serial|sr\.?|s\.?\s*no|s/n)\s*(?:no|n[o0]|number|num)?\.?"
    r")(?=\s|[:;|#./-]|$)"
)

PREMIUM_FIELD_KEYS = {"net_premium", "gst", "gross_premium"}

PREMIUM_LABEL_PATTERNS = {
    "net_premium": (
        r"\bnet\s+(?:od\s+)?premium\b",
        r"\btotal\s+net\s+premium\b",
        r"\bpremium\s+before\s+(?:tax|gst)\b",
        r"\bsubtotal\s+premium\b",
        r"\bsub\s*total\s+premium\b",
        r"\btotal\s+premium\b",
        r"\btotal\s+policy\s+premium\b",
        r"\bpremium\s+payable\b",
        r"\bfinal\s+premium\b",
    ),
    "gst": (
        r"\btotal\s+gst\b",
        r"\bgst\s*(?:amount|premium|payable)?\b",
        r"\bgoods\s+and\s+services\s+tax\b",
        r"\btax\s+amount\b",
        r"\btotal\s+tax\b",
    ),
    "gross_premium": (
        r"\bgross\s+premium\b",
        r"\btotal\s+premium\b",
        r"\bpremium\s+payable\b",
        r"\bfinal\s+premium\b",
        r"\btotal\s+amount\s+payable\b",
        r"\bamount\s+payable\b",
        r"\btotal\s+policy\s+premium\b",
        r"\bpremium\s+including\s+gst\b",
    ),
}

GST_COMPONENT_LABEL_PATTERNS = (
    r"\bcgst\b",
    r"\bsgst\b",
    r"\bigst\b",
    r"\butgst\b",
)

KNOWN_INSURANCE_COMPANY_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ICICI Lombard General Insurance Company Limited", (r"\bicici\s+lombard\b", r"\bicicilombard\b")),
    ("HDFC ERGO General Insurance Company Limited", (r"\bhdfc\s+ergo\b", r"\bhdfcergo\b")),
    ("Bajaj Allianz General Insurance Company Limited", (r"\bbajaj\s+allianz\s+general\s+insurance\b",)),
    ("Tata AIG General Insurance Company Limited", (r"\btata\s+aig\b", r"\btataaig\b")),
    ("SBI General Insurance Company Limited", (r"\bsbi\s+general\s+insurance\b", r"\bsbigeneral\b")),
    ("Reliance General Insurance Company Limited", (r"\breliance\s+general\s+insurance\b", r"\breliancegeneral\b")),
    ("The New India Assurance Company Limited", (r"\bnew\s+india\s+assurance\b", r"\bthe\s+new\s+india\s+assurance\b")),
    ("National Insurance Company Limited", (r"\bnational\s+insurance\s+(?:company|co\.?|ltd|limited)\b",)),
    ("United India Insurance Company Limited", (r"\bUnited\s+India\s+Insurance\b",)),
    ("The Oriental Insurance Company Limited", (r"\boriental\s+insurance\b", r"\bthe\s+oriental\s+insurance\b")),
    ("Royal Sundaram General Insurance Company Limited", (r"\broyal\s+sundaram\b",)),
    ("Go Digit General Insurance Limited", (r"\bgo\s+digit\b", r"\bdigit\s+general\s+insurance\b")),
    ("Acko General Insurance Limited", (r"\backo\b",)),
    ("Kotak Mahindra General Insurance Company Limited", (r"\bkotak\s+mahindra\s+general\s+insurance\b", r"\bkotak\s+general\s+insurance\b")),
    ("Future Generali India Insurance Company Limited", (r"\bfuture\s+generali\b",)),
    ("IFFCO Tokio General Insurance Company Limited", (r"\biffco\s+tokio\b",)),
    ("Universal Sompo General Insurance Company Limited", (r"\buniversal\s+sompo\b",)),
    ("Cholamandalam MS General Insurance Company Limited", (r"\bcholamandalam\s+ms\b", r"\bchola\s+ms\b")),
    ("Shriram General Insurance Company Limited", (r"\bshriram\s+general\s+insurance\b",)),
    ("Magma HDI General Insurance Company Limited", (r"\bmagma\s*-?\s*hdi\b", r"\bmagmahdi\b")),
    ("Zuno General Insurance Limited", (r"\bzuno\s+general\s+insurance\b", r"\bedelweiss\s+general\s+insurance\b")),
    ("Liberty General Insurance Limited", (r"\bliberty\s+general\s+insurance\b",)),
    ("Raheja QBE General Insurance Company Limited", (r"\braheja\s+qbe\b",)),
    ("Niva Bupa Health Insurance Company Limited", (r"\bniva\s+bupa\b", r"\bmax\s+bupa\b")),
    ("Care Health Insurance Limited", (r"\bcare\s+health\s+insurance\b", r"\breligare\s+health\s+insurance\b")),
    ("Star Health and Allied Insurance Company Limited", (r"\bstar\s+health\b",)),
    ("Aditya Birla Health Insurance Company Limited", (r"\baditya\s+birla\s+health\s+insurance\b",)),
    ("Life Insurance Corporation of India", (r"\blife\s+insurance\s+corporation\s+of\s+india\b", r"\blic\s+of\s+india\b", r"\blic\b")),
    ("HDFC Life Insurance Company Limited", (r"\bhdfc\s+life\b",)),
    ("SBI Life Insurance Company Limited", (r"\bsbi\s+life\b",)),
    ("ICICI Prudential Life Insurance Company Limited", (r"\bicici\s+prudential\s+life\b", r"\bprudential\s+life\b")),
    ("Max Life Insurance Company Limited", (r"\bmax\s+life\b",)),
    ("Tata AIA Life Insurance Company Limited", (r"\btata\s+aia\b",)),
    ("Bajaj Allianz Life Insurance Company Limited", (r"\bbajaj\s+allianz\s+life\b",)),
)


class ExtractionError(Exception):
    """Base exception for extraction failures."""


class UnsupportedFileTypeError(ExtractionError):
    """Raised when an upload is not a supported PDF or image."""


class OCREngineUnavailableError(ExtractionError):
    """Raised when OCR is required but the local OCR engine is unavailable."""


class OCRProcessingError(ExtractionError):
    """Raised when an OCR or PDF processing command fails."""


@dataclass(frozen=True)
class FieldSpec:
    # NOTE: the field definitions for this dataclass were missing from the
    # source (the pasted text jumped straight from the class header into
    # unrelated PDF-rendering code). Reconstructed from how FieldSpec(...)
    # is instantiated later in this file (key=..., labels=..., cleaner=...).
    key: str
    labels: tuple[str, ...]
    cleaner: Callable[[str], str | None]


@dataclass(frozen=True)
class LabelHit:
    # NOTE: also missing from the source; reconstructed from how LabelHit(...)
    # is instantiated later in this file (field_key=, start=, end=, label=).
    field_key: str
    start: int
    end: int
    label: str


def ocr_pdf_bytes(content: bytes) -> tuple[str, int]:
    # NOTE: the start of this function (signature + pdftoppm/dpi/render_timeout
    # setup) was missing from the source text; reconstructed to match the
    # style of ocr_image_path below and the _required_binary helper.
    pdftoppm = _required_binary("PDFTOPPM_CMD", "pdftoppm", "Poppler pdftoppm")
    dpi = os.getenv("PDF_RENDER_DPI", "300")
    render_timeout = int(os.getenv("PDF_RENDER_TIMEOUT_SECONDS", "120"))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        pdf_path = tmp_path / "input.pdf"
        output_prefix = tmp_path / "page"
        pdf_path.write_bytes(content)
        try:
            subprocess.run(
                [pdftoppm, "-r", dpi, "-png", str(pdf_path), str(output_prefix)],
                check=True,
                capture_output=True,
                text=True,
                timeout=render_timeout,
            )
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip() or "PDF rendering failed."
            raise OCRProcessingError(detail) from exc
        except subprocess.TimeoutExpired as exc:
            raise OCRProcessingError("PDF rendering timed out.") from exc

        image_paths = sorted(
            tmp_path.glob("page-*.png"),
            key=lambda path: _page_sort_key(path.name),
        )
        if not image_paths:
            return "", 0

        page_texts = [ocr_image_path(path) for path in image_paths]
        return "\n".join(page_texts), len(image_paths)


def ocr_image_bytes(content: bytes, filename: str | None = None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
        suffix = ".png"
    with tempfile.TemporaryDirectory() as tmp_dir:
        image_path = Path(tmp_dir) / f"upload{suffix}"
        image_path.write_bytes(content)
        return ocr_image_path(image_path)


def ocr_image_path(image_path: Path) -> str:
    tesseract = _required_binary("TESSERACT_CMD", "tesseract", "Tesseract OCR")
    language = os.getenv("OCR_LANGUAGE", "eng")
    psm = os.getenv("TESSERACT_PSM", "6")
    timeout = int(os.getenv("OCR_PAGE_TIMEOUT_SECONDS", "60"))
    try:
        result = subprocess.run(
            [tesseract, str(image_path), "stdout", "-l", language, "--psm", psm],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or "OCR failed."
        raise OCRProcessingError(detail) from exc
    except subprocess.TimeoutExpired as exc:
        raise OCRProcessingError("OCR timed out.") from exc
    return result.stdout


def extract_policy_fields(text: str) -> dict[str, str | None]:
    normalized_text = normalize_text(text)
    lines = split_lines(normalized_text)
    candidates = collect_label_candidates(lines)
    data = empty_policy_data()
    for spec in FIELD_SPECS:
        for candidate in candidates.get(spec.key, []):
            cleaned = spec.cleaner(candidate)
            if cleaned:
                data[spec.key] = cleaned
                break
    apply_fallbacks(data, normalized_text)
    return data


def collect_label_candidates(lines: list[str]) -> dict[str, list[str]]:
    candidates: dict[str, list[str]] = {key: [] for key in OUTPUT_KEYS}
    for index, line in enumerate(lines):
        hits = find_label_hits(line)
        hits = [hit for hit in hits if not should_skip_label_hit(lines, index, hit)]
        if not hits:
            continue
        for hit_index, hit in enumerate(hits):
            next_start = hits[hit_index + 1].start if hit_index + 1 < len(hits) else len(line)
            raw_value = line[hit.end:next_start]
            value = strip_value(raw_value)
            if not value and index + 1 < len(lines):
                next_line = lines[index + 1]
                if len(hits) == 1 and not find_label_hits(next_line):
                    value = strip_value(next_line)
            if value:
                candidates[hit.field_key].append(value)
        if index + 1 < len(lines) and len(hits) > 1:
            next_line = lines[index + 1]
            if not find_label_hits(next_line):
                for field_key, value in collect_table_row_candidates(line, next_line, hits):
                    candidates[field_key].append(value)
    return candidates


def should_skip_label_hit(lines: list[str], index: int, hit: LabelHit) -> bool:
    if hit.field_key != "insurance_company_name":
        return False
    line = lines[index]
    prefix = line[: hit.start]
    suffix = line[hit.end :]
    previous_context = " ".join(lines[max(0, index - 3) : index + 1])
    next_line = lines[index + 1] if index + 1 < len(lines) else ""
    if re.search(r"\b(?:previous|prev\.?|prior|old|expiring|expired)\b", prefix, flags=re.I):
        return True
    if re.search(r"\bprevious\s+(?:own\s+damage\s+)?(?:insurer|policy)?\b", previous_context, flags=re.I):
        return True
    if re.search(r"\bservicing\s+office\s+of\b", prefix, flags=re.I):
        return True
    if hit.label.lower().startswith("insurer") and re.match(r"\s*['\u2019]s\b", suffix, flags=re.I):
        return True
    if hit.label.lower().startswith("insurer") and re.match(
        r"\s*(?:nominee|make\s+model|vehicle\s+type|policy\s+no\.?|address)\b",
        next_line,
        flags=re.I,
    ):
        return True
    return False


def collect_table_row_candidates(
    header_line: str,
    value_line: str,
    hits: list[LabelHit],
) -> list[tuple[str, str]]:
    mapped: list[tuple[str, str]] = []
    mapped_fields: set[str] = set()
    header_cells = split_spaced_cells(header_line)
    value_cells = split_spaced_cells(value_line)
    if len(header_cells) >= 2 and len(value_cells) >= 2:
        for cell_index, (_, _, header_text) in enumerate(header_cells):
            if cell_index >= len(value_cells):
                continue
            value = strip_value(value_cells[cell_index][2])
            if not value:
                continue
            cell_hits = find_label_hits(header_text)
            for hit in cell_hits:
                if hit.field_key in mapped_fields:
                    continue
                mapped.append((hit.field_key, value))
                mapped_fields.add(hit.field_key)
        if len(mapped) >= 2:
            return mapped
    compact_mapped = collect_compact_vehicle_table_candidates(header_line, value_line, hits)
    if compact_mapped:
        return compact_mapped
    if not (re.search(r"\s{2,}", header_line) and re.search(r"\s{2,}", value_line)):
        return mapped
    for hit_index, hit in enumerate(hits):
        next_start = hits[hit_index + 1].start if hit_index + 1 < len(hits) else len(value_line)
        if hit.start >= len(value_line):
            continue
        value = strip_value(value_line[hit.start:next_start])
        if value:
            mapped.append((hit.field_key, value))
    return mapped


def collect_compact_vehicle_table_candidates(
    header_line: str,
    value_line: str,
    hits: list[LabelHit],
) -> list[tuple[str, str]]:
    field_keys = {hit.field_key for hit in hits}
    vehicle_fields = {
        "vehicle_make",
        "vehicle_model_variant_subtype",
        "fuel_type",
        "cubic_capacity",
        "idv",
        "seating_capacity",
    }
    if len(field_keys & vehicle_fields) < 2:
        return []
    tokens = value_line.split()
    if len(tokens) < 2:
        return []
    mapped: list[tuple[str, str]] = []
    fuel_index = find_fuel_token_index(tokens)
    cc_index = find_cc_token_index(tokens, start=(fuel_index + 1 if fuel_index is not None else 0))
    money_tokens = [(index, token) for index, token in enumerate(tokens) if clean_money(token)]
    if "vehicle_make" in field_keys:
        mapped.append(("vehicle_make", tokens[0]))
    if "vehicle_model_variant_subtype" in field_keys:
        end_index = fuel_index if fuel_index is not None else cc_index
        idv_token = choose_compact_idv_token(money_tokens, cc_index, fuel_index)
        if end_index is None and idv_token:
            end_index = idv_token[0]
        if end_index is not None:
            start_index = 1 if "vehicle_make" in field_keys and len(tokens) > 1 else 0
            model_value = " ".join(tokens[start_index:end_index])
            if model_value:
                mapped.append(("vehicle_model_variant_subtype", model_value))
    if "fuel_type" in field_keys and fuel_index is not None:
        mapped.append(("fuel_type", tokens[fuel_index]))
    if "seating_capacity" in field_keys:
        seating_token = choose_compact_seating_token(tokens)
        if seating_token:
            mapped.append(("seating_capacity", seating_token))
    if "cubic_capacity" in field_keys and cc_index is not None:
        mapped.append(("cubic_capacity", tokens[cc_index]))
    if "idv" in field_keys:
        idv_token = choose_compact_idv_token(money_tokens, cc_index, fuel_index)
        if idv_token:
            mapped.append(("idv", idv_token[1]))
    return mapped


def choose_compact_idv_token(
    money_tokens: list[tuple[int, str]],
    cc_index: int | None,
    fuel_index: int | None,
) -> tuple[int, str] | None:
    minimum_index = cc_index if cc_index is not None else fuel_index
    eligible = [
        (index, token)
        for index, token in money_tokens
        if minimum_index is None or index > minimum_index
    ]
    for index, token in eligible:
        amount = money_to_float(clean_money(token) or "")
        if amount is not None and is_plausible_idv_amount(amount):
            return index, token
    return None


def choose_compact_seating_token(tokens: list[str]) -> str | None:
    for token in tokens:
        seats = clean_seating_capacity(token)
        if seats:
            return seats
    return None


def find_fuel_token_index(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        if clean_fuel_type(token):
            return index
    return None


def find_cc_token_index(tokens: list[str], start: int = 0) -> int | None:
    for index, token in enumerate(tokens[start:], start=start):
        if clean_cubic_capacity(token):
            return index
    return None


def split_spaced_cells(line: str) -> list[tuple[int, int, str]]:
    cells: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\S(?:.*?\S)?(?=\s{2,}|\s*$)", line):
        text = match.group(0).strip()
        if text:
            cells.append((match.start(), match.end(), text))
    return cells


def find_label_hits(line: str) -> list[LabelHit]:
    raw_hits: list[LabelHit] = []
    for spec in FIELD_SPECS:
        for label_pattern in spec.labels:
            for match in re.finditer(label_pattern, line, flags=re.IGNORECASE):
                raw_hits.append(
                    LabelHit(
                        field_key=spec.key,
                        start=match.start(),
                        end=match.end(),
                        label=match.group(0),
                    )
                )
    raw_hits.sort(key=lambda hit: (hit.start, -(hit.end - hit.start)))
    selected: list[LabelHit] = []
    occupied_until = -1
    for hit in raw_hits:
        if hit.start < occupied_until:
            continue
        selected.append(hit)
        occupied_until = hit.end
    return selected


def empty_policy_data() -> dict[str, str | None]:
    # NOTE: definition was missing from the source; reconstructed from its
    # single call site in extract_policy_fields (data = empty_policy_data()).
    return {key: None for key in OUTPUT_KEYS}


def apply_fallbacks(data: dict[str, str | None], text: str) -> None:
    better_idv = extract_idv_candidate_from_text(text)
    if better_idv and (not data["idv"] or better_idv[0] >= 150):
        data["idv"] = better_idv[2]
    if not data["email"]:
        data["email"] = clean_email(text)
    better_insurance_company = extract_insurance_company_from_text(text)
    if better_insurance_company and should_replace_insurance_company(
        data.get("insurance_company_name"),
        better_insurance_company,
    ):
        data["insurance_company_name"] = better_insurance_company
    better_mobile = extract_mobile_from_text(text)
    if better_mobile:
        data["mobile_number"] = better_mobile
    if not data["date_of_birth"]:
        data["date_of_birth"] = extract_date_of_birth_from_text(text, data.get("policy_holder_name"))
    if not data["vehicle_registration_number"]:
        data["vehicle_registration_number"] = extract_vehicle_registration_from_text(text)
    better_model_variant = extract_vehicle_model_variant_from_text(text, data.get("vehicle_make"))
    if better_model_variant and should_replace_model_variant(data.get("vehicle_model_variant_subtype"), better_model_variant):
        data["vehicle_model_variant_subtype"] = better_model_variant
    if not data["engine_number"]:
        data["engine_number"] = extract_engine_number_from_text(text)
    if not data["chassis_number"]:
        data["chassis_number"] = extract_vin(text)
    better_net_premium = extract_premium_amount_from_text(text, "net_premium")
    if better_net_premium:
        data["net_premium"] = better_net_premium
    better_gst = extract_gst_from_text(text)
    if better_gst:
        data["gst"] = better_gst
    better_gross_premium = extract_premium_amount_from_text(text, "gross_premium")
    if better_gross_premium:
        data["gross_premium"] = better_gross_premium
    if not data["policy_type"]:
        data["policy_type"] = clean_policy_type(text)
    apply_policy_type_rules(data, text)


def apply_policy_type_rules(data: dict[str, str | None], text: str) -> None:
    health_or_life_type = infer_health_or_life_policy_type(data, text)
    if health_or_life_type:
        data["policy_type"] = health_or_life_type
        data["vehicle_registration_number"] = None
        data["gst"] = "0"
        return
    if is_motor_or_vehicle_policy(data, text):
        data["policy_type"] = "motor"
    else:
        data["vehicle_registration_number"] = None
        data["gst"] = "0"


def infer_health_or_life_policy_type(data: dict[str, str | None], text: str) -> str | None:
    if data.get("policy_type") in {"health", "life"}:
        return data["policy_type"]
    company_name = data.get("insurance_company_name") or ""
    context = f"{company_name}\n{text}"
    if re.search(
        r"\b(?:health\s+insurance|medical\s+insurance|mediclaim|hospitali[sz]ation|"
        r"critical\s+illness|patient|inpatient|care\s+health|star\s+health|niva\s+bupa)\b",
        context,
        flags=re.I,
    ):
        return "health"
    if re.search(
        r"\b(?:life\s+insurance|term\s+insurance|life\s+assured|death\s+benefit|"
        r"endowment|annuity|ulip|lic\s+of\s+india|hdfc\s+life|sbi\s+life|"
        r"icici\s+prudential\s+life|max\s+life|tata\s+aia)\b",
        context,
        flags=re.I,
    ):
        return "life"
    return None


def is_motor_or_vehicle_policy(data: dict[str, str | None], text: str) -> bool:
    if data.get("policy_type") == "motor":
        return True
    if any(
        data.get(key)
        for key in (
            "vehicle_registration_number",
            "vehicle_make",
            "vehicle_model_variant_subtype",
            "engine_number",
            "chassis_number",
            "idv",
        )
    ):
        return True
    return bool(
        re.search(
            r"\b(?:motor|vehicle|private\s+car|two\s*wheeler|bike|scooter|"
            r"commercial\s+vehicle|own\s+damage|third\s+party)\b",
            text,
            flags=re.I,
        )
    )


def normalize_text(text: str) -> str:
    replacements = {
        "\r": "\n",
        "\u00a0": " ",
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("\t", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def strip_value(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^[\s:=|#./-]+", "", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" :;-|#")
    return value


def clean_name(value: str) -> str | None:
    value = strip_value(value)
    value = re.sub(
        r"^(?:of\s+(?:the\s+)?)?(?:prospect|proposer|applicant)\s*/\s*policy\s*holder\s*:?",
        "",
        value,
        flags=re.I,
    )
    value = strip_value(value)
    month_names = (
        "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may", "jun",
        "june", "jul", "july", "aug", "august", "sep", "sept", "september", "oct", "october",
        "nov", "november", "dec", "december",
    )
    month_pattern = "|".join(month_names)
    value = re.split(
        rf"\b(?:\d{{1,2}}\s*(?:[-/.]\s*\d{{1,2}}\s*[-/.]\s*|\s+(?:{month_pattern})\s+)\d{{2,4}}|"
        r"\d{4}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2})\b",
        value,
        1,
        flags=re.I,
    )[0]
    value = re.split(r"\b(?:address|age|dob|date of birth|mobile|phone|email)\b", value, 1, flags=re.I)[0]
    value = value.strip(" :;-|#,")
    if not value or is_null_value(value):
        return None
    if len(value) < 2 or len(value) > 100:
        return None
    if sum(char.isdigit() for char in value) > 2:
        return None
    return value


def clean_mobile_number(value: str) -> str | None:
    value = strip_value(value)
    candidates = extract_mobile_candidates(value)
    if candidates:
        return candidates[0][0]
    return None


def extract_mobile_from_text(text: str) -> str | None:
    scored: list[tuple[int, int, str]] = []
    for line_index, line in enumerate(split_lines(text)):
        for mobile, start, end in extract_mobile_candidates(line):
            context = f"{line[max(0, start - 60):start]} {line[end:end + 30]}".lower()
            score = 10
            if has_mobile_label(context):
                score += 100
            if has_non_mobile_number_context(context):
                score -= 120
            scored.append((score, -line_index, mobile))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][2] if scored[0][0] > -50 else None


def extract_date_of_birth_from_text(text: str, policy_holder_name: str | None = None) -> str | None:
    lines = split_lines(text)
    normalized_name = normalize_name_for_matching(policy_holder_name)
    if normalized_name:
        for index, line in enumerate(lines):
            if normalized_name in normalize_name_for_matching(line):
                context = " ".join(lines[max(0, index - 2) : min(len(lines), index + 2)])
                if not has_date_of_birth_label(context):
                    continue
                date_of_birth = clean_date_of_birth(line)
                if date_of_birth:
                    return date_of_birth
    for index, line in enumerate(lines):
        if not has_date_of_birth_label(line):
            continue
        previous_line = lines[index - 1] if index > 0 else ""
        previous_line_has_holder = bool(
            normalized_name and normalized_name in normalize_name_for_matching(previous_line)
        )
        for value_line in lines[index + 1 : index + 6]:
            if normalized_name:
                value_line_has_holder = normalized_name in normalize_name_for_matching(value_line)
                if not value_line_has_holder and not previous_line_has_holder:
                    continue
            date_of_birth = clean_date_of_birth(value_line)
            if date_of_birth:
                return date_of_birth
    return None


def normalize_name_for_matching(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def has_date_of_birth_label(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:date\s*of\s*birth|d\.?\s*o\.?\s*b\.?|dob|birth\s*date)\b",
            value,
            flags=re.I,
        )
    )


def extract_mobile_candidates(value: str) -> list[tuple[str, int, int]]:
    patterns = (
        re.compile(r"(?<![A-Za-z0-9])(?:\+?\s*91[ .()-]*)?[6-9](?:[ .()-]*\d){9}(?![ .()-]*\d)"),
        re.compile(r"(?<![A-Za-z0-9])0[6-9](?:[ .()-]*\d){9}(?![ .()-]*\d)"),
    )
    candidates: list[tuple[str, int, int]] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(value):
            normalized = normalize_mobile_number(match.group(0))
            if normalized and normalized not in seen:
                candidates.append((normalized, match.start(), match.end()))
                seen.add(normalized)
    return candidates


def normalize_mobile_number(value: str) -> str | None:
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("0") and digits[1] in "6789":
        return digits[1:]
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return f"+{digits}"
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return None


def has_mobile_label(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:mobile|mob|contact|phone|telephone|cell|whatsapp|registered\s+mobile)\b",
            value,
            flags=re.I,
        )
    )


def has_non_mobile_number_context(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:policy|engine|chassis|vin|idv|premium|gst|tax|registration|regn|"
            r"account|receipt|invoice|proposal)\b",
            value,
            flags=re.I,
        )
    )


def clean_date_of_birth(value: str) -> str | None:
    value = strip_value(value)
    if is_null_value(value):
        return None
    numeric = re.search(r"\b(\d{4})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{1,2})\b", value)
    if numeric:
        year, month, day = map(int, numeric.groups())
        return safe_iso_date(year, month, day)
    numeric = re.search(r"\b(\d{1,2})\s*[-/.]\s*(\d{1,2})\s*[-/.]\s*(\d{2,4})\b", value)
    if numeric:
        first, second, year = map(int, numeric.groups())
        if year < 100:
            year += 1900 if year > 30 else 2000
        day, month = first, second
        if first <= 12 and second > 12:
            month, day = first, second
        return safe_iso_date(year, month, day)
    month_names = (
        "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may", "jun",
        "june", "jul", "july", "aug", "august", "sep", "sept", "september", "oct", "october",
        "nov", "november", "dec", "december",
    )
    month_pattern = "|".join(month_names)
    date_separator = r"(?:\s+|\s*[-/.]\s*)"
    # NOTE: this regex was cut off mid-pattern in the source (it broke off
    # after "(\d{{2" with the rest of the file missing). Reconstructed to
    # match a "12 January 2024"-style date, consistent with month_number()
    # and normalize_year() below, which exist but were otherwise unused.
    word_date = re.search(
        rf"\b(\d{{1,2}}){date_separator}({month_pattern}){date_separator}(\d{{2,4}})\b",
        value,
        flags=re.I,
    )
    if word_date:
        day = int(word_date.group(1))
        month = month_number(word_date.group(2))
        year = normalize_year(int(word_date.group(3)))
        return safe_iso_date(year, month, day)
    return None


def clean_email(value: str) -> str | None:
    value = strip_value(value)
    match = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", value, flags=re.I)
    if not match:
        return None
    return match.group(0).lower()


def clean_insurance_company_name(value: str) -> str | None:
    value = strip_value(value)
    value = re.split(
        r"\b(?:policy|proposal|certificate|customer|insured|proposer|address|mobile|phone|"
        r"email|vehicle|registration|engine|chassis|premium|gst|idv|sum\s*insured)\b",
        value,
        1,
        flags=re.I,
    )[0]
    value = re.sub(r"\s+", " ", value).strip(" :;-|#,.")
    if not value or is_null_value(value):
        return None
    if is_insurer_sentence_fragment(value):
        return None
    if is_policy_product_text(value):
        return None
    if len(value) < 3 or len(value) > 140:
        return None
    if sum(char.isdigit() for char in value) > 2:
        return None
    if not re.search(r"[A-Za-z]", value):
        return None
    return value


def extract_insurance_company_from_text(text: str) -> str | None:
    lines = split_lines(text)
    label_pattern = (
        r"\b(?:insurance\s*company|insurer(?!\s*['\u2019]s)|insurance\s*provider|policy\s*issuer|issuer|"
        r"underwritten\s*by|underwriter|issued\s*by)\s*(?:name)?\.?"
        r"(?=\s|[:;|#,-]|$)"
    )
    for index, line in enumerate(lines):
        label_match = re.search(label_pattern, line, flags=re.I)
        if not label_match:
            continue
        label_hit = LabelHit(
            field_key="insurance_company_name",
            start=label_match.start(),
            end=label_match.end(),
            label=label_match.group(0),
        )
        if should_skip_label_hit(lines, index, label_hit):
            continue
        if line[:label_match.start()].strip(" :;-|#,."):
            continue
        raw_same_line_value = line[label_match.end():]
        if is_insurer_sentence_fragment(raw_same_line_value):
            continue
        known_same_line_company = match_known_insurance_company(raw_same_line_value) or match_known_insurance_company(line)
        if known_same_line_company:
            return known_same_line_company
        same_line_value = clean_insurance_company_name(raw_same_line_value)
        if same_line_value:
            return same_line_value
        if index + 1 < len(lines) and not find_label_hits(lines[index + 1]):
            known_next_line_company = match_known_insurance_company(lines[index + 1])
            if known_next_line_company:
                return known_next_line_company
            next_line_value = clean_insurance_company_name(lines[index + 1])
            if next_line_value:
                return next_line_value
    current_context_company = match_known_insurance_company_in_current_policy_context(lines)
    if current_context_company:
        return current_context_company
    known_company = match_known_insurance_company(text)
    if known_company:
        return known_company
    for line in lines:
        if not re.search(r"\b(?:insurance|assurance|reinsurance)\b", line, flags=re.I):
            continue
        if not re.search(r"\b(?:company|co\.?|limited|ltd\.?)\b", line, flags=re.I):
            continue
        cleaned = clean_insurance_company_name(line)
        if cleaned:
            return cleaned
    company_pattern = re.compile(
        r"\b([A-Z][A-Za-z&.'() -]{2,120}?"
        r"(?:Insurance|Assurance|Life\s+Insurance|General\s+Insurance|Health\s+Insurance|"
        r"Reinsurance)"
        r"[A-Za-z&.'() -]{0,80}?"
        r"(?:Company\s+Limited|Company|Co\.?\s*Ltd\.?|Limited|Ltd\.?))\b",
        flags=re.I,
    )
    for line in lines:
        match = company_pattern.search(line)
        if not match:
            continue
        cleaned = clean_insurance_company_name(match.group(1))
        if cleaned:
            return cleaned
    return None


def match_known_insurance_company_in_current_policy_context(lines: list[str]) -> str | None:
    for index, line in enumerate(lines):
        combined_line = " ".join(lines[index : index + 2])
        company_name = match_known_insurance_company(combined_line)
        if not company_name:
            continue
        context = " ".join(lines[max(0, index - 3) : min(len(lines), index + 4)])
        if is_previous_insurer_context(context):
            continue
        if is_current_policy_company_context(context):
            return company_name
    return None


def is_previous_insurer_context(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:previous\s+(?:own\s+damage\s+)?(?:insurer|policy|liability)|"
            r"prev\.?\s+(?:insurer|policy)|prior\s+(?:insurer|policy)|"
            r"old\s+(?:insurer|policy)|expiring\s+(?:insurer|policy)|"
            r"third\s+party\s+policy|insured\s+by)\b",
            value,
            flags=re.I,
        )
    )


def is_current_policy_company_context(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:preferred\s+insurance\s+partner|for\s*&\s*on\s+behalf\s+of|"
            r"powered\s+by|certificate\s+cum\s+policy|policy\s+schedule|"
            r"package\s+policy|stand[-\s]*alone\s+own\s+damage\s+policy|"
            r"irdai\s+registration|form\s+51|product\s*:)\b",
            value,
            flags=re.I,
        )
    )


def is_insurer_sentence_fragment(value: str) -> bool:
    normalized = strip_value(value).lower()
    if not normalized:
        return False
    if re.match(
        r"^(?:has|have|had|is|are|was|were|will|shall|may|can|must|should|would|could)\b",
        normalized,
    ):
        return True
    if re.search(r"\b(?:received|cleared\s+funds|dishono[u]?r|cancelled\s+ab\s+initio)\b", normalized):
        return True
    if re.search(r"\b(?:has\s+been\s+successfully|rules?\s*&\s*regulations)\b", normalized):
        return True
    if re.match(r"^(?:ltd|limited|co\.?\s*ltd\.*?)\b", normalized):
        return True
    if re.match(r"^(?:['\"]s\s*)?(?:web\s*site|website|site)\b", normalized):
        return True
    return False


def is_policy_product_text(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value).strip(" .,;:-\"").lower()
    return bool(
        re.fullmatch(
            r"(?:"
            r"health\s+insurance|life\s+insurance|motor\s+insurance|vehicle\s+insurance|"
            r"private\s+car(?:\s+package)?(?:\s+policy)?|two\s+wheeler(?:\s+package)?(?:\s+policy)?|"
            r"commercial\s+vehicle(?:\s+package)?(?:\s+policy)?|package\s+policy|policy"
            r")",
            normalized,
        )
    )


def match_known_insurance_company(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", value)
    # NOTE: source called `.items()` on KNOWN_INSURANCE_COMPANY_PATTERNS, but
    # that constant is a tuple of (name, patterns) pairs, not a dict — tuples
    # have no .items(). Fixed to iterate the tuple directly.
    for company_name, patterns in KNOWN_INSURANCE_COMPANY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, normalized, flags=re.I):
                return company_name
    return None


def should_replace_insurance_company(current: str | None, candidate: str) -> bool:
    if not current:
        return True
    current_clean = current.strip().lower()
    candidate_clean = candidate.strip().lower()
    if current_clean in {"limited", "ltd", "company", "company limited", "co ltd", "co. ltd"}:
        return True
    if current_clean in candidate_clean and len(candidate_clean) > len(current_clean) + 5:
        return True
    if re.search(r"\b(?:insurance|assurance|reinsurance|insurer)\b", candidate_clean) and not re.search(
        r"\b(?:insurance|assurance|reinsurance|insurer)\b",
        current_clean,
    ):
        return True
    return False


def clean_vehicle_registration(value: str) -> str | None:
    value = strip_value(value).upper()
    registration = extract_vehicle_registration(value)
    if registration:
        return registration
    compact = re.sub(r"[^A-Z0-9]", "", value)
    if is_vehicle_registration_shape(compact):
        return compact
    return None


def is_vehicle_registration_shape(value: str) -> bool:
    return bool(
        re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4}", value)
        or re.fullmatch(r"[A-Z]{2}\d{1,2}\d{1,4}", value)
        or re.fullmatch(r"\d{2}BH\d{4}[A-Z]{1,2}", value)
    )


def extract_vehicle_registration_from_text(text: str) -> str | None:
    lines = split_lines(text)
    for index, line in enumerate(lines):
        label_match = re.search(
            r"\b(?:vehicle\s*)?(?:registration|regn\.?|reg\.?)\s*(?:no|number|num|#)?\.?\b|"
            r"\bregistration\s*mark\b|\bvehicle\s*(?:no|number|num)\.?\b",
            line,
            flags=re.I,
        )
        if not label_match:
            continue
        same_line_value = clean_vehicle_registration(line[label_match.end() :])
        if same_line_value:
            return same_line_value
        if index + 1 < len(lines):
            next_line_value = clean_vehicle_registration(lines[index + 1])
            if next_line_value:
                return next_line_value
    return extract_unlabeled_vehicle_registration(lines)


def extract_unlabeled_vehicle_registration(lines: list[str]) -> str | None:
    for line in lines:
        if has_conflicting_identifier_label(line):
            continue
        registration = extract_vehicle_registration(line)
        if registration:
            return registration
    return None


def has_conflicting_identifier_label(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:engine|eng\.?|motor|chassis|chasis|vin)\s*(?:no|number|num|#)?\.?"
            r"(?=\s|[.,;:#/-]|$)",
            value,
            flags=re.I,
        )
    )


def extract_vehicle_registration(value: str) -> str | None:
    patterns = (
        r"\b\d{2}[\s-]?BH[\s-]?\d{4}[\s-]?[A-Z]{1,2}\b",
        r"\b[A-Z]{2}[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{1,4}\b",
        r"\b[A-Z]{2}[\s-]?\d{1,2}[\s-]?\d{1,4}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, value.upper())
        if match:
            return re.sub(r"[^A-Z0-9]", "", match.group(0))
    return None


def clean_vehicle_make(value: str) -> str | None:
    return clean_vehicle_text(
        value,
        stop_pattern=(
            r"\b(?:model|variant|sub\s*type|subtype|fuel|seating|seat|cubic|cc|"
            r"engine|chassis|idv|registration|regn|manufacturing|mfg)\b"
        ),
        max_len=60,
    )


def clean_vehicle_model_variant_subtype(value: str) -> str | None:
    return clean_vehicle_text(
        value,
        stop_pattern=(
            r"\b(?:fuel|seating|seat|cubic|cc|engine|chassis|idv|registration|"
            r"regn|manufacturing|mfg|year\s*of\s*regn|year\s*of\s*registration)\b"
        ),
        max_len=100,
    )


def clean_vehicle_text(value: str, stop_pattern: str, max_len: int) -> str | None:
    value = strip_value(value)
    value = re.split(stop_pattern, value, 1, flags=re.I)[0]
    value = value.strip(" :,|-#,/")
    value = re.sub(r"\s+", " ", value)
    if not value or is_null_value(value):
        return None
    if len(value) > max_len or not re.search(r"[A-Za-z]", value):
        return None
    return value


def extract_vehicle_model_variant_from_text(text: str, vehicle_make: str | None = None) -> str | None:
    lines = split_lines(text)
    label_patterns = (
        r"\bmake\s*/\s*model\s*/\s*variant\b",
        r"\bmodel\s*/\s*(?:vehicle\s*)?variant(?:\s*\(\s*sub\s*type\s*\)|\s*\(\s*subtype\s*\))?",
        r"\bmodel\s*/\s*variant(?:\s*\(\s*sub\s*type\s*\)|\s*\(\s*subtype\s*\))?",
        r"\bvariant\s*/\s*sub\s*type\b",
        r"\bvariant\s*/\s*subtype\b",
        r"\bvehicle\s*model\b",
        r"\bmodel\s*name\b",
        r"\bmodel\s*variant\b",
        r"\bvariant(?:\s*\(\s*sub\s*type\s*\)|\s*\(\s*subtype\s*\))?",
        r"\bsub\s*type\b",
        r"\bsubtype\b",
        r"\bmodel\b(?!\s*year)",
    )
    for index, line in enumerate(lines):
        for pattern in label_patterns:
            match = re.search(pattern, line, flags=re.I)
            if not match:
                continue
            value = strip_value(line[match.end() :])
            if not value and index + 1 < len(lines) and not find_label_hits(lines[index + 1]):
                value = strip_value(lines[index + 1])
            cleaned = clean_vehicle_model_variant_subtype(value)
            if cleaned:
                return cleaned
    if vehicle_make:
        make_pattern = re.escape(vehicle_make.strip())
        for line in lines:
            if not re.search(make_pattern, line, flags=re.I):
                continue
            cleaned = clean_vehicle_model_from_row(line, vehicle_make)
            if cleaned:
                return cleaned
    return None


def should_replace_model_variant(current: str | None, candidate: str) -> bool:
    if is_placeholder_model_variant(candidate):
        return False
    if not current:
        return True
    if re.match(r"^(?:variant|sub\s*type|subtype)\s*[:/-]", current, flags=re.I):
        return True
    return False


def is_placeholder_model_variant(value: str) -> bool:
    return value.strip().lower() in {"model", "variant", "subtype", "sub type", "vehicle variant"}


def clean_vehicle_model_from_row(line: str, vehicle_make: str) -> str | None:
    value = re.sub(re.escape(vehicle_make), " ", line, count=1, flags=re.I)
    value = re.sub(r"\b[A-Z]{2}[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{1,4}\b", " ", value, flags=re.I)
    value = re.sub(r"\b(?:petrol|diesel|cng|lpg|electric|ev|hybrid)\b", " ", value, flags=re.I)
    value = re.sub(r"\b(?:19|20)\d{2}\b", " ", value)
    value = re.sub(r"\b\d{2,8}(?:\.\d{1,2})?\b", " ", value)
    value = re.sub(r"\b[A-HJ-NPR-Z0-9]{17}\b", " ", value, flags=re.I)
    return clean_vehicle_model_variant_subtype(value)


def clean_seating_capacity(value: str) -> str | None:
    value = strip_value(value)
    match = re.search(r"\b([1-9]\d?)\b", value)
    if not match:
        return None
    seats = int(match.group(1))
    if 1 <= seats <= 99:
        return str(seats)
    return None


def clean_fuel_type(value: str) -> str | None:
    value = strip_value(value)
    value = re.split(
        r"\b(?:seating|seat|cubic|cc|engine|chassis|idv|registration|regn|manufacturing|mfg)\b",
        value,
        1,
        flags=re.I,
    )[0]
    lowered = value.lower()
    fuel_patterns = (
        ("petrol/cng", r"\b(?:petrol\s*/\s*cng|cng\s*/\s*petrol|petrol\s*\+\s*cng|cng\s*\+\s*petrol)\b"),
        ("petrol/lpg", r"\b(?:petrol\s*/\s*lpg|lpg\s*/\s*petrol|petrol\s*\+\s*lpg|lpg\s*\+\s*petrol)\b"),
        ("diesel", r"\bdiesel\b"),
        ("petrol", r"\bpetrol\b"),
        ("cng", r"\bcng\b"),
        ("lpg", r"\blpg\b"),
        ("electric", r"\b(?:electric|ev|battery)\b"),
        ("hybrid", r"\bhybrid\b"),
    )
    for fuel, pattern in fuel_patterns:
        if re.search(pattern, lowered):
            return fuel
    return None


def clean_year_value(value: str) -> str | None:
    value = strip_value(value)
    current_year = date.today().year
    for match in re.finditer(r"\b((?:19|20)\d{2})\b", value):
        year = int(match.group(1))
        if 1900 <= year <= current_year + 1:
            return str(year)
    return None


def clean_cubic_capacity(value: str) -> str | None:
    value = strip_value(value)
    for amount, _, _ in extract_money_matches(value):
        numeric_amount = money_to_float(amount)
        if numeric_amount is None:
            continue
        cc = int(numeric_amount)
        if 50 <= cc <= 10000:
            return str(cc)
    match = re.search(r"\b([1-9]\d{1,4})\s*(?:cc|c\.c\.|cubic)?\b", value, flags=re.I)
    if not match:
        return None
    cc = int(match.group(1))
    if 50 <= cc <= 10000:
        return str(cc)
    return None


def clean_engine_number(value: str) -> str | None:
    value = strip_value(value)
    value = re.sub(ENGINE_LABEL_PATTERN, "", value, count=1, flags=re.I)
    value = strip_value(value)
    value = re.split(
        r"\b(?:chassis|chasis|vin|vehicle\s*identification|registration|regn|make|model|"
        r"variant|fuel|idv|policy|premium|sum\s*insured|seating|cubic|cc|mobile|phone|"
        r"email|date\s*of\s*birth|dob)\b",
        value,
        1,
        flags=re.I,
    )[0]
    return clean_identifier(value, min_len=5, max_len=30)


def extract_engine_number_from_text(text: str) -> str | None:
    lines = split_lines(text)
    for index, line in enumerate(lines):
        label_match = re.search(ENGINE_LABEL_PATTERN, line, flags=re.I)
        if not label_match:
            continue
        line_hits = find_label_hits(line)
        same_line_value = clean_engine_number(line[label_match.end() :])
        if same_line_value:
            return same_line_value
        if index + 1 < len(lines) and len(line_hits) <= 1:
            next_line_value = clean_engine_number(lines[index + 1])
            if next_line_value:
                return next_line_value
    for index, line in enumerate(lines[:-1]):
        hits = find_label_hits(line)
        if not any(hit.field_key == "engine_number" for hit in hits):
            continue
        if find_label_hits(lines[index + 1]):
            continue
        table_value = extract_engine_number_from_identifier_table(line, lines[index + 1], hits)
        if table_value:
            return table_value
    return None


def extract_engine_number_from_identifier_table(
    header_line: str,
    value_line: str,
    hits: list[LabelHit],
) -> str | None:
    header_cells = split_spaced_cells(header_line)
    value_cells = split_spaced_cells(value_line)
    if len(header_cells) >= 2 and len(value_cells) >= 2:
        for cell_index, (_, _, header_text) in enumerate(header_cells):
            if cell_index >= len(value_cells):
                continue
            if any(hit.field_key == "engine_number" for hit in find_label_hits(header_text)):
                cleaned = clean_engine_number(value_cells[cell_index][2])
                if cleaned:
                    return cleaned
    identifier_hits = [
        hit for hit in hits if hit.field_key in {"vehicle_registration_number", "engine_number", "chassis_number"}
    ]
    if len(identifier_hits) < 2:
        return None
    engine_index = next(
        (index for index, hit in enumerate(identifier_hits) if hit.field_key == "engine_number"),
        None,
    )
    if engine_index is None:
        return None
    tokens = [token for token in value_line.split() if clean_identifier(token, min_len=5, max_len=30)]
    if engine_index >= len(tokens):
        return None
    return clean_engine_number(tokens[engine_index])


def clean_chassis_number(value: str) -> str | None:
    value = strip_value(value).upper()
    vin = extract_vin(value)
    if vin:
        return vin
    return clean_identifier(value, min_len=8, max_len=30)


def extract_vin(value: str) -> str | None:
    match = re.search(r"\b[A-HJ-NPR-Z0-9]{17}\b", value.upper())
    if not match:
        return None
    return match.group(0)


def clean_identifier(value: str, min_len: int, max_len: int) -> str | None:
    value = strip_value(value).upper()
    value = re.split(r"\b(?:make|model|variant|fuel|registration|regn|mfg)\b", value, 1, flags=re.I)[0]
    compact = re.sub(r"[^A-Z0-9/-]", "", value)
    if min_len <= len(compact) <= max_len and re.search(r"\d", compact):
        return compact
    return None


def clean_money(value: str) -> str | None:
    value = strip_value(value)
    if is_null_value(value):
        return None
    matches = extract_money_matches(value)
    if not matches:
        return None
    return matches[0][0]


def clean_sum_insured(value: str) -> str | None:
    value = strip_value(value)
    if is_null_value(value):
        return None
    shorthand = extract_lakh_amount(value)
    if shorthand:
        return shorthand
    return clean_money(value)


def extract_lakh_amount(value: str) -> str | None:
    match = re.search(
        r"\b(\d+(?:\.\d{1,2})?)\s*(?:lacs?|lakhs?|lac|lakh|l)\b",
        value,
        flags=re.I,
    )
    if not match:
        return None
    amount = money_to_float(match.group(1))
    if amount is None:
        return None
    return format_money_amount(amount * 100000)


def clean_premium_amount(value: str) -> str | None:
    value = strip_value(value)
    if is_null_value(value):
        return None
    matches = extract_premium_money_matches(value)
    if not matches:
        return None
    return matches[0][0]


def extract_premium_amount_from_text(text: str, field_key: str) -> str | None:
    candidates: list[tuple[int, int, str]] = []
    lines = split_lines(text)
    patterns = PREMIUM_LABEL_PATTERNS[field_key]
    for index, line in enumerate(lines):
        for pattern_index, pattern in enumerate(patterns):
            for match in re.finditer(pattern, line, flags=re.I):
                context = premium_context_after_label(line, match.end())
                if not extract_premium_money_matches(context) and index + 1 < len(lines):
                    next_line = lines[index + 1]
                    if not find_label_hits(next_line):
                        context = next_line
                for amount, start, _ in extract_premium_money_matches(context):
                    numeric_amount = money_to_float(amount)
                    if numeric_amount is None or not is_plausible_premium_amount(numeric_amount):
                        continue
                    score = 100 - min(40, start) - (pattern_index * 3)
                    if field_key == "gross_premium" and re.search(r"\b(?:gross|total|payable|final)\b", match.group(0), flags=re.I):
                        score += 20
                    if field_key == "net_premium" and re.search(r"\bnet\b|\bbefore\s+tax\b", match.group(0), flags=re.I):
                        score += 20
                    candidates.append((score, int(numeric_amount), amount))
    table_value = extract_premium_amount_from_table(lines, field_key)
    if table_value:
        candidates.append((140, int(money_to_float(table_value) or 0), table_value))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def extract_gst_from_text(text: str) -> str | None:
    explicit_gst = extract_premium_amount_from_text(text, "gst")
    component_amounts: list[float] = []
    for line in split_lines(text):
        for pattern in GST_COMPONENT_LABEL_PATTERNS:
            for match in re.finditer(pattern, line, flags=re.I):
                context = premium_context_after_label(line, match.end())
                money_matches = extract_premium_money_matches(context)
                if not money_matches:
                    continue
                amount = money_to_float(money_matches[0][0])
                if amount is not None and is_plausible_premium_amount(amount):
                    component_amounts.append(amount)
    if explicit_gst:
        return explicit_gst
    if component_amounts:
        return format_money_amount(sum(component_amounts))
    return None


def premium_context_after_label(line: str, label_end: int) -> str:
    context = line[label_end:]
    next_label = next_premium_label_match(context)
    if not next_label:
        return context
    before_next_label = context[:next_label.start()]
    if extract_premium_money_matches(before_next_label):
        return before_next_label
    return context


def next_premium_label_match(value: str) -> re.Match[str] | None:
    matches = [
        match
        for patterns in PREMIUM_LABEL_PATTERNS.values()
        for pattern in patterns
        for match in re.finditer(pattern, value, flags=re.I)
    ]
    if not matches:
        return None
    matches.sort(key=lambda match: match.start())
    return matches[0]


def extract_premium_amount_from_table(lines: list[str], field_key: str) -> str | None:
    for index, line in enumerate(lines[:-1]):
        hits = find_label_hits(line)
        premium_hits = [hit for hit in hits if hit.field_key in PREMIUM_FIELD_KEYS]
        if len(premium_hits) < 2:
            continue
        if find_label_hits(lines[index + 1]):
            continue
        field_index = next(
            (hit_index for hit_index, hit in enumerate(premium_hits) if hit.field_key == field_key),
            None,
        )
        if field_index is None:
            continue
        amounts = [amount for amount, _, _ in extract_premium_money_matches(lines[index + 1])]
        if field_index < len(amounts):
            return amounts[field_index]
    return None


def extract_premium_money_matches(value: str) -> list[tuple[str, int, int]]:
    matches: list[tuple[str, int, int]] = []
    for amount, start, end in extract_money_matches(value):
        if re.match(r"\s*%", value[end:end + 3]):
            continue
        if value[max(0, start - 3):start].strip().endswith("@"):
            continue
        matches.append((amount, start, end))
    return matches


def is_plausible_premium_amount(amount: float) -> bool:
    return 1 <= amount <= 100000000


def format_money_amount(amount: float) -> str:
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def clean_idv(value: str) -> str | None:
    value = strip_value(value)
    if is_null_value(value):
        return None
    candidates = score_idv_amounts(value)
    if not candidates:
        return None
    return candidates[0][2]


def extract_idv_from_text(text: str) -> str | None:
    candidate = extract_idv_candidate_from_text(text)
    return candidate[2] if candidate else None


def extract_idv_candidate_from_text(text: str) -> tuple[int, int, str] | None:
    best_candidates: list[tuple[int, int, str]] = []
    lines = split_lines(text)
    for index, line in enumerate(lines):
        context = line
        if is_total_line(line) and index + 1 < len(lines) and has_idv_label(lines[index + 1]):
            context = f"{context} {lines[index + 1]}"
            if index + 2 < len(lines) and not has_blocking_money_label(lines[index + 2]):
                context = f"{context} {lines[index + 2]}"
        elif not has_idv_label(line):
            continue
        if index + 1 < len(lines) and not has_blocking_money_label(lines[index + 1]):
            context = f"{context} {lines[index + 1]}"
        best_candidates.extend(score_idv_amounts(context))
    if not best_candidates:
        return None
    best_candidates.sort(reverse=True)
    return best_candidates[0]


def score_idv_amounts(value: str) -> list[tuple[int, int, str]]:
    matches = extract_money_matches(value)
    if not matches:
        return []
    scored: list[tuple[int, int, str]] = []
    for amount, start, end in matches:
        numeric_amount = money_to_float(amount)
        if numeric_amount is None or not is_plausible_idv_amount(numeric_amount):
            continue
        before = value[max(0, start - 120):start].lower()
        after = value[end:end + 40].lower()
        label_match = last_idv_label_match(before)
        if label_match and has_blocking_money_label(before[label_match.end():]):
            continue
        if has_premium_or_tax_context(before, after) and not label_match:
            continue
        score = 10
        if label_match:
            score += 80
            score -= min(40, len(before) - label_match.end())
        if re.search(r"\btotal\s+idv(?:\s+value)?\b", before, flags=re.I):
            score += 70
        elif re.search(r"\bidv\s+value\s+of\s+vehicle\b|\bvalue\s+of\s+vehicle\s+idv\b", before, flags=re.I):
            score += 65
        elif re.search(r"\binsured\s+declared\s+value\b", before, flags=re.I):
            score += 55
        elif re.search(r"\bdeclared\s+value\b", before, flags=re.I):
            score += 45
        elif re.search(r"\bvehicle\s+idv(?:\s+value)?\b", before, flags=re.I):
            score += 35
        elif re.search(r"\bidv(?:\s+value)?\b", before, flags=re.I):
            score += 25
        if has_premium_or_tax_context(before, after):
            score -= 70
        scored.append((score, int(numeric_amount), amount))
    scored.sort(reverse=True)
    return scored


def is_plausible_idv_amount(amount: float) -> bool:
    return MIN_IDV_AMOUNT <= amount <= 100000000


def is_total_line(value: str) -> bool:
    return bool(re.fullmatch(r"\s*total\s*[:#-]?\s*", value, flags=re.I))


def extract_money_matches(value: str) -> list[tuple[str, int, int]]:
    pattern = re.compile(
        r"(?:rs\.?|inr|\u20b9)?\s*((?:\d{1,3})(?:,\d{2,3})+|\d+)(?:\.\d{1,2})?",
        flags=re.I,
    )
    matches: list[tuple[str, int, int]] = []
    for match in pattern.finditer(value):
        amount = re.sub(r",", "", match.group(1))
        if re.fullmatch(r"\d+(?:\.\d{1,2})?", amount):
            matches.append((amount, match.start(1), match.end(1)))
    return matches


def money_to_float(amount: str) -> float | None:
    try:
        return float(amount)
    except ValueError:
        return None


def has_idv_label(value: str) -> bool:
    return bool(
        re.search(
            r"\btotal\s+idv(?:\s+value)?\b|"
            r"\bidv\s+value\s+of\s+vehicle\b|\bvalue\s+of\s+vehicle\s+idv\b|"
            r"\b(?:total\s+)?idv(?:\s+value)?\b|\bvehicle\s+idv(?:\s+value)?\b|"
            r"\binsured\s+declared\s+value\b|\bdeclared\s+value\b",
            value,
            flags=re.I,
        )
    )


def last_idv_label_match(value: str) -> re.Match[str] | None:
    matches = list(
        re.finditer(
            r"\btotal\s+idv(?:\s+value)?\b|"
            r"\bidv\s+value\s+of\s+vehicle\b|\bvalue\s+of\s+vehicle\s+idv\b|"
            r"\b(?:total\s+)?idv(?:\s+value)?\b|\bvehicle\s+idv(?:\s+value)?\b|"
            r"\binsured\s+declared\s+value\b|\bdeclared\s+value\b",
            value,
            flags=re.I,
        )
    )
    return matches[-1] if matches else None


def has_blocking_money_label(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:premium|gst|tax|ncb|discount|deductible|loading|od\s+premium|net\s+premium|gross\s+premium)\b",
            value,
            flags=re.I,
        )
    )


def has_premium_or_tax_context(before: str, after: str) -> bool:
    context = f"{before[-45:]} {after[:30]}"
    return has_blocking_money_label(context)


def clean_policy_type(value: str) -> str | None:
    value = strip_value(value)
    if is_null_value(value):
        return None
    lowered = value.lower()
    scores = {
        "motor": count_terms(
            lowered,
            (
                "motor", "vehicle", "car", "two wheeler", "bike", "scooter",
                "commercial vehicle", "private car", "third party", "own damage",
                "engine", "chassis", "registration", "regn",
            ),
        ),
        "health": count_terms(
            lowered,
            (
                "health", "medical", "mediclaim", "hospital", "hospitalisation",
                "hospitalization", "critical illness", "patient", "inpatient",
            ),
        ),
        "life": count_terms(
            lowered,
            (
                "life", "term", "endowment", "ulip", "annuity", "life assured", "death benefit",
            ),
        ),
    }
    best_type, best_score = max(scores.items(), key=lambda item: item[1])
    return best_type if best_score > 0 else None


def count_terms(text: str, terms: Iterable[str]) -> int:
    return sum(1 for term in terms if re.search(rf"\b{re.escape(term)}\b", text))


def safe_iso_date(year: int, month: int, day: int) -> str | None:
    try:
        parsed = date(year, month, day)
    except ValueError:
        return None
    return parsed.isoformat()


def normalize_year(year: int) -> int:
    if year < 100:
        return year + 1900 if year > 30 else year + 2000
    return year


def month_number(month: str) -> int:
    lookup = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
        "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    return lookup[month.lower()]


def is_null_value(value: str) -> bool:
    return value.strip().lower() in {"", "-", "--", "na", "n/a", "nil", "none", "not available"}


def _required_binary(env_var: str, default_name: str, display_name: str) -> str:
    configured = _find_binary(env_var, default_name)
    if configured:
        return configured
    raise OCREngineUnavailableError(
        f"{display_name} is required for OCR. Install it or set {env_var}."
    )


def _find_binary(env_var: str, default_name: str) -> str | None:
    configured = os.getenv(env_var)
    if configured:
        return configured
    local_binary = LOCAL_OCR_BIN / default_name
    if local_binary.exists():
        return str(local_binary)
    return shutil.which(default_name)


def _page_sort_key(name: str) -> tuple[int, str]:
    match = re.search(r"-(\d+)\.png$", name)
    if match:
        return int(match.group(1)), name
    return 0, name


# ---------------------------------------------------------------------------
# Public entry points
#
# NOTE: everything in this section (ExtractionResult, PDF/image content-type
# and extension tables, detect_source_type, extract_text_from_pdf, and both
# extract_from_bytes and get_ocr_engine_status) was entirely absent from the
# source file even though main.py imports extract_from_bytes and
# get_ocr_engine_status directly, ExtractionResult's attributes (data,
# source_type, used_ocr, pages_processed, missing_fields, warnings) are read
# by main.py, and pdfplumber / PIL.Image were imported at the top of the file
# but never referenced anywhere else. Reconstructed from those call sites.
# ---------------------------------------------------------------------------

MIN_EXTRACTABLE_TEXT_CHARS = int(os.getenv("MIN_EXTRACTABLE_TEXT_CHARS", "40"))

PDF_CONTENT_TYPES = {"application/pdf"}
IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/bmp",
    "image/tiff",
}
PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass(frozen=True)
class ExtractionResult:
    data: dict[str, str | None]
    source_type: SourceType
    used_ocr: bool
    pages_processed: int
    missing_fields: list[str]
    warnings: list[str]


def detect_source_type(filename: str | None, content_type: str | None) -> SourceType:
    normalized_content_type = (content_type or "").lower().split(";")[0].strip()
    if normalized_content_type in PDF_CONTENT_TYPES:
        return "pdf"
    if normalized_content_type in IMAGE_CONTENT_TYPES:
        return "image"

    suffix = Path(filename or "").suffix.lower()
    if suffix in PDF_EXTENSIONS:
        return "pdf"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return "unknown"


def extract_text_from_pdf(content: bytes) -> tuple[str, int]:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_texts = [page.extract_text() or "" for page in pdf.pages]
            return "\n".join(page_texts), len(pdf.pages)
    except Exception as exc:  # noqa: BLE001 - surface as a domain error
        raise OCRProcessingError(f"Failed to read PDF: {exc}") from exc


def extract_from_bytes(
    *,
    content: bytes,
    filename: str | None = None,
    content_type: str | None = None,
    force_ocr: bool = False,
) -> ExtractionResult:
    source_type = detect_source_type(filename, content_type)
    if source_type == "unknown":
        raise UnsupportedFileTypeError(
            "Unsupported file type. Please upload a PDF or an image "
            "(jpg, jpeg, png, webp, bmp, tiff)."
        )

    warnings: list[str] = []
    used_ocr = False
    pages_processed = 0
    text = ""

    if source_type == "pdf":
        if not force_ocr:
            text, pages_processed = extract_text_from_pdf(content)

        if force_ocr or len(text.strip()) < MIN_EXTRACTABLE_TEXT_CHARS:
            if text.strip() and not force_ocr:
                warnings.append(
                    "Embedded PDF text was too sparse to be reliable; fell back to OCR."
                )
            ocr_text, ocr_pages = ocr_pdf_bytes(content)
            text = ocr_text
            pages_processed = ocr_pages or pages_processed
            used_ocr = True
    else:
        text = ocr_image_bytes(content, filename=filename)
        pages_processed = 1
        used_ocr = True

    if not text.strip():
        warnings.append("No readable text could be extracted from the upload.")

    data = extract_policy_fields(text)
    missing_fields = [key for key in OUTPUT_KEYS if not data.get(key)]

    return ExtractionResult(
        data=data,
        source_type=source_type,
        used_ocr=used_ocr,
        pages_processed=pages_processed,
        missing_fields=missing_fields,
        warnings=warnings,
    )


def get_ocr_engine_status() -> dict[str, bool | str | None]:
    tesseract_cmd = _find_binary("TESSERACT_CMD", "tesseract")
    pdftoppm_cmd = _find_binary("PDFTOPPM_CMD", "pdftoppm")
    return {
        "tesseract_available": tesseract_cmd is not None,
        "pdftoppm_available": pdftoppm_cmd is not None,
        "tesseract_cmd": tesseract_cmd,
        "pdftoppm_cmd": pdftoppm_cmd,
        "ready_for_image_ocr": tesseract_cmd is not None,
        "ready_for_pdf_ocr": tesseract_cmd is not None and pdftoppm_cmd is not None,
    }


FIELD_SPECS = (
    FieldSpec(
        key="policy_holder_name",
        labels=(
            r"\bpolicy\s*holder\s*name\b",
            r"\bpolicyholder\s*name\b",
            r"\bname\s*of\s*(?:the\s*)?(?:prospect|proposer|applicant)\s*/\s*policy\s*holder\b",
            r"\b(?:prospect|proposer|applicant)\s*/\s*policy\s*holder\s*name\b",
            r"\bcustomer\s*name\b",
            r"\binsured\s*name\b",
            r"\bname\s*of\s*insured\b",
            r"\bproposer\s*name\b",
            r"\bapplicant\s*name\b",
            r"\bmember\s*name\b",
            r"\blife\s*assured\s*name\b",
            r"^\s*name\b",
        ),
        cleaner=clean_name,
    ),
    FieldSpec(
        key="mobile_number",
        labels=(
            r"\bmobile\s*(?:no|number|num)\.?\b",
            r"\bmob\.?\s*(?:no|number|num)?\.?\b",
            r"\bmobile\b",
            r"\bcontact\s*(?:no|number)\.?\b",
            r"\bphone\s*(?:no|number)\.?\b",
            r"\bphone\s*/\s*mobile\b",
            r"\bmobile\s*/\s*phone\b",
            r"\btelephone\s*(?:no|number)\.?\b",
            r"\bcell\s*(?:no|number)\.?\b",
            r"\bwhats\s*app\s*(?:no|number)\.?\b",
            r"\bwhatsapp\s*(?:no|number)\.?\b",
            r"\binsured\s*mobile\b",
            r"\bpolicy\s*holder\s*mobile\b",
            r"\bregistered\s*mobile\b",
        ),
        cleaner=clean_mobile_number,
    ),
    FieldSpec(
        key="date_of_birth",
        labels=(
            r"\bdate\s*of\s*birth\b",
            r"\bd\.?\s*o\.?\s*b\.?\b",
            r"\bdob\b",
            r"\bbirth\s*date\b",
            r"\bborn\s*on\b",
        ),
        cleaner=clean_date_of_birth,
    ),
    FieldSpec(
        key="email",
        labels=(
            r"\be-?mail\s*(?:id|address)?\b",
            r"\bmail\s*id\b",
        ),
        cleaner=clean_email,
    ),
    FieldSpec(
        key="insurance_company_name",
        labels=(
            r"\binsurance\s*company\s*(?:name)?\b",
            r"\binsurer(?!\s*['\u2019]s)\s*(?:name)?\b",
            r"\bname\s*of\s*insurer\b",
            r"\binsurance\s*provider\s*(?:name)?\b",
            r"\bpolicy\s*issuer\s*(?:name)?\b",
            r"\bissued\s*by\b",
            r"\bunderwritten\s*by\b",
            r"\bunderwriter\s*(?:name)?\b",
        ),
        cleaner=clean_insurance_company_name,
    ),
    FieldSpec(
        key="vehicle_registration_number",
        labels=(
            r"\bvehicle\s*registration\s*(?:no|number)\.?\b",
            r"\bregistration\s*(?:no|number|num|#)\.?\b",
            r"\bregistration\s*(?:no|number)\.?\b",
            r"\bregn\.?\s*(?:no|number)\.?\b",
            r"\bregn\.?\s*(?:no|number|num|#)\.?\b",
            r"\breg\.?\s*(?:no|number)\.?\b",
            r"\breg\.?\s*(?:no|number|num|#)\.?\b",
            r"\bvehicle\s*(?:no|number)\.?\b",
            r"\bregistration\s*mark\b",
            r"\bregistration\b",
        ),
        cleaner=clean_vehicle_registration,
    ),
    FieldSpec(
        key="vehicle_make",
        labels=(
            r"\bvehicle\s*make\b",
            r"\bmake\s*of\s*vehicle\b",
            r"\bmanufacturer\s*(?:name)?\b",
            r"\bmfg\.?\s*by\b",
            r"\bmake\b",
        ),
        cleaner=clean_vehicle_make,
    ),
    FieldSpec(
        key="vehicle_model_variant_subtype",
        labels=(
            r"\bmake\s*/\s*model\s*/\s*variant\b",
            r"\bvehicle\s*description\b",
            r"\bmodel\s*/\s*(?:vehicle\s*)?variant(?:\s*\(\s*sub\s*type\s*\)|\s*\(\s*subtype\s*\))?",
            r"\bmodel\s*/\s*variant(?:\s*\(\s*sub\s*type\s*\)|\s*\(\s*subtype\s*\))?",
            r"\bvariant\s*/\s*sub\s*type\b",
            r"\bvariant\s*/\s*subtype\b",
            r"\bvehicle\s*variant(?:\s*\(\s*sub\s*type\s*\)|\s*\(\s*subtype\s*\))?",
            r"\bmodel\s*variant\b",
            r"\bmodel\s*name\b",
            r"\bvehicle\s*model\b",
            r"\bvariant(?:\s*\(\s*sub\s*type\s*\)|\s*\(\s*subtype\s*\))?",
            r"\bsub\s*type\b",
            r"\bsubtype\b",
            r"\bmodel\b(?!\s*year)",
        ),
        cleaner=clean_vehicle_model_variant_subtype,
    ),
    FieldSpec(
        key="seating_capacity",
        labels=(
            r"\bseating\s*capacity\b",
            r"\bseating\s*cap\.?\b",
            r"\bseat\s*capacity\b",
            r"\bno\.?\s*of\s*seats\b",
            r"\bnumber\s*of\s*seats\b",
            r"\bpassenger\s*capacity\b",
            r"\bcarrying\s*capacity\b",
            r"\bseats\b",
        ),
        cleaner=clean_seating_capacity,
    ),
    FieldSpec(
        key="fuel_type",
        labels=(
            r"\bfuel\s*type\b",
            r"\btype\s*of\s*fuel\b",
            r"\bfuel\b",
        ),
        cleaner=clean_fuel_type,
    ),
    FieldSpec(
        key="registration_year",
        labels=(
            r"\byear\s*of\s*regn\.?\b",
            r"\byear\s*of\s*registration\b",
            r"\bregistration\s*year\b",
            r"\bregn\.?\s*year\b",
            r"\breg\.?\s*year\b",
            r"\bregistered\s*year\b",
        ),
        cleaner=clean_year_value,
    ),
    FieldSpec(
        key="manufacturing_year",
        labels=(
            r"\bmanufacturing\s*year\b",
            r"\bmanufacture\s*year\b",
            r"\byear\s*of\s*manufacture\b",
            r"\bmfg\.?\s*year\b",
            r"\bmfg\.?\s*yr\.?\b",
            r"\bmake\s*year\b",
        ),
        cleaner=clean_year_value,
    ),
    FieldSpec(
        key="cubic_capacity",
        labels=(
            r"\bcubic\s*capacity\s*(?:/\s*cc)?\b",
            r"\bcubic\s*cap\.?\b",
            r"\bengine\s*capacity\b",
            r"\bengine\s*cc\b",
            r"\bcc\b",
        ),
        cleaner=clean_cubic_capacity,
    ),
    FieldSpec(
        key="engine_number",
        labels=(ENGINE_LABEL_PATTERN,),
        cleaner=clean_engine_number,
    ),
    FieldSpec(
        key="chassis_number",
        labels=(
            r"\bchassis\s*(?:no|number)\.?\b",
            r"\bchasis\s*(?:no|number)\.?\b",
            r"\bvin\b",
            r"\bvehicle\s*identification\s*(?:no|number)\.?\b",
        ),
        cleaner=clean_chassis_number,
    ),
    FieldSpec(
        key="idv",
        labels=(
            r"\bidv\s*value\s*of\s*vehicle\b",
            r"\bvalue\s*of\s*vehicle\s*idv\b",
            r"\bvehicle\s*idv\s*value\b",
            r"\bvehicle\s*idv\b",
            r"\btotal\s*idv\s*value\b",
            r"\btotal\s*idv\b",
            r"\bidv\s*value\b",
            r"\binsured\s*declared\s*value\b",
            r"\bdeclared\s*value\b",
            r"\bidv\b",
        ),
        cleaner=clean_idv,
    ),
    FieldSpec(
        key="sum_insured",
        labels=(
            r"\bsum\s*insured\b",
            r"\bsum\s*assured\b",
            r"\binsured\s*amount\b",
            r"\bcoverage\s*amount\b",
            r"\bsum\s*covered\b",
            r"\btotal\s*sum\s*insured\b",
        ),
        cleaner=clean_sum_insured,
    ),
    FieldSpec(
        key="net_premium",
        labels=PREMIUM_LABEL_PATTERNS["net_premium"],
        cleaner=clean_premium_amount,
    ),
    FieldSpec(
        key="gst",
        labels=PREMIUM_LABEL_PATTERNS["gst"] + GST_COMPONENT_LABEL_PATTERNS,
        cleaner=clean_premium_amount,
    ),
    FieldSpec(
        key="gross_premium",
        labels=PREMIUM_LABEL_PATTERNS["gross_premium"],
        cleaner=clean_premium_amount,
    ),
    FieldSpec(
        key="policy_type",
        labels=(
            r"\bpolicy\s*type\b",
            r"\btype\s*of\s*policy\b",
            r"\binsurance\s*type\b",
            r"\bproduct\s*type\b",
            r"\bproduct\s*name\b",
            r"\bline\s*of\s*business\b",
            r"\blob\b",
        ),
        cleaner=clean_policy_type,
    ),
)
