# Circuit JSON Contract (Proposed / Not Implemented)

Circuit JSON is the proposed canonical intermediate representation, independent of LTspice symbol coordinates and SPICE line syntax. This document contains a **draft schema**, not an installed validator. [Semantic rules](validation-rules.md) are required in addition to shape validation.

## Record Model

| Field | Meaning / authority |
| --- | --- |
| `schema_version` | Proposed contract version `0.2-draft1`; not the application release version |
| `metadata` | Circuit identity, revision, origin and catalog version; revisions are assigned by the future app, not trusted from a provider |
| `source_image_reference` | Opaque local asset ID, content hash and original dimensions; no file bytes, absolute paths or remote URLs. Null is allowed for manual-JSON M2 fixtures |
| `components` | Device identities, types, pin IDs, quantities, model references and typed source settings |
| `pins` | Unique terminals with component owner and electrical role |
| `nets` | Electrical identity and ground status; opaque IDs rather than simulator node syntax |
| `connections` | **Only authoritative pin-to-net membership**; unresolved pins have no connection record |
| `labels` | Text, scope and proposed attachment; unresolved attachment is null |
| `visual` | Original-pixel geometry, symbol pose, text/wire/junction evidence and extraction provenance; never executable code |
| `confidence` | Optional extraction score, basis and calibration flag; not electrical correctness or approval |
| `ambiguities` | Alternatives and explicit resolution record; uncertainty is not silently collapsed |
| `warnings` | Finding IDs referring to WARNING entries in `validation_state.findings`, avoiding duplicated diagnostic text |
| `validation_state` | Revision-specific deterministic report. Imported values are untrusted and recomputed before review/export |

Components reference top-level pins; each pin references its owner. The redundant ownership relation must agree. Nets do not persist a second `connected_pins` list: that view is derived from `connections`. This avoids conflicting sources of connectivity truth.

Ground symbols, wires and labels live in visual/label records, not the device array. All accepted ground symbols resolve to one net with `is_ground=true`. Export maps that net to simulator node 0. A textual label alone must not silently establish ground.

## Quantities, Sources and Models

Quantities preserve `literal` and use a decimal-string `si_value` plus an explicit unit. Strings allow exact decimal normalization without binary-float rounding or NaN/Infinity. `grammar` identifies how the literal was interpreted. Drafts can retain a null normalized value, but missing/invalid required quantities block generation.

R/C/L require positive finite values in ohm/F/H. NMOS/PMOS require four pin roles, a reviewed model-catalog reference, and positive `width`/`length` quantities in meters. Model definitions are selected from a versioned local allowlist, not arbitrary OCR text or model-file paths. Invisible model parameters are not inferred from the symbol.

Independent sources require explicit terminal polarity/direction and DC value, including an explicit zero when intended. Voltage is positive-terminal potential minus negative-terminal potential; current flows from the positive terminal to the negative terminal. Optional AC has nonnegative magnitude in V/A and phase in degrees. SINE parameters are `offset`, `amplitude`, `frequency`; PULSE parameters are `initial`, `pulsed`, `delay`, `rise`, `fall`, `width`, `period`. Values use source-appropriate units, Hz or seconds. Source-specific rules validate parameter keys, dimensions and timing relationships; no opaque waveform expression is allowed. Analysis requests do not determine missing source settings.

SPICE-literal input is one parsing grammar, not the canonical encoding. In that grammar `m`/`M` means milli and `Meg` means mega; image text suggesting engineering uppercase M requires clarification rather than automatic reinterpretation. The exporter uses normalized SI values and explicit tested formatting. Unsupported expression values, arbitrary parameters/functions and injection-like text are rejected in the first scope.

## Proposed JSON Schema — Draft 2020-12

