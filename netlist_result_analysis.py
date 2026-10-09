"""Mapped M2 RAW input adapter; all numerical algorithms remain in v0.1 modules.

No label guessing, sign inversion, RAW fabrication or approval authority. Ground
voltage is not manufactured when LTspice omits V(0); request another net. Only
two-terminal R/C/L/V/I current probes are admitted; MOS Id/Is/Ig conventions are
deliberately not guessed. Missing probes retain the actual available trace list.
"""
from dataclasses import dataclass

import numpy as np
from PyLTSpice import RawRead

from circuit_ir.execution import ACCondition, TransientCondition, DCCondition
from ac_result_analysis import MissingTraceError, analyze_ac
from transient_result_analysis import analyze_transient
from dc_result_analysis import analyze_dc


@dataclass(frozen=True, slots=True)
class NetlistAnalysis:
    result: object
    available_traces: tuple[str, ...]
    selected_traces: tuple[tuple[str, str, str], ...]


def _raw(raw_path, artifact):
    raw = RawRead(raw_path, dialect="ltspice", verbose=False)
    kind = artifact.directive.split(" ", 1)[0]
    expected = {".ac": "ac analysis", ".tran": "transient analysis",
                ".dc": "dc transfer characteristic"}[kind]
    if raw.get_raw_property("Plotname").casefold() != expected:
        raise ValueError("RAW analysis mode differs from the approved directive")
    if "stepped" in raw.get_raw_property("Flags").casefold():
        raise ValueError("Stepped RAW is outside the M2 execution contract")
    available = tuple(raw.get_trace_names())
    folded = [name.casefold() for name in available]
    if len(set(folded)) != len(folded):
        raise ValueError("Ambiguous case-insensitive RAW trace names")
    axis_name = {".ac": "frequency", ".tran": "time"}.get(kind)
    if axis_name and (not available or available[0].casefold() != axis_name):
        raise ValueError("Unexpected RAW axis for the approved analysis")
    # spicelib 1.6 lazily loads binary data. get_axis() alone raises while
    # _axis is still None, even when the header declares a valid sweep axis.
    # Axis.get_wave also applies LTspice compressed-time sign correction.
    axis = np.asarray(raw.get_trace(0).get_wave())
    if np.iscomplexobj(axis):
        if kind != ".ac" or np.any(axis.imag != 0):
            raise ValueError("Unexpected complex RAW axis")
        axis = axis.real
    axis = np.asarray(axis, dtype=float)
    if kind == ".tran":
        offset = float(raw.get_raw_property().get("Offset", 0))
        if not np.isfinite(offset) or offset < 0:
            raise ValueError("Invalid transient RAW Offset")
        axis = axis + offset
    if (axis.ndim != 1 or len(axis) < 2 or not np.all(np.isfinite(axis))
            or not np.all(np.diff(axis) > 0)):
        raise ValueError("RAW must have a finite, strictly increasing single axis")
    if kind == ".ac" and np.any(axis <= 0) or kind == ".tran" and np.any(axis < 0):
        raise ValueError("RAW axis is outside the supported physical domain")
    return raw, axis, available


def _wave(raw, available, name, axis):
    actual = {value.casefold(): value for value in available}.get(name.casefold())
    if actual is None:
        raise MissingTraceError([name], list(available))
    values = np.asarray(raw.get_trace(actual).get_wave())
    if values.shape != axis.shape or not np.all(np.isfinite(values)):
        raise ValueError("Selected RAW trace has invalid samples or length")
    return values, actual


def read_netlist_analysis(raw_path, artifact, request):
    """Called with the already verified M2 artifact and its approved request."""
    prefix = {ACCondition: ".ac", TransientCondition: ".tran", DCCondition: ".dc"}.get(type(request.condition))
    if prefix != artifact.directive.split(" ", 1)[0]:
        raise ValueError("Request and artifact analysis modes differ")
    raw, axis, available = _raw(raw_path, artifact)
    signals, selected = {}, []
    for role, identity, name in artifact.trace_map:
        values, actual = _wave(raw, available, name, axis)
        signals[role] = values
        selected.append((role, identity, actual))
    if "target_net" not in signals:
        raise ValueError("A reviewed target net is required for result analysis")
    target = signals["target_net"]
    condition = request.condition
    if type(condition) is ACCondition:
        if "reference_net" not in signals:
            raise ValueError("AC transfer analysis requires a reviewed reference net")
        result = analyze_ac(axis, target, signals["reference_net"])
        result.target_name = next(v[2] for v in selected if v[0] == "target_net")
        result.reference_name = next(v[2] for v in selected if v[0] == "reference_net")
    elif type(condition) is TransientCondition:
        result = analyze_transient(axis, target, signals.get("reference_net"), request.measurements)
        result.target_name = next(v[2] for v in selected if v[0] == "target_net")
        result.reference_name = next((v[2] for v in selected if v[0] == "reference_net"), "Reference")
    elif type(condition) is DCCondition:
        point = None if request.requested_point is None else float(request.requested_point)
        result = analyze_dc(axis, target, signals.get("comparison_net"), request.measurements, point)
        result.target_name = next(v[2] for v in selected if v[0] == "target_net")
        result.comparison_name = next((v[2] for v in selected if v[0] == "comparison_net"), "Comparison")
        result.sweep_source = artifact.sweep_source_map[1]
    else:
        raise ValueError("Unsupported typed analysis condition")
    return NetlistAnalysis(result, available, tuple(selected))


def read_generated_current(raw_path, artifact, export_result, component_id):
    """For a successful approved run: exact IR ID -> generated I(element).

    This observational helper cannot execute a simulator or authorize a run.
    Voltage-source current is INTO its positive terminal. An independent
    current source's positive current flows from positive to negative terminal.
    Passive currents follow emitted first-to-second terminal order.
    """
    import hashlib
    from circuit_ir.exporter import _mapping_digest
    if (_mapping_digest(export_result.element_map, export_result.net_map, export_result.model_map)
            != artifact.provenance.mapping_sha256
            or hashlib.sha256(export_result.spice_text.encode("utf-8")).hexdigest()
            != artifact.provenance.base_netlist_sha256):
        raise ValueError("Probe mapping does not match the approved base artifact")
    token = dict(export_result.element_map).get(component_id)
    if token is None:
        raise ValueError("Unknown exact component IR ID")
    if token[0] not in "RCLVI":
        raise ValueError("Device current convention is unsupported; no MOS probe substitution")
    raw, axis, available = _raw(raw_path, artifact)
    values, actual = _wave(raw, available, f"I({token})", axis)
    return axis, values, actual
