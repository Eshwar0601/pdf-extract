"""Coordinate-aware keyword extraction for insurance PDFs."""

import re

from config.keywords import FIELDS


class KeywordExtractor:
    def __init__(self, lines, words=None, tables=None, raw_text=None):
        self.lines = [line.strip() for line in lines if line.strip()]
        self.words = words or []
        self.tables = tables or []
        self.raw_text = raw_text or ""
        self.word_index = self._build_word_index()

    def _build_word_index(self):
        index = []
        for word in self.words:
            if isinstance(word, dict):
                text = str(word.get("text", "")).strip()
                if text:
                    index.append(word)
        return index

    def extract(self):
        data = {}
        for field, keywords in FIELDS.items():
            value = self.extract_field(field, keywords)
            data[field] = value
        return data

    def extract_field(self, field, keywords):
        for keyword in sorted(keywords, key=lambda item: -len(item)):
            candidate = self.find_keyword(keyword, field)
            if candidate:
                return candidate

        for table in self.tables:
            candidate = self.extract_table_value(table, keywords, field)
            if candidate:
                return candidate

        return "Not Found"

    def find_keyword(self, keyword, field_name=None):
        for index, line in enumerate(self.lines):
            match = self.find_keyword_match(line, keyword)
            if not match:
                continue

            value = self.extract_same_line(line, keyword, field_name, match)
            if value:
                cleaned = self.clean_candidate(value)
                if cleaned and self.is_valid_value(cleaned, field_name):
                    return cleaned

            value = self.extract_below(index, keyword, field_name)
            if value:
                cleaned = self.clean_candidate(value)
                if cleaned and self.is_valid_value(cleaned, field_name):
                    return cleaned

        for word in self.word_index:
            if word.get("text", "").strip().lower() == keyword.strip().lower():
                return self.extract_using_coordinates(word, field_name)

        return None

    def find_all_keywords(self, keyword):
        matches = []
        for word in self.word_index:
            if str(word.get("text", "")).strip().lower() == keyword.lower():
                matches.append(word)
        return matches

    def find_keyword_match(self, line, keyword):
        keyword_text = str(keyword).strip().lower()
        keyword_text = re.sub(r"[\.:]+$", "", keyword_text)
        pattern = rf"(?<!\w){re.escape(keyword_text)}(?!\w)"
        return re.search(pattern, line.lower())

    def extract_same_line(self, line, keyword, field_name=None, match=None):
        if match is None:
            match = self.find_keyword_match(line, keyword)
            if not match:
                return None

        value = line[match.end():].strip()
        while value.startswith(":") or value.startswith("-"):
            value = value[1:].strip()
        if not value or value.lower() == str(keyword).strip().lower():
            return None

        if self.is_table_header_line(value):
            return None

        if field_name == "customerName":
            value = self.trim_after_date_token(value)

        if field_name in {"policyStartDate", "policyEndDate"}:
            value = self.select_date_from_value(value, "first" if field_name == "policyStartDate" else "last")

        value = self.trim_after_stop_keyword(value)
        return value

    def select_date_from_value(self, value, prefer="first"):
        dates = self.find_date_tokens(value)
        if not dates:
            return value
        return dates[0] if prefer == "first" else dates[-1]

    def find_date_tokens(self, value):
        if not value:
            return []

        patterns = [
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
            r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b",
            r"\b\d{1,2}-[A-Za-z]{3}-\d{2,4}\b",
            r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b"
        ]
        dates = []
        for pattern in patterns:
            dates.extend(re.findall(pattern, value))
        return [date.strip() for date in dates if date.strip()]

    def trim_after_date_token(self, value):
        if not value:
            return value

        pattern = r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b(?:\s*(?:to|-|TO|To)\s*\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b)?"
        match = re.search(pattern, value)
        if match:
            return value[:match.start()].strip()

        return value

    def is_table_header_line(self, value):
        lower = value.lower()
        header_terms = [
            "model",
            "variant",
            "cubic capacity",
            "gvw",
            "seating capacity",
            "engine",
            "chassis",
            "vin",
            "registration",
            "vehicle type"
        ]
        matches = sum(1 for term in header_terms if term in lower)
        return matches >= 2

    def trim_after_stop_keyword(self, value):
        stop_terms = [
            "policy",
            "period",
            "cover",
            "premium",
            "validity",
            "vehicle",
            "registration",
            "phone",
            "mobile",
            "email",
            "gstin",
            "nominee",
            "proposal",
            "previous",
            "fax",
            "website",
            "address",
            "helpline"
        ]
        lower_value = value.lower()
        earliest = len(value)
        for term in stop_terms:
            idx = lower_value.find(term)
            if idx != -1 and idx < earliest:
                earliest = idx
        if earliest < len(value):
            value = value[:earliest].strip()
        return value

    def extract_right(self, keyword_word):
        candidates = []
        for word in self.word_index:
            if word.get("page") != keyword_word.get("page"):
                continue
            if word.get("x0", 0) <= keyword_word.get("x1", 0):
                continue
            if abs(word.get("top", 0) - keyword_word.get("top", 0)) < 10:
                candidates.append(word)
        candidates.sort(key=lambda item: item.get("x0", 0))
        return candidates

    def extract_below(self, index, keyword, field_name=None):
        for offset in range(1, 3):
            if index + offset >= len(self.lines):
                break
            next_line = self.lines[index + offset].strip()
            if len(next_line) < 2:
                continue
            if self.is_table_header_line(next_line):
                continue
            if field_name == "customerName":
                next_line = self.trim_after_date_token(next_line)
            if field_name in {"policyStartDate", "policyEndDate"}:
                next_line = self.select_date_from_value(next_line, "first" if field_name == "policyStartDate" else "last")
            next_line = self.trim_after_stop_keyword(next_line)
            if next_line and self.is_valid_value(next_line, field_name):
                return next_line
        return None

    def extract_table(self, tables):
        for table in tables:
            for row in table:
                if not row:
                    continue
                row_values = [str(col).strip() if col else "" for col in row]
                joined = " ".join(row_values).strip()
                if joined:
                    yield row_values

    def nearest_word(self, word):
        nearest = None
        best_distance = None
        for candidate in self.word_index:
            if candidate.get("page") != word.get("page"):
                continue
            if candidate.get("text", "").strip().lower() == str(word.get("text", "")).strip().lower():
                continue
            if candidate.get("top", 0) < word.get("top", 0) - 10 or candidate.get("top", 0) > word.get("top", 0) + 10:
                continue
            distance = abs(candidate.get("x0", 0) - word.get("x1", 0))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                nearest = candidate
        return nearest

    def stop_at_next_keyword(self, words, start_index):
        stop_words = {"policy", "period", "cover", "premium", "validity", "vehicle", "registration", "phone", "mobile", "email", "gstin", "nominee"}
        for index in range(start_index, len(words)):
            text = str(words[index].get("text", "")).strip().lower()
            if text in stop_words or any(token in text for token in stop_words):
                return index
        return len(words)

    def is_keyword(self, text):
        text = str(text).strip().lower()
        for field, keywords in FIELDS.items():
            for keyword in keywords:
                if text == keyword.lower():
                    return True
        return False

    def is_valid_value(self, value, field_name):
        if not value:
            return False
        value = str(value).strip()
        if not value or value.lower() in {"not found", "unknown", "n/a"}:
            return False
        lower_value = value.lower()
        if field_name == "customerName" and any(token in lower_value for token in ["policy", "period", "cover", "premium", "gstin", "help", "contact"]):
            return False
        if field_name == "policyNumber":
            if len(value) < 5 or not any(ch.isdigit() for ch in value):
                return False
            if any(token in lower_value for token in ["through", "preferred", "insurance partner", "proposal", "proposal no"]):
                return False
        if field_name == "customerMobileNumber":
            digits = "".join(ch for ch in value if ch.isdigit())
            if len(digits) < 10:
                return False
            if any(token in lower_value for token in ["helpline", "help", "phone", "toll"]):
                return False
        if field_name == "customerEmailId" and "@" not in value:
            return False
        if field_name == "customerEmailId" and any(token in lower_value for token in ["support@", "customercare@", "grievance@", "customerservice@"]):
            return False
        if field_name in {"policyStartDate", "policyEndDate", "customerDOB"} and not self.find_date_tokens(value):
            return False
        if field_name in {"vehicleEngineNumber", "vehicleChassisNumber"}:
            compact = re.sub(r"[^A-Za-z0-9]", "", value)
            if len(compact) < 5 or len(compact) > 24 or not any(char.isdigit() for char in compact):
                return False
        if field_name == "vehicleRegistrationNumber":
            if "irda" in lower_value or "registration no" in lower_value:
                return False
            if len("".join(ch for ch in value if ch.isalnum())) < 7:
                return False
        if field_name == "gstAmount":
            if "gstin" in lower_value or any(token in lower_value for token in ["cin", "pan", "registration"]):
                return False
        return True

    def clean_candidate(self, candidate, field_hint=None):
        if candidate is None:
            return None
        if isinstance(candidate, list):
            pieces = []
            for item in candidate:
                if isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                else:
                    text = str(item).strip()
                if text:
                    pieces.append(text)
            candidate = " ".join(pieces)
        candidate = str(candidate).strip()
        if not candidate:
            return None
        candidate = candidate.replace("\n", " ").replace("\t", " ")
        while "  " in candidate:
            candidate = candidate.replace("  ", " ")
        candidate = candidate.strip(" :,-")
        return candidate if candidate else None

    def extract_using_coordinates(self, keyword_word, field_name=None):
        if not keyword_word:
            return None

        candidates = self.extract_right(keyword_word)
        if candidates:
            value_words = []
            for candidate in candidates:
                text = str(candidate.get("text", "")).strip()
                if not text:
                    continue
                if self.is_keyword(text):
                    break
                if field_name == "customerName" and any(token in text.lower() for token in ["period", "policy", "cover", "premium", "gstin", "help", "contact"]):
                    break
                value_words.append(text)
            if value_words:
                value = self.clean_candidate(value_words)
                if self.is_valid_value(value, field_name or "customerName"):
                    return value

        nearest = self.nearest_word(keyword_word)
        if nearest:
            value = self.clean_candidate(nearest.get("text", ""))
            if self.is_valid_value(value, field_name or "customerName"):
                return value

        return None

    def extract_table_value(self, table, keywords, field_name=None):
        if not table:
            return None
        for row_index, row in enumerate(table):
            if not row:
                continue
            row_values = [str(col).strip() if col else "" for col in row]
            for keyword in keywords:
                for idx, cell in enumerate(row_values):
                    if self.cell_contains_keyword(cell, keyword):
                        if idx + 1 < len(row_values) and row_values[idx + 1].strip():
                            value = self.clean_candidate(row_values[idx + 1])
                            if self.is_valid_value(value, field_name):
                                return value
                        if row_index + 1 < len(table):
                            next_row = table[row_index + 1]
                            if idx < len(next_row):
                                value = self.clean_candidate(str(next_row[idx]).strip())
                                if self.is_valid_value(value, field_name):
                                    return value
                        break
        return None

    def cell_contains_keyword(self, cell, keyword):
        if not cell:
            return False
        cell_text = str(cell).strip().lower()
        keyword_text = str(keyword).strip().lower()
        keyword_text = re.sub(r"[\.:]+$", "", keyword_text)
        pattern = rf"(?<!\w){re.escape(keyword_text)}(?!\w)"
        return bool(re.search(pattern, cell_text))
