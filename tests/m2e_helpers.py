"""Public repository fixture/test decisions only; no imported review authority."""
from pathlib import Path
import circuit_ir as ir

ROOT = Path(__file__).resolve().parents[1]
BASES = ROOT / "tests/fixtures/spice_export"


def document(name="resistor_divider"):
    loaded = ir.load_document((BASES / name / "circuit.json").read_text(encoding="utf-8"))
    if loaded.document is None:
        raise AssertionError(loaded.issues)
    return loaded.document


def chain(name="resistor_divider", request=None, doc=None, context=None):
    doc = document(name) if doc is None else doc
    context = ir.repository_model_context("m2-demo-models-v1" if any(c.parameters for c in doc.components)
                                           else "m2-no-models-v1") if context is None else context
    report = ir.validate_document(doc)
    ids = tuple(sorted(i.issue_id for i in report.issues if i.severity is ir.IssueSeverity.WARNING))
    circuit = ir.make_circuit_approval(doc, approved=True, acknowledged_warning_ids=ids, exporter_contract="m2-spice-v1",
                                     model_registry_version=context[0], model_registry_sha256=context[1])
    base = ir.export_document(doc, circuit, model_context=context)
    representation = ir.make_representation_approval(doc, base, circuit, approved=True, model_context=context)
    request = ir.AnalysisRequest(ir.ACCondition(ir.ACSweep.DECADE, 100, "10", "1000000"),
                                target_net="vout", reference_net="vin") if request is None else request
    execution = ir.make_execution_approval(doc, base, circuit, representation, request, approved=True, model_context=context)
    return dict(document=doc, export_result=base, circuit_approval=circuit, representation_approval=representation,
                request=request, execution_approval=execution, model_context=context)


def make_request(data):
    fields = dict(data["condition"])
    kind = fields.pop("analysis_type")
    if kind == "AC":
        fields["sweep"] = ir.ACSweep(fields["sweep"])
        condition = ir.ACCondition(**fields)
    elif kind == "TRAN":
        condition = ir.TransientCondition(**fields)
    elif kind == "DC":
        condition = ir.DCCondition(**fields)
    else:
        raise AssertionError("Unknown authored fixture type")
    selected = dict(data.get("selection", {}))
    if "measurements" in selected:
        selected["measurements"] = tuple(selected["measurements"])
    return ir.AnalysisRequest(condition, **selected)
