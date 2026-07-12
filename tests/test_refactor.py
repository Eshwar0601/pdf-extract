import unittest

from config.companies import detect_company
from config.insurance_types import detect_insurance_type
from parser.cleaner import clean_vehicle_number
from parser.keyword_extractor import KeywordExtractor


class ParserRefactorTests(unittest.TestCase):
    def test_company_detection_prefers_highest_scoring_match(self):
        text = "Previous Insurer\nICICI Lombard\nMagma HDI\nMagma HDI\nMagma HDI"
        self.assertEqual(
            detect_company(text),
            "MAGMA HDI GENERAL INSURANCE COMPANY LIMITED",
        )

    def test_motor_type_is_detected_from_vehicle_keywords(self):
        text = "Vehicle registration number, third party premium, own damage premium"
        self.assertEqual(detect_insurance_type(text), "Motor")

    def test_extracts_value_from_the_right_of_a_keyword(self):
        words = [
            {"text": "Customer", "x0": 0, "x1": 20, "top": 10, "bottom": 20, "page": 1},
            {"text": "Name", "x0": 21, "x1": 40, "top": 10, "bottom": 20, "page": 1},
            {"text": "John", "x0": 41, "x1": 60, "top": 10, "bottom": 20, "page": 1},
            {"text": "Smith", "x0": 61, "x1": 80, "top": 10, "bottom": 20, "page": 1},
        ]
        extractor = KeywordExtractor(
            lines=["Customer Name John Smith"],
            words=words,
            tables=[],
            raw_text="Customer Name John Smith",
        )
        data = extractor.extract()
        self.assertEqual(data["customerName"], "John Smith")

    def test_vehicle_number_is_rejected_when_it_is_not_a_registration_number(self):
        self.assertEqual(clean_vehicle_number("IRDA Registration No. 149"), "Not Found")
        self.assertEqual(clean_vehicle_number("KA 01 AB 1234"), "KA01AB1234")


if __name__ == "__main__":
    unittest.main()
