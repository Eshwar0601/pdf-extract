"""High-confidence, layout-independent insurance policy field extraction.

This module deliberately extracts a value only when its label and format agree.
It is used ahead of the older keyword fallback, which is useful for unusual
layouts but is too permissive for policy schedules containing many references
to previous policies, support contacts, and premium tables.
"""

import re


DATE = r"(?:\d{1,2}[/-][A-Za-z]{3,9}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
MONEY = r"(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d{1,2})?)"


class RuleExtractor:
    def __init__(self, lines, raw_text, tables=None):
        self.lines = [re.sub(r"\s+", " ", line).strip() for line in lines if line.strip()]
        self.text = "\n".join(self.lines) or raw_text
        self.tables = tables or []

    def extract(self):
        vehicle = self._motor_table()
        return {
            "customerName": self._table_customer_name() or self._name(),
            "policyNumber": self._policy_number(),
            "policyType": self._label_value(["policy plan", "policy type", "cover type"], text=True) or self._motor_product(),
            "productName": self._label_value(["product name", "plan name"], text=True) or self._motor_product(),
            "policyStartDate": self._insured_period_date("first") or self._date("(?:period of (?:insurance|own damage|liability)\\s*(?:cover)?|policy period|coverage|insurance)\\s*(?:from|start)") or self._date("from"),
            "policyEndDate": self._insured_period_date("last") or self._date("(?:period of (?:insurance|own damage|liability)\\s*(?:cover)?|policy period|coverage|insurance)\\s*(?:to|end|expiry)") or self._date("to"),
            "vehicleRegistrationNumber": vehicle.get("vehicleRegistrationNumber") or self._registration(),
            "vehicleEngineNumber": vehicle.get("vehicleEngineNumber") or self._motor_identifiers()[0] or self._identifier(["engine no", "engine number"], min_length=5, max_length=24),
            "vehicleChassisNumber": vehicle.get("vehicleChassisNumber") or self._motor_identifiers()[1] or self._identifier(["chassis no", "chassis number", "vin"], min_length=8, max_length=24),
            "vehicleMake": vehicle.get("vehicleMake"),
            "vehicleModel": vehicle.get("vehicleModel"),
            "vehicleIDV": vehicle.get("vehicleIDV") or self._vehicle_idv(),
            "basicODPremium": self._money(["basic od premium", "basic premium", "net own damage premium", "total own damage premium", "od total"]),
            "tpPremium": self._money(["basic tp premium", "total liability premium", "third party premium", "liability premium"]),
            "netPremium": self._money(["net premium", "gross premium"]),
            "finalPremium": self._money(["premium amount", "gross premium paid", "total premium payable", "total premium"]),
            "premiumDiscount": self._money(["no claim bonus.*", "premium discount"]),
            "ncb": self._ncb(),
            "customerDOB": self._dob(),
            "customerAge": self._age(),
            "customerMobileNumber": self._mobile(),
            "customerEmailId": self._email(),
            "customerAddress": self._table_address() or self._address(),
            "gstAmount": self._gst_amount(),
        }

    def _table_customer_name(self):
        for table in self.tables:
            for row in table:
                cells = [str(cell or "").replace("\n", " ").strip() for cell in row]
                for index, cell in enumerate(cells):
                    if "insured's code/name" in cell.lower() or "insured's code/ name" in cell.lower():
                        value = next((item for item in cells[index + 1:] if item), "")
                        value = re.sub(r"^[A-Z0-9-]+\s*/\s*", "", value, flags=re.I)
                        value = re.sub(r"^(?:MR|MRS|MS)\.?\s*", "", value, flags=re.I)
                        return value or None
        return None

    def _table_address(self):
        for table in self.tables:
            for row in table:
                cells = [str(cell or "").replace("\n", " ").strip() for cell in row]
                for index, cell in enumerate(cells):
                    if "insured address and" in cell.lower():
                        value = next((item for item in cells[index + 1:] if item), "")
                        value = re.split(r",?\s*(?:mob|mobile|email)\s*[-:]", value, flags=re.I)[0].strip(" ,")
                        return value or None
        return None

    def _motor_table(self):
        result = {}
        for table in self.tables:
            for row_index, row in enumerate(table[:-1]):
                headers = [str(cell or "").replace("\n", " ").strip().lower() for cell in row]
                if not any("registration" in cell for cell in headers) or not any("engine" in cell for cell in headers):
                    continue
                values = [str(cell or "").replace("\n", " ").strip() for cell in table[row_index + 1]]
                registration = values[0] if values else ""
                engine = values[1] if len(values) > 1 else ""
                make = values[3] if len(values) > 3 else ""
                reg_match = re.search(r"[A-Z]{2}\s*-?\s*\d{1,2}\s*-?\s*[A-Z]{1,3}\s*-?\s*\d{3,4}", registration, re.I)
                ids = re.findall(r"\b[A-Z0-9]{6,24}\b", engine, re.I)
                if reg_match:
                    result["vehicleRegistrationNumber"] = reg_match.group(0)
                if len(ids) >= 2:
                    result["vehicleEngineNumber"], result["vehicleChassisNumber"] = ids[-2:]
                if make:
                    result["vehicleMake"] = make
                    result["vehicleModel"] = make
        for table in self.tables:
            for row_index, row in enumerate(table[:-1]):
                headers = " ".join(str(cell or "") for cell in row).lower()
                if "idv for the" in headers:
                    values = [str(cell or "").strip() for cell in table[row_index + 1]]
                    if len(values) > 4 and values[4]:
                        result["vehicleIDV"] = values[4]
        return result

    def _motor_product(self):
        for line in self.lines[:20]:
            if "motor" in line.lower() and "policy" in line.lower():
                return line.strip(" -")
        return None

    def _gst_amount(self):
        amounts = []
        for label in ("cgst", "sgst/utgst", "igst"):
            value = self._money([label])
            if value:
                amounts.append(float(value))
        return str(sum(amounts)) if amounts else None

    def _label_value(self, labels, text=False):
        for index, line in enumerate(self.lines):
            for label in labels:
                match = re.search(r"\b" + label + r"\b\s*[:#-]?\s*(.+)$", line, re.I)
                if match:
                    value = match.group(1).strip(" :-")
                    if value and len(value) < 100:
                        return value
        return None

    def _name(self):
        labels = ["insured(?:'s)? name", "insured name", "client name", "customer name", "policyholder name", "policy holder name", "name of insured", "^name"]
        for line in self.lines:
            for label in labels:
                match = re.search(label + r"\s*[:#-]?\s*([A-Za-z][A-Za-z .']{2,70}?)(?=\s+(?:age|period|policy|address|vehicle|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})|$)", line, re.I)
                if match:
                    value = re.sub(r"^(?:Mrs|Miss|Mr|Ms|Shri|Smt)\.?\s*", "", match.group(1), flags=re.I).strip()
                    if len(value.split()) >= 2:
                        return value
        return None

    def _policy_number(self):
        labels = ["policy no(?:\\.|umber)?", "policy #", "policy number", "certificate (?:no|number)", "quotation (?:no|number)", "quote (?:no|number)"]
        for line in self.lines:
            if re.search(r"previous|third party|tp policy", line, re.I):
                continue
            for label in labels:
                match = re.search(label + r"\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/._-]{5,40})", line, re.I)
                if match:
                    return match.group(1).strip(".,")
        return None

    def _date(self, label):
        for line in self.lines:
            match = re.search(label + r"[^0-9\n]{0,30}(" + DATE + r")", line, re.I)
            if match:
                return match.group(1)
        return None

    def _insured_period_date(self, position):
        for line in self.lines:
            if not re.search(r"insured(?:'s)? name|insured name", line, re.I):
                continue
            dates = re.findall(DATE, line, re.I)
            if dates:
                return dates[0] if position == "first" else dates[-1]
        return None

    def _registration(self):
        # Indian registrations retain their structure after PDF text extraction.
        for index, line in enumerate(self.lines):
            if re.search(r"registration|vehicle (?:no|number)", line, re.I):
                match = re.search(r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{3,4})\b", line, re.I)
                if match:
                    return match.group(1)
                for next_line in self.lines[index + 1:index + 3]:
                    match = re.search(r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{3,4})\b", next_line, re.I)
                    if match:
                        return match.group(1)
        match = re.search(r"\b([A-Z]{2}\s*\d{1,2}\s*[A-Z]{1,3}\s*\d{3,4})\b", self.text, re.I)
        return match.group(1) if match else None

    def _identifier(self, labels, min_length, max_length):
        for line in self.lines:
            for label in labels:
                match = re.search(label + r"\s*[:#.-]?\s*([A-Z0-9-]{" + str(min_length) + "," + str(max_length) + r"})\b", line, re.I)
                if match:
                    value = match.group(1)
                    if any(char.isdigit() for char in value):
                        return value
        return None

    def _motor_identifiers(self):
        for index, line in enumerate(self.lines):
            if not (re.search(r"engine (?:no|number)", line, re.I) and re.search(r"chassis (?:no|number)|vin", line, re.I)):
                continue
            values = " ".join(self.lines[index + 1:index + 4])
            tokens = re.findall(r"\b[A-Z0-9]{8,24}\b", values, re.I)
            # Labels are usually followed by vehicle type/fuel then engine and VIN.
            tokens = [token for token in tokens if any(char.isdigit() for char in token)]
            if len(tokens) >= 2:
                return tokens[-2], tokens[-1]
        return None, None

    def _money(self, labels):
        for label in labels:
            for index, line in enumerate(self.lines):
                match = re.search(label + r"[^0-9\n]{0,35}" + MONEY, line, re.I)
                if match:
                    return match.group(1).replace(",", "")
                # In many PDFs a multi-column header is followed by its values.
                if re.search(label, line, re.I) and index + 1 < len(self.lines):
                    next_value = re.search(MONEY, self.lines[index + 1], re.I)
                    if next_value:
                        return next_value.group(1).replace(",", "")
        return None

    def _vehicle_idv(self):
        value = self._money(["total idv", "idv of vehicle", "vehicle idv", "insured declared value"])
        if value:
            return value
        for index, line in enumerate(self.lines):
            if re.search(r"vehicle idv|\bidv\b.*total idv|total value", line, re.I) and index + 1 < len(self.lines):
                values = re.findall(r"\b\d+(?:\.\d{1,2})?\b", self.lines[index + 1].replace(",", ""))
                if values:
                    return values[0]
        return None

    def _ncb(self):
        match = re.search(r"(?:no claim bonus|\bncb\b)[^\n%]{0,50}?\(?\s*(\d{1,2})\s*%", self.text, re.I)
        return match.group(1) + "%" if match else None

    def _dob(self):
        match = re.search(r"(?:date of birth|\bdob\b)\s*[:#-]?\s*(" + DATE + r")", self.text, re.I)
        return match.group(1) if match else None

    def _age(self):
        for line in self.lines:
            if "nominee" in line.lower():
                continue
            match = re.search(r"(?:customer |insured )?\bage\b\s*(?:\(yrs?\))?\s*[:#-]?\s*(\d{1,3})\b", line, re.I)
            if match:
                return match.group(1)
        return None

    def _mobile(self):
        for line in self.lines:
            if re.search(r"(?:mobile|customer contact|phone)\s*(?:no|number|#)?", line, re.I) and not re.search(r"helpline|support|toll", line, re.I):
                match = re.search(r"(?<!\d)(?:\+91[- ]?)?([6-9]\d{9})(?!\d)", line)
                if match:
                    return match.group(1)
        return None

    def _email(self):
        for line in self.lines:
            if re.search(r"(?:customer )?(?:e-?mail|email)(?: id| address)?", line, re.I):
                if "*" in line:
                    continue
                match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", line, re.I)
                if match and not re.search(r"support|customercare|grievance", match.group(0), re.I):
                    return match.group(0)
        return None

    def has_masked_personal_contacts(self):
        """A masked insured contact is not recoverable and must not be replaced
        by a branch, agent, or grievance contact elsewhere in the document."""
        return any(
            "*" in line and re.search(r"(?:mob|mobile|e-?mail|email)", line, re.I)
            for line in self.lines
        )

    def _address(self):
        for index, line in enumerate(self.lines):
            match = re.search(r"(?:insured )?address\s*[:#-]?\s*(.+)$", line, re.I)
            if match and match.group(1).strip() and "email" not in match.group(1).lower():
                return match.group(1).strip()
            if re.fullmatch(r"(?:insured )?address\s*[:#-]?", line, re.I) and index + 1 < len(self.lines):
                return self.lines[index + 1]
        return None