This complete shape schema intentionally allows unresolved drafts. Type-specific completeness, uniqueness across arrays, referential integrity, geometry bounds, topology and state transitions are enforced by the future deterministic validator. A schema-valid document is **not** simulator-ready. Conditional schema validation can tighten typed records later; see [JSON Schema conditionals](https://json-schema.org/understanding-json-schema/reference/conditionals).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "Proposed Circuit JSON 0.2-draft1",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "metadata", "source_image_reference", "components", "pins", "nets", "connections", "labels", "visual", "confidence", "ambiguities", "warnings", "validation_state"],
  "properties": {
    "schema_version": {"const": "0.2-draft1"},
    "metadata": {
      "type": "object", "additionalProperties": false,
      "required": ["circuit_id", "revision", "origin", "catalog_version"],
      "properties": {
        "circuit_id": {"$ref": "#/$defs/id"},
        "revision": {"type": "integer", "minimum": 0},
        "origin": {"enum": ["image", "manual"]},
        "catalog_version": {"type": "string", "minLength": 1, "maxLength": 64}
      }
    },
    "source_image_reference": {
      "oneOf": [
        {"type": "null"},
        {
          "type": "object", "additionalProperties": false,
          "required": ["asset_id", "sha256", "width_px", "height_px"],
          "properties": {
            "asset_id": {"$ref": "#/$defs/id"},
            "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
            "width_px": {"type": "integer", "minimum": 1},
            "height_px": {"type": "integer", "minimum": 1}
          }
        }
      ]
    },
    "components": {"type": "array", "items": {"$ref": "#/$defs/component"}},
    "pins": {"type": "array", "items": {"$ref": "#/$defs/pin"}},
    "nets": {"type": "array", "items": {"$ref": "#/$defs/net"}},
    "connections": {"type": "array", "items": {"$ref": "#/$defs/connection"}},
    "labels": {"type": "array", "items": {"$ref": "#/$defs/label"}},
    "visual": {
      "type": "object", "additionalProperties": false,
      "required": ["coordinate_space", "entities"],
      "properties": {
        "coordinate_space": {"const": "original_pixels"},
        "entities": {"type": "array", "items": {"$ref": "#/$defs/visual_entity"}}
      }
    },
    "confidence": {"$ref": "#/$defs/confidence"},
    "ambiguities": {"type": "array", "items": {"$ref": "#/$defs/ambiguity"}},
    "warnings": {"$ref": "#/$defs/ids"},
    "validation_state": {
      "type": "object", "additionalProperties": false,
      "required": ["status", "validated_revision", "ruleset_version", "findings"],
      "properties": {
        "status": {"enum": ["draft", "blocked", "ready_for_review", "reviewed"]},
        "validated_revision": {"type": ["integer", "null"], "minimum": 0},
        "ruleset_version": {"type": ["string", "null"]},
        "findings": {"type": "array", "items": {"$ref": "#/$defs/finding"}}
      }
    }
  },
  "$defs": {
    "id": {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_.-]*$", "maxLength": 64},
    "ids": {"type": "array", "uniqueItems": true, "items": {"$ref": "#/$defs/id"}},
    "nullable_id": {"oneOf": [{"$ref": "#/$defs/id"}, {"type": "null"}]},
    "point": {
      "type": "array", "minItems": 2, "maxItems": 2,
      "items": {"type": "number", "minimum": 0}
    },
    "confidence": {
      "type": "object", "additionalProperties": false,
      "required": ["score", "basis", "calibrated"],
      "properties": {
        "score": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
        "basis": {"enum": ["provider_score", "heuristic", "manual", "unknown"]},
        "calibrated": {"type": "boolean"}
      }
    },
    "quantity": {
      "type": "object", "additionalProperties": false,
      "required": ["literal", "si_value", "unit", "grammar"],
      "properties": {
        "literal": {"type": ["string", "null"], "maxLength": 128},
        "si_value": {
          "oneOf": [
            {"type": "string", "pattern": "^[+-]?(?:[0-9]+(?:\\.[0-9]+)?|\\.[0-9]+)(?:[eE][+-]?[0-9]+)?$", "maxLength": 128},
            {"type": "null"}
          ]
        },
        "unit": {"enum": ["ohm", "F", "H", "V", "A", "Hz", "s", "deg", "m"]},
        "grammar": {"enum": ["spice", "si", "manual", "unresolved"]}
      }
    },
    "source": {
      "type": "object", "additionalProperties": false,
      "required": ["dc", "ac", "waveform"],
      "properties": {
        "dc": {"oneOf": [{"$ref": "#/$defs/quantity"}, {"type": "null"}]},
        "ac": {
          "oneOf": [
            {"type": "null"},
            {
              "type": "object", "additionalProperties": false,
              "required": ["magnitude", "phase"],
              "properties": {"magnitude": {"$ref": "#/$defs/quantity"}, "phase": {"$ref": "#/$defs/quantity"}}
            }
          ]
        },
        "waveform": {
          "type": "object", "additionalProperties": false,
          "required": ["kind", "parameters"],
          "properties": {
            "kind": {"enum": ["none", "sine", "pulse"]},
            "parameters": {"type": "object", "additionalProperties": {"$ref": "#/$defs/quantity"}}
          }
        }
      }
    },
    "component": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "type", "pin_ids", "value", "model_ref", "parameters", "source", "visual_ref"],
      "properties": {
        "id": {"$ref": "#/$defs/id"},
        "type": {"enum": ["resistor", "capacitor", "inductor", "voltage_source", "current_source", "nmos", "pmos", "unknown"]},
        "pin_ids": {"$ref": "#/$defs/ids"},
        "value": {"oneOf": [{"$ref": "#/$defs/quantity"}, {"type": "null"}]},
        "model_ref": {"$ref": "#/$defs/nullable_id"},
        "parameters": {"type": "object", "additionalProperties": false, "properties": {"width": {"$ref": "#/$defs/quantity"}, "length": {"$ref": "#/$defs/quantity"}}},
        "source": {"oneOf": [{"$ref": "#/$defs/source"}, {"type": "null"}]},
        "visual_ref": {"$ref": "#/$defs/nullable_id"}
      }
    },
    "pin": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "component_id", "role", "visual_ref"],
      "properties": {
        "id": {"$ref": "#/$defs/id"}, "component_id": {"$ref": "#/$defs/id"},
        "role": {"enum": ["a", "b", "positive", "negative", "drain", "gate", "source", "bulk", "unknown"]},
        "visual_ref": {"$ref": "#/$defs/nullable_id"}
      }
    },
    "net": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "is_ground"],
      "properties": {"id": {"$ref": "#/$defs/id"}, "is_ground": {"type": "boolean"}}
    },
    "connection": {
      "type": "object", "additionalProperties": false,
      "required": ["pin_id", "net_id", "visual_refs", "confidence"],
      "properties": {
        "pin_id": {"$ref": "#/$defs/id"}, "net_id": {"$ref": "#/$defs/id"},
        "visual_refs": {"$ref": "#/$defs/ids"}, "confidence": {"$ref": "#/$defs/confidence"}
      }
    },
    "label": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "text", "scope", "net_id", "visual_ref"],
      "properties": {
        "id": {"$ref": "#/$defs/id"}, "text": {"type": "string", "minLength": 1, "maxLength": 64},
        "scope": {"const": "flat"}, "net_id": {"$ref": "#/$defs/nullable_id"}, "visual_ref": {"$ref": "#/$defs/nullable_id"}
      }
    },
    "visual_entity": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "kind", "bbox", "position", "orientation", "points", "text", "method", "confidence"],
      "properties": {
        "id": {"$ref": "#/$defs/id"},
        "kind": {"enum": ["symbol", "pin", "wire", "junction", "ground", "label", "text", "unknown"]},
        "bbox": {"oneOf": [{"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number", "minimum": 0}}, {"type": "null"}]},
        "position": {"oneOf": [{"$ref": "#/$defs/point"}, {"type": "null"}]},
        "orientation": {"enum": ["r0", "r90", "r180", "r270", "r0_mirror", "r90_mirror", "r180_mirror", "r270_mirror", "unknown"]},
        "points": {"type": "array", "items": {"$ref": "#/$defs/point"}},
        "text": {"type": ["string", "null"], "maxLength": 256},
        "method": {"type": "string", "minLength": 1, "maxLength": 64},
        "confidence": {"$ref": "#/$defs/confidence"}
      }
    },
    "ambiguity": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "kind", "target_refs", "candidates", "state", "selected_candidate_id", "resolution_note"],
      "properties": {
        "id": {"$ref": "#/$defs/id"},
        "kind": {"enum": ["symbol_type", "value", "crossing", "wire_gap", "label_attachment", "pin_mapping", "body_connection"]},
        "target_refs": {"$ref": "#/$defs/ids"},
        "candidates": {
          "type": "array", "items": {
            "type": "object", "additionalProperties": false,
            "required": ["id", "description"],
            "properties": {"id": {"$ref": "#/$defs/id"}, "description": {"type": "string", "minLength": 1, "maxLength": 256}}
          }
        },
        "state": {"enum": ["unresolved", "resolved"]},
        "selected_candidate_id": {"$ref": "#/$defs/nullable_id"},
        "resolution_note": {"type": ["string", "null"], "maxLength": 256}
      }
    },
    "finding": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "code", "severity", "target_refs", "message", "visual_refs"],
      "properties": {
        "id": {"$ref": "#/$defs/id"}, "code": {"$ref": "#/$defs/id"},
        "severity": {"enum": ["ERROR", "WARNING", "AMBIGUOUS", "CONFIRMED"]},
        "target_refs": {"$ref": "#/$defs/ids"}, "message": {"type": "string", "minLength": 1, "maxLength": 512},
        "visual_refs": {"$ref": "#/$defs/ids"}
      }
    }
  }
}
```

## Complete Illustrative Draft

The following is an authored **manual voltage-divider draft**, not vision output or a simulation result. Image reference and visual records are intentionally empty for M2. All pins are mapped, but `draft` grants no review/export/execution permission. No numerical result is claimed.

```json
{
  "schema_version": "0.2-draft1",
  "metadata": {"circuit_id": "divider_demo", "revision": 0, "origin": "manual", "catalog_version": "phase_a_draft1"},
  "source_image_reference": null,
  "components": [
    {"id": "V1", "type": "voltage_source", "pin_ids": ["V1.positive", "V1.negative"], "value": null, "model_ref": null, "parameters": {}, "source": {"dc": {"literal": "1", "si_value": "1", "unit": "V", "grammar": "manual"}, "ac": {"magnitude": {"literal": "1", "si_value": "1", "unit": "V", "grammar": "manual"}, "phase": {"literal": "0", "si_value": "0", "unit": "deg", "grammar": "manual"}}, "waveform": {"kind": "none", "parameters": {}}}, "visual_ref": null},
    {"id": "R1", "type": "resistor", "pin_ids": ["R1.a", "R1.b"], "value": {"literal": "2k", "si_value": "2000", "unit": "ohm", "grammar": "spice"}, "model_ref": null, "parameters": {}, "source": null, "visual_ref": null},
    {"id": "R2", "type": "resistor", "pin_ids": ["R2.a", "R2.b"], "value": {"literal": "2k", "si_value": "2000", "unit": "ohm", "grammar": "spice"}, "model_ref": null, "parameters": {}, "source": null, "visual_ref": null}
  ],
  "pins": [
    {"id": "V1.positive", "component_id": "V1", "role": "positive", "visual_ref": null},
    {"id": "V1.negative", "component_id": "V1", "role": "negative", "visual_ref": null},
    {"id": "R1.a", "component_id": "R1", "role": "a", "visual_ref": null},
    {"id": "R1.b", "component_id": "R1", "role": "b", "visual_ref": null},
    {"id": "R2.a", "component_id": "R2", "role": "a", "visual_ref": null},
    {"id": "R2.b", "component_id": "R2", "role": "b", "visual_ref": null}
  ],
  "nets": [{"id": "n0", "is_ground": true}, {"id": "nin", "is_ground": false}, {"id": "nout", "is_ground": false}],
  "connections": [
    {"pin_id": "V1.positive", "net_id": "nin", "visual_refs": [], "confidence": {"score": null, "basis": "manual", "calibrated": false}},
    {"pin_id": "V1.negative", "net_id": "n0", "visual_refs": [], "confidence": {"score": null, "basis": "manual", "calibrated": false}},
    {"pin_id": "R1.a", "net_id": "nin", "visual_refs": [], "confidence": {"score": null, "basis": "manual", "calibrated": false}},
    {"pin_id": "R1.b", "net_id": "nout", "visual_refs": [], "confidence": {"score": null, "basis": "manual", "calibrated": false}},
    {"pin_id": "R2.a", "net_id": "nout", "visual_refs": [], "confidence": {"score": null, "basis": "manual", "calibrated": false}},
    {"pin_id": "R2.b", "net_id": "n0", "visual_refs": [], "confidence": {"score": null, "basis": "manual", "calibrated": false}}
  ],
  "labels": [
    {"id": "label_in", "text": "vin", "scope": "flat", "net_id": "nin", "visual_ref": null},
    {"id": "label_out", "text": "vout", "scope": "flat", "net_id": "nout", "visual_ref": null}
  ],
  "visual": {"coordinate_space": "original_pixels", "entities": []},
  "confidence": {"score": null, "basis": "manual", "calibrated": false},
  "ambiguities": [],
  "warnings": [],
  "validation_state": {"status": "draft", "validated_revision": null, "ruleset_version": null, "findings": []}
}
```

## Geometry, Alternatives and Revisions

`bbox` means `[x, y, width, height]`; `position` and `points` use original-image pixel coordinates. Store normalized-image transforms in extraction-run evidence outside the canonical electrical model, and convert geometry back before assembly. Orientation belongs to visual provenance, not simulator syntax. Validate every coordinate against original dimensions; image-origin records must have a source reference.

Candidate descriptions are display text, not executable patches. A chosen candidate or manual correction is applied through typed review actions, then references, graph and diagnostics are rebuilt atomically. A resolved ambiguity must identify an existing candidate or a nonempty manual-resolution note. Unsupported candidates cannot be approved into the supported profile.

Increment revision for circuit/image/model/configuration edits. Recompute canonical electrical hash over schema/catalog versions, components, pins, nets, connections and labels in sorted, normalized form; ignore visual scores/report text for electrical equivalence. Approval also binds the image hash/revision and generated artifact hash so changing evidence cannot reuse stale consent. Persist approvals in an app-managed envelope, not provider-owned JSON. See [approval state contract](validation-rules.md) and [ADR-004](adr/004-human-approval.md).

Schema-valid records with `status=reviewed` supplied by an import/provider remain untrusted. Fresh validation and human review are mandatory; a serialized state flag is never authorization.
