"""Verify a proposed scalar normalization; no OCR, unit guessing or expressions."""
import re
from circuit_ir.models import ValueGrammar
from circuit_ir.value_parser import parse_quantity
from .models import Notation

_UNITS = {"Ω":"ohm", "ohm":"ohm", "F":"F", "H":"H", "V":"V", "A":"A",
          "Hz":"Hz", "s":"s", "deg":"deg", "m":"m"}
_PRINTED_UNITS = {"kΩ":("ohm","k"), "MΩ":("ohm","Meg"), "nF":("F","n"),
                  "pF":("F","p"), "uF":("F","u"), "µF":("F","u"), "μF":("F","u"),
                  "um":("m","u"), "µm":("m","u"), "μm":("m","u")}
_PRINTED = re.compile(r"([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)(Meg|[TGMkmunpµμ])?", re.ASCII)


def observed_unit(raw_unit, notation):
    """Only an explicit recognized unit token can support a unit candidate."""
    if notation is Notation.PRINTED and raw_unit in _PRINTED_UNITS:
        return _PRINTED_UNITS[raw_unit][0]
    return _UNITS.get(raw_unit)


def proposed_normalization(raw_scalar, raw_unit, notation):
    """Return exact (unit, SI string) or None. Raw evidence remains in its record.

    This function verifies the explicitly proposed notation, never selects it.
    """
    if raw_unit is None or notation is Notation.UNRESOLVED:
        return None
    unit, suffix = _UNITS.get(raw_unit), ""
    if notation is Notation.PRINTED and raw_unit in _PRINTED_UNITS:
        unit,suffix = _PRINTED_UNITS[raw_unit]
    if unit is None:
        return None
    scalar, grammar = raw_scalar, ValueGrammar.SI
    if notation is Notation.PRINTED:
        match = _PRINTED.fullmatch(raw_scalar.strip())
        if match is None or suffix and match[2]:
            return None
        token = match[2] or suffix
        token = {"M":"Meg", "µ":"u", "μ":"u"}.get(token,token)
        scalar = match[1]+token
        grammar = ValueGrammar.SPICE
    elif notation is Notation.SPICE:
        grammar = ValueGrammar.SPICE
    result = parse_quantity(scalar,unit,grammar)
    return (unit,result.quantity.si_value) if result.quantity else None
