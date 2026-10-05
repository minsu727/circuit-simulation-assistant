"""Exact M1 scalar normalization and its small typed failure envelope."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, Inexact, Rounded, localcontext
import unittest

import circuit_ir as ir
from circuit_ir.serialization import decode_json, dump_document
from test_circuit_ir_serialization import minimal_document


class ScalarTests(unittest.TestCase):
    def parse(self, text, grammar=ir.ValueGrammar.SPICE, unit="ohm"):
        result = ir.parse_quantity(text, unit, grammar)
        self.assertIsInstance(result, ir.ValueParseResult)
        self.assertEqual(result.issues, ())
        self.assertIsNotNone(result.quantity)
        return result.quantity

    def invalid(self, text):
        result = ir.parse_quantity(text, "ohm", ir.ValueGrammar.SPICE)
        self.assertIsNone(result.quantity)
        self.assertEqual(len(result.issues), 1)
        issue = result.issues[0]
        self.assertEqual(issue.code, "VALUE_INVALID")
        self.assertEqual(issue.severity, ir.IssueSeverity.ERROR)
        self.assertTrue(issue.blocking)
        self.assertEqual(issue.field, "literal")
        self.assertEqual(issue.target_refs, ())
        self.assertEqual(issue.provenance, ())
        return result

    def test_integer_decimal_and_plain_exponent(self):
        for text, expected in (("1", "1"), ("1.0", "1"), ("2.2", "2.2"),
                               (".5", "0.5"), ("1.", "1"), ("001.2300", "1.23"),
                               ("1e3", "1000"), ("1E-3", "0.001")):
            with self.subTest(text=text):
                self.assertEqual(self.parse(text).si_value, expected)

    def test_all_spice_suffix_families(self):
        cases = (("1T", "1000000000000"), ("1G", "1000000000"),
                 ("1Meg", "1000000"), ("1k", "1000"), ("2.2k", "2200"),
                 ("100m", "0.1"), ("10u", "0.00001"), ("4.7n", "0.0000000047"),
                 ("1p", "0.000000000001"), ("1f", "0.000000000000001"))
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self.parse(text).si_value, expected)

    def test_suffix_case_semantics_are_spice_not_generic_si(self):
        for text in ("1m", "1M"):
            self.assertEqual(self.parse(text).si_value, "0.001")
        for text in ("1meg", "1Meg", "1MEG", "1mEg"):
            self.assertEqual(self.parse(text).si_value, "1000000")
        for suffix in ("t", "g", "k", "u", "n", "p", "f"):
            self.assertEqual(self.parse("1" + suffix).si_value,
                             self.parse("1" + suffix.upper()).si_value)

    def test_sign_and_zero_do_not_impose_device_positivity(self):
        for text, expected in (("+1k", "1000"), ("-2.5", "-2.5"), ("-1m", "-0.001"),
                               ("0", "0"), ("-0.000k", "0"), ("+0e300", "0")):
            with self.subTest(text=text):
                self.assertEqual(self.parse(text).si_value, expected)

    def test_exponent_and_single_suffix_can_be_combined(self):
        self.assertEqual(self.parse("2.5e-3k").si_value, "2.5")
        self.assertEqual(self.parse("1E3Meg").si_value, "1000000000")

    def test_original_outer_whitespace_is_preserved(self):
        text = " \t2.200k\n"
        quantity = self.parse(text)
        self.assertEqual(quantity.literal, text)
        self.assertEqual(quantity.si_value, "2200")

    def test_unit_is_explicit_and_not_inferred(self):
        for unit in ("ohm", "F", "H", "V", "A", "Hz", "s", "deg", "m"):
            with self.subTest(unit=unit):
                quantity = self.parse("-1k", unit=unit)
                self.assertEqual(quantity.unit, unit)
                self.assertEqual(quantity.si_value, "-1000")

    def test_si_and_manual_grammars_accept_plain_numbers_only(self):
        for grammar in (ir.ValueGrammar.SI, ir.ValueGrammar.MANUAL):
            quantity = self.parse("-2.5e3", grammar)
            self.assertEqual(quantity.si_value, "-2500")
            self.assertEqual(quantity.grammar, grammar)
            result = ir.parse_quantity("1k", "ohm", grammar)
            self.assertIsNone(result.quantity)
            self.assertEqual(result.issues[0].code, "VALUE_INVALID")

    def test_invalid_suffixes_and_expressions_are_rejected(self):
        for text in ("1kk", "1me", "1Megm", "1x", "1kOhm", "1μ", "1µ", "1uF",
                     "1/2", "1k+2", "R=1k", "{R}", "sin(1)", ".include demo.lib",
                     "../model.lib", "value", "0x10"):
            with self.subTest(text=text):
                self.invalid(text)

    def test_empty_malformed_decimal_and_internal_space_are_rejected(self):
        for text in ("", " \t", ".", "+", "--1", "1.2.3", "1e", "1e+", "1  k",
                     "1 e3", "1\nk", "１k", "1_000"):
            with self.subTest(text=text):
                self.invalid(text)

    def test_nan_and_infinity_are_rejected(self):
        for text in ("NaN", "nan", "sNaN", "Inf", "infinity", "-Infinity", "+Inf"):
            with self.subTest(text=text):
                self.invalid(text)

    def test_low_decimal_context_cannot_round_a_long_coefficient(self):
        literal = "1.23456789012345678901234567890123456789k"
        expected = "1234.56789012345678901234567890123456789"
        with localcontext() as context:
            context.prec = 3
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            self.assertEqual(self.parse(literal).si_value, expected)
        self.assertEqual(Decimal(self.parse(literal).si_value), Decimal(expected))

    def test_small_long_coefficients_remain_exact(self):
        literal = "0.000000000000000000000000000000000000000123456789u"
        expected = "0.000000000000000000000000000000000000000000000123456789"
        self.assertEqual(self.parse(literal).si_value, expected)

    def test_exponent_boundary_uses_bounded_scientific_output(self):
        self.assertEqual(self.parse("1e300").si_value, "1e300")
        self.assertEqual(self.parse("1e-300").si_value, "1e-300")
        self.assertEqual(self.parse("1e297k").si_value, "1e300")
        for text in ("1e301", "1e-301", "1e300k", "1e-300f", "99e300", "0e301"):
            with self.subTest(text=text):
                self.invalid(text)

    def test_literal_length_boundary_and_original_text_limit(self):
        literal = "9" * 128
        self.assertEqual(self.parse(literal).si_value, literal)
        self.invalid("9" * 129)
        self.invalid(" " * 128 + "1")

    def test_normalized_length_overflow_is_rejected_not_truncated(self):
        self.invalid("9" * 126 + "k")

    def test_repeated_results_are_equal_and_do_not_mutate_existing_quantity(self):
        quantity = ir.Quantity("1k", None, "ohm", ir.ValueGrammar.SPICE)
        first = ir.parse_quantity(quantity.literal, quantity.unit, quantity.grammar)
        second = ir.parse_quantity(quantity.literal, quantity.unit, quantity.grammar)
        self.assertEqual(first, second)
        self.assertIsNone(quantity.si_value)
        self.assertEqual(first.quantity.si_value, "1000")
        self.assertEqual(self.invalid("bad"), self.invalid("bad"))

    def test_api_configuration_errors_are_explicit(self):
        for text in (1, True, None, b"1k"):
            with self.subTest(text=text), self.assertRaises(TypeError):
                ir.parse_quantity(text, "ohm", ir.ValueGrammar.SPICE)
        with self.assertRaises(TypeError):
            ir.parse_quantity("1k", "ohm", "spice")
        with self.assertRaises(ValueError):
            ir.parse_quantity("1k", "unknown_unit", ir.ValueGrammar.SPICE)
        with self.assertRaises(ValueError):
            ir.parse_quantity("1k", "ohm", ir.ValueGrammar.UNRESOLVED)

    def test_parsed_quantity_projects_without_numeric_precision_loss(self):
        quantity = self.parse("1.23456789012345678901234567890123456789k")
        doc = minimal_document()
        changed = replace(doc, components=(replace(doc.components[0], value=quantity),))
        value = decode_json(dump_document(changed))["components"][0]["value"]
        self.assertEqual(value["literal"], quantity.literal)
        self.assertEqual(value["si_value"], quantity.si_value)
        self.assertIs(type(value["si_value"]), str)


class ParseRecordTests(unittest.TestCase):
    def test_issue_blocking_is_derived_and_cannot_be_overridden(self):
        issue = ir.parse_quantity("bad", "ohm", ir.ValueGrammar.SPICE).issues[0]
        for severity, blocking in ((ir.IssueSeverity.ERROR, True),
                                   (ir.IssueSeverity.AMBIGUOUS, True),
                                   (ir.IssueSeverity.WARNING, False),
                                   (ir.IssueSeverity.CONFIRMED, False)):
            self.assertEqual(replace(issue, severity=severity).blocking, blocking)
        with self.assertRaises(TypeError):
            replace(issue, blocking=False)

    def test_result_and_issue_are_immutable_native_records(self):
        result = ir.parse_quantity("bad", "ohm", ir.ValueGrammar.SPICE)
        self.assertFalse(hasattr(result, "__dict__"))
        self.assertFalse(hasattr(result.issues[0], "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            result.quantity = None
        with self.assertRaises(FrozenInstanceError):
            result.issues[0].message = "other"
        self.assertEqual(hash(result), hash(ir.parse_quantity("bad", "ohm", ir.ValueGrammar.SPICE)))

    def test_runtime_records_do_not_accept_mutable_issue_collections(self):
        with self.assertRaises(TypeError):
            ir.ValueParseResult(None, [])
        with self.assertRaises(TypeError):
            ir.ValueParseResult(None, ("not_an_issue",))
        issue = ir.parse_quantity("bad", "ohm", ir.ValueGrammar.SPICE).issues[0]
        with self.assertRaises(TypeError):
            replace(issue, provenance=[])

    def test_parser_envelope_is_not_a_circuit_or_authorization(self):
        result = ir.parse_quantity("1k", "ohm", ir.ValueGrammar.SPICE)
        with self.assertRaises(TypeError):
            dump_document(result)
        self.assertFalse(hasattr(result, "technical_state"))
        self.assertFalse(hasattr(result, "approved"))
        self.assertFalse(hasattr(result, "can_execute"))


if __name__ == "__main__":
    unittest.main()
