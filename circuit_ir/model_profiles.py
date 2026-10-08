"""Sealed repository demo Level-1 data, not a user model/library resolver.

Context is the existing immutable (version, digest) pair. Constructing a profile
does not enroll it in a registry. Only the two repository-owned contexts resolve;
there is no caller registry argument, external lookup or simulator I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
import re

from .models import ComponentType, ValueGrammar
from .value_parser import parse_quantity


def _si_token(decimal: Decimal) -> str:
    """Shared M2C exact renderer, extracted unchanged for model/W/L reuse.

    Callers first establish bounded finite SI syntax. Decimal.as_tuple avoids
    float conversion, normalize() and context-dependent rounding.
    """
    negative, digits, exponent = decimal.as_tuple()
    coefficient = "".join(str(d) for d in digits).lstrip("0")
    if not coefficient:
        return "0"
    trimmed = coefficient.rstrip("0")
    exponent += len(coefficient) - len(trimmed)
    coefficient = trimmed
    adjusted = exponent + len(coefficient) - 1
    prefix = "-" if negative else ""
    if -3 <= adjusted <= 6:
        point = len(coefficient) + exponent
        if point <= 0:
            body = "0." + "0" * -point + coefficient
        elif point >= len(coefficient):
            body = coefficient + "0" * (point - len(coefficient))
        else:
            body = coefficient[:point] + "." + coefficient[point:]
    else:
        body = coefficient[0] + ("." + coefficient[1:] if len(coefficient) > 1 else "") + "e" + str(adjusted)
    token = prefix + body
    if len(token) > 128 or abs(adjusted) > 300:
        raise ValueError("Emitted SI token exceeds the format bounds.")
    return token


def _coefficient(value: str) -> Decimal:
    if not isinstance(value, str):
        raise TypeError("Model coefficients must be exact SI decimal strings")
    # M1's parser is syntactic only. V is a parser carrier, not a claim about
    # coefficient dimensions: those belong to the fixed Level-1 template.
    parsed = parse_quantity(value, "V", ValueGrammar.SI)
    if parsed.quantity is None:
        raise ValueError("Model coefficient must be a bounded finite SI scalar")
    decimal = Decimal(parsed.quantity.si_value)
    _si_token(decimal)
    return decimal


@dataclass(frozen=True, slots=True)
class TrustedModelProfile:
    """Template-owned dimensions/signs; LEVEL=1 is fixed, not configurable.

    vto: V, kp: A/V², lambda_: 1/V, gamma: V^0.5, phi: V,
    cgso/cgdo: F/m. Demo profiles do not claim process accuracy or convergence.
    """
    profile_id: str
    component_type: ComponentType
    vto: str
    kp: str
    lambda_: str
    gamma: str
    phi: str
    cgso: str
    cgdo: str

    def __post_init__(self):
        if not isinstance(self.profile_id, str):
            raise TypeError("profile_id must be a string")
        if len(self.profile_id) > 64 or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", self.profile_id) is None:
            raise ValueError("profile_id must be a bounded identifier")
        if not isinstance(self.component_type, ComponentType):
            raise TypeError("component_type must be ComponentType")
        if self.component_type not in (ComponentType.NMOS, ComponentType.PMOS):
            raise ValueError("Only NMOS/PMOS Level-1 profiles are supported")
        vto = _coefficient(self.vto)
        if ((self.component_type is ComponentType.NMOS and vto <= 0)
                or (self.component_type is ComponentType.PMOS and vto >= 0)):
            raise ValueError("VTO must be nonzero and polarity-consistent")
        for field in ("kp", "phi"):
            if _coefficient(getattr(self, field)) <= 0:
                raise ValueError(f"{field} must be positive")
        for field in ("lambda_", "gamma", "cgso", "cgdo"):
            if _coefficient(getattr(self, field)) < 0:
                raise ValueError(f"{field} must be nonnegative")


_DEMO_PROFILES = (
    TrustedModelProfile("repository_demo_nmos", ComponentType.NMOS,
                        "1", "0.0001", "0.02", "0", "0.6", "0", "0"),
    TrustedModelProfile("repository_demo_pmos", ComponentType.PMOS,
                        "-1", "0.0001", "0.02", "0", "0.6", "0", "0"),
)


def _registry(version):
    if version == "m2-no-models-v1":
        return ()
    if version == "m2-demo-models-v1":
        return _DEMO_PROFILES
    raise ValueError("Unsupported repository model registry version")


def _profile_projection(profile):
    return {"profile_id": profile.profile_id, "component_type": profile.component_type.value,
            "level": 1, "vto": _si_token(_coefficient(profile.vto)),
            "kp": _si_token(_coefficient(profile.kp)),
            "lambda_": _si_token(_coefficient(profile.lambda_)),
            "gamma": _si_token(_coefficient(profile.gamma)),
            "phi": _si_token(_coefficient(profile.phi)),
            "cgso": _si_token(_coefficient(profile.cgso)),
            "cgdo": _si_token(_coefficient(profile.cgdo))}


def _registry_digest(version, profiles):
    if type(profiles) is not tuple or any(type(p) is not TrustedModelProfile for p in profiles):
        raise TypeError("Repository registry must be an immutable tuple of profiles")
    ids = [p.profile_id for p in profiles]
    if len(set(ids)) != len(ids):
        raise ValueError("Repository registry contains duplicate profile IDs")
    projection = {"registry_version": version, "profiles": [
        _profile_projection(p) for p in sorted(profiles, key=lambda p: p.profile_id)]}
    encoded = json.dumps(projection, sort_keys=True, ensure_ascii=True, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def repository_model_context(registry_version: str = "m2-demo-models-v1") -> tuple[str, str]:
    """Return the exact current repository context; never accept caller profiles.

    Recompute from sealed content instead of caching a digest separately. A repo
    coefficient update therefore invalidates existing envelopes even at the same
    version; changing versions also changes the digest.
    """
    if not isinstance(registry_version, str):
        raise TypeError("registry_version must be a string")
    return registry_version, _registry_digest(registry_version, _registry(registry_version))


def repository_model_profiles(model_context: tuple[str, str]) -> tuple[TrustedModelProfile, ...]:
    """Review/read only: resolve an exact known context to its sealed profiles."""
    if (type(model_context) is not tuple or len(model_context) != 2
            or any(not isinstance(v, str) for v in model_context)):
        raise TypeError("model_context must be an immutable (version, sha256) string pair")
    if model_context != repository_model_context(model_context[0]):
        raise ValueError("Model context digest does not match repository content")
    return _registry(model_context[0])
