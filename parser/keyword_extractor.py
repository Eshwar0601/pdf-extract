"""Coordinate-aware keyword extraction for insurance PDFs."""

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
        for keyword in keywords:
            candidate = self.find_keyword(keyword, field)
            if candidate:
                return candidate

        for table in self.tables:
            candidate = self.extract_table_value(table, keywords)
            if candidate:
                return candidate

        return "Not Found"

    def find_keyword(self, keyword, field_name=None):
        keyword_clean = keyword.strip().lower()

        for index, line in enumerate(self.lines):
            lower_line = line.lower()
            if keyword_clean not in lower_line:
                continue

            value = self.extract_same_line(line, keyword)
            if value:
                return self.clean_candidate(value)

            value = self.extract_below(index, keyword)
            if value:
                return self.clean_candidate(value)

        for word in self.word_index:
            if word.get("text", "").strip().lower() == keyword_clean:
                return self.extract_using_coordinates(word, field_name)

        return None

    def find_all_keywords(self, keyword):
        matches = []
        for word in self.word_index:
            if str(word.get("text", "")).strip().lower() == keyword.lower():
                matches.append(word)
        return matches

    def extract_same_line(self, line, keyword):
        lower_line = line.lower()
        position = lower_line.find(keyword.lower())
        if position == -1:
            return None

        value = line[position + len(keyword):].strip()
        while value.startswith(":") or value.startswith("-"):
            value = value[1:].strip()
        if not value or value.lower() == keyword.lower():
            return None
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

    def extract_below(self, index, keyword):
        if index + 1 >= len(self.lines):
            return None
        next_line = self.lines[index + 1].strip()
        if len(next_line) < 2:
            return None
        return next_line

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
        if field_name == "customerName" and any(token in value.lower() for token in ["policy", "period", "cover", "premium", "gstin"]):
            return False
        if field_name == "policyNumber" and len(value) < 2:
            return False
        if field_name == "customerMobileNumber" and len("".join(ch for ch in value if ch.isdigit())) < 10:
            return False
        if field_name == "customerEmailId" and "@" not in value:
            return False
        return True

    def clean_candidate(self, candidate, field_hint=None):
        if candidate is None:
            return None
        if isinstance(candidate, list):
            candidate = " ".join(str(item.get("text", "")).strip() for item in candidate if str(item.get("text", "")).strip())
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

    def extract_table_value(self, table, keywords):
        if not table:
            return None
        for row in table:
            if not row:
                continue
            row_values = [str(col).strip() if col else "" for col in row]
            joined = " ".join(row_values).lower()
            for keyword in keywords:
                if keyword.lower() in joined:
                    for col in row_values:
                        if col.lower() != keyword.lower() and col:
                            value = self.clean_candidate(col)
                            if self.is_valid_value(value, None):
                                return value
        return None