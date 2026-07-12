"""Main extraction engine for insurance PDFs."""

from parser.keyword_extractor import KeywordExtractor
from parser.formatter import format_response, merge_data
from config.companies import detect_company
from config.insurance_types import detect_insurance_type
from parser.rule_extractor import RuleExtractor


def extract_policy_data(pages, lines, raw_text, words=None, tables=None):
    company = detect_company(raw_text)
    insurance_type = detect_insurance_type(raw_text)

    extractor = KeywordExtractor(lines=lines, words=words or [], tables=tables or [], raw_text=raw_text)
    keyword_result = extractor.extract()
    rule_result = RuleExtractor(lines, raw_text).extract()

    coordinate_result = {}
    table_result = {}

    for field in keyword_result:
        if keyword_result[field] not in [None, "", "Not Found"]:
            coordinate_result[field] = keyword_result[field]

    # High-confidence label + format rules take precedence over generic keyword
    # matching.  The latter remains a useful fallback for unrecognised layouts.
    merged = merge_data(rule_result, coordinate_result, table_result, keyword_result)
    merged["companyName"] = company
    merged["insuranceType"] = insurance_type

    if merged.get("productName") in [None, "", "Not Found"]:
        merged["productName"] = merged.get("policyType", "Not Found")

    return format_response(merged)
