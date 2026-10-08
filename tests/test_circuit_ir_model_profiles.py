"""Independent sealed-registry vectors and pure exact coefficient boundaries."""
from dataclasses import FrozenInstanceError, fields, replace
from decimal import localcontext
import hashlib
import json
import unittest
from unittest.mock import patch

import circuit_ir as ir
from circuit_ir import model_profiles as mp


def native_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def expected_projection():
    return {"registry_version": "m2-demo-models-v1", "profiles": [
        {"profile_id": "repository_demo_" + kind, "component_type": kind, "level": 1,
         "vto": vto, "kp": "1e-4", "lambda_": "0.02", "gamma": "0", "phi": "0.6", "cgso": "0", "cgdo": "0"}
        for kind, vto in (("nmos", "1"), ("pmos", "-1"))]}


class ModelProfileTests(unittest.TestCase):
    def setUp(self):
        self.context = ir.repository_model_context()
        self.profiles = ir.repository_model_profiles(self.context)
        self.nmos, self.pmos = self.profiles

    def test_independent_full_registry_vector(self):
        self.assertEqual(self.context, ("m2-demo-models-v1", native_digest(expected_projection())))
        self.assertEqual([p.profile_id for p in self.profiles], ["repository_demo_nmos", "repository_demo_pmos"])
        self.assertEqual([p.component_type for p in self.profiles], [ir.ComponentType.NMOS, ir.ComponentType.PMOS])
        for p, vto in ((self.nmos, "1"), (self.pmos, "-1")):
            self.assertEqual((p.vto, p.kp, p.lambda_, p.gamma, p.phi, p.cgso, p.cgdo),
                             (vto, "0.0001", "0.02", "0", "0.6", "0", "0"))

    def test_empty_context_exact_m2b_bytes(self):
        digest = hashlib.sha256(b'{"profiles":[],"registry_version":"m2-no-models-v1"}').hexdigest()
        context = ir.repository_model_context("m2-no-models-v1")
        self.assertEqual(context, ("m2-no-models-v1", digest))
        self.assertEqual(ir.repository_model_profiles(context), ())

    def test_profiles_and_context_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.nmos.kp = "2"
        with self.assertRaises(TypeError):
            self.profiles[0] = self.pmos
        with self.assertRaises(TypeError):
            self.context[1] = "a" * 64
        self.assertFalse(hasattr(self.nmos, "__dict__"))

    def test_constructing_profile_does_not_register_it(self):
        custom = replace(self.nmos, profile_id="custom_demo", kp="2")
        self.assertNotIn(custom, ir.repository_model_profiles(self.context))
        self.assertEqual(ir.repository_model_context(), self.context)
        with self.assertRaises(TypeError):
            ir.repository_model_context(profiles=(custom,))

    def test_minimal_fixed_field_contract(self):
        self.assertEqual([f.name for f in fields(ir.TrustedModelProfile)],
                         ["profile_id", "component_type", "vto", "kp", "lambda_", "gamma", "phi", "cgso", "cgdo"])
        for key in ("raw_model_text", "path", "level", "model_token", "parameters"):
            with self.subTest(key=key), self.assertRaises(TypeError):
                replace(self.nmos, **{key: ".include evil.lib"})

    def test_profile_identifier_rejects_injection(self):
        for text in ("", ".include evil.lib", "foo\n.tran 1", "NMOS(...)", "../model", "x" * 65):
            with self.subTest(text=text), self.assertRaises(ValueError):
                replace(self.nmos, profile_id=text)

    def test_type_must_be_mos_enum(self):
        with self.assertRaises(TypeError):
            replace(self.nmos, component_type="nmos")
        for kind in (ir.ComponentType.UNKNOWN, ir.ComponentType.RESISTOR, ir.ComponentType.VOLTAGE_SOURCE):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                replace(self.nmos, component_type=kind)

    def test_vto_sign_matches_polarity(self):
        for profile, values in ((self.nmos, ("0", "-0", "-1")), (self.pmos, ("0", "1"))):
            for value in values:
                with self.subTest(profile=profile.profile_id, value=value), self.assertRaises(ValueError):
                    replace(profile, vto=value)

    def test_positive_coefficients(self):
        for field in ("kp", "phi"):
            for value in ("0", "-0", "-0.1"):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(self.nmos, **{field: value})

    def test_nonnegative_coefficients(self):
        for field in ("lambda_", "gamma", "cgso", "cgdo"):
            with self.subTest(field=field):
                self.assertIsInstance(replace(self.nmos, **{field: "-0"}), ir.TrustedModelProfile)
                with self.assertRaises(ValueError):
                    replace(self.nmos, **{field: "-1"})

    def test_nonfinite_expression_suffix_and_raw_syntax_rejected(self):
        for text in ("NaN", "sNaN", "Infinity", "-Inf", "{x}", "1/2", "1k", "1\n.model x NMOS", ".lib model", "1; .tran 1", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                replace(self.nmos, kp=text)

    def test_no_float_or_numeric_coercion(self):
        for value in (0.0001, 1, True, None):
            with self.subTest(value=value), self.assertRaises(TypeError):
                replace(self.nmos, kp=value)

    def test_coefficient_bounds(self):
        for text in ("1e301", "1e-301", "1" * 129):
            with self.subTest(text=text), self.assertRaises(ValueError):
                replace(self.nmos, kp=text)
        self.assertEqual(mp._profile_projection(replace(self.nmos, kp="1e-300"))["kp"], "1e-300")
        self.assertEqual(mp._profile_projection(replace(self.nmos, kp="1e300"))["kp"], "1e300")

    def test_context_precision_independent_and_exact(self):
        coefficient = "0.000123456789012345678901234567890123456789"
        profile = replace(self.nmos, kp=coefficient)
        with localcontext() as ctx:
            ctx.prec = 2
            with patch.object(mp, "_DEMO_PROFILES", (profile, self.pmos)):
                context = ir.repository_model_context()
            self.assertEqual(mp._profile_projection(profile)["kp"], "1.23456789012345678901234567890123456789e-4")
        with patch.object(mp, "_DEMO_PROFILES", (profile, self.pmos)):
            self.assertEqual(ir.repository_model_context(), context)

    def test_equivalent_numbers_share_context_digest(self):
        profiles = (replace(self.nmos, kp="1.000e-4", vto="+1.0", gamma="-0.0"), self.pmos)
        with patch.object(mp, "_DEMO_PROFILES", profiles):
            self.assertEqual(ir.repository_model_context(), self.context)

    def test_every_coefficient_change_changes_digest(self):
        for field, value in (("vto", "2"), ("kp", "0.0002"), ("lambda_", "0.03"), ("gamma", "1"),
                             ("phi", "0.7"), ("cgso", "0.0001"), ("cgdo", "0.0001")):
            with self.subTest(field=field), patch.object(mp, "_DEMO_PROFILES", (replace(self.nmos, **{field: value}), self.pmos)):
                self.assertNotEqual(ir.repository_model_context(), self.context)
                with self.assertRaises(ValueError):
                    ir.repository_model_profiles(self.context)

    def test_version_id_and_type_are_digest_bound(self):
        profiles = self.profiles
        original = mp._registry_digest("m2-demo-models-v1", profiles)
        self.assertNotEqual(mp._registry_digest("m2-demo-models-v2", profiles), original)
        self.assertNotEqual(mp._registry_digest("m2-demo-models-v1", (replace(self.nmos, profile_id="other"), self.pmos)), original)
        changed = replace(self.nmos, component_type=ir.ComponentType.PMOS, vto="-1")
        self.assertNotEqual(mp._registry_digest("m2-demo-models-v1", (changed, self.pmos)), original)

    def test_registry_order_independent_and_duplicate_id_rejected(self):
        with patch.object(mp, "_DEMO_PROFILES", tuple(reversed(self.profiles))):
            self.assertEqual(ir.repository_model_context(), self.context)
        with patch.object(mp, "_DEMO_PROFILES", (self.nmos, replace(self.nmos, kp="2"))):
            with self.assertRaises(ValueError):
                ir.repository_model_context()

    def test_registry_rejects_mutable_and_untyped_records(self):
        for value in ([self.nmos], ({"raw_model_text": ".model x NMOS"},)):
            with self.subTest(value=value), patch.object(mp, "_DEMO_PROFILES", value), self.assertRaises(TypeError):
                ir.repository_model_context()

    def test_context_requires_exact_known_pair(self):
        for value in (("m2-demo-models-v1", "a" * 64), ("future_models", self.context[1]),
                      ("m2-no-models-v1", self.context[1])):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ir.repository_model_profiles(value)

    def test_context_shape_and_version_types(self):
        for value in (list(self.context), (), (None, self.context[1]), (*self.context, self.profiles)):
            with self.subTest(value=value), self.assertRaises(TypeError):
                ir.repository_model_profiles(value)
        with self.assertRaises(TypeError):
            ir.repository_model_context(None)

    def test_registry_resolution_has_no_external_io(self):
        with patch("builtins.open", side_effect=AssertionError("filesystem access")), \
                patch("os.getenv", side_effect=AssertionError("environment access")):
            self.assertEqual(ir.repository_model_context(), self.context)
            self.assertEqual(ir.repository_model_profiles(self.context), self.profiles)


if __name__ == "__main__":
    unittest.main()
