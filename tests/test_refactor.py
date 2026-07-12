import unittest

from config.companies import detect_company
from config.insurance_types import detect_insurance_type
from parser.cleaner import clean_vehicle_number
from parser.keyword_extractor import KeywordExtractor
from parser.rule_extractor import RuleExtractor


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

    def test_schedule_rules_extract_split_motor_vehicle_fields(self):
        lines = [
            "Insured Name MRS. JANE DOE 22 Jul 2022 12:00AM to 21 Jul 2023 11:59PM",
            "Policy No. & Policy Issued On 3001/O/RE-17290589/00/000 , 21 Jun 2022",
            "Vehicle Type Fuel Type Engine No. Chassis No./VIN",
            "PRIVATE COMPACT Petrol B4DA417E050337 MEERBC004M2082876",
            "Manufacturing Year RTO Registration No.",
            "2021 ELECTRONIC CITY KA 51 MQ 9681",
            "Vehicle IDV Non-Elec. Accessories IDV Total IDV",
            "557485 0 557485.00",
            "Gross Premium Paid 9,707",
        ]
        data = RuleExtractor(lines, "\n".join(lines)).extract()
        self.assertEqual(data["customerName"], "JANE DOE")
        self.assertEqual(data["policyStartDate"], "22 Jul 2022")
        self.assertEqual(data["policyEndDate"], "21 Jul 2023")
        self.assertEqual(data["vehicleRegistrationNumber"], "KA 51 MQ 9681")
        self.assertEqual(data["vehicleEngineNumber"], "B4DA417E050337")
        self.assertEqual(data["vehicleChassisNumber"], "MEERBC004M2082876")
        self.assertEqual(data["vehicleIDV"], "557485")


if __name__ == "__main__":
    unittest.main()
