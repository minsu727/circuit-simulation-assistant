# M1 Acceptance Matrix — m1-local-v1

Authority: [Test Plan](test-plan.md), [Validation Plan](validation-plan.md) and [parent rules](../validation-rules.md). The static [catalog](../../../tests/fixtures/circuit_ir/catalog.json) contains exactly the planned **38 cases: 8 VALID / 20 INVALID / 10 AMBIGUOUS**. Each path is relative to `tests/fixtures/circuit_ir/` and contains an authored `circuit.json` / `expected.json` pair.

The pre-existing `valid/simple_source_resistor` pair is preserved and tested as a supplemental regression, outside the 38-case distribution. There are **39 pairs on disk**, not 39 planned acceptance cases. The separate `serialization_draft.json` remains the M1B serialization golden, not a circuit acceptance case.

## Planned Cases

| ID | Fixture | Category / boundary | Primary finding | Stage |
| --- | --- | --- | --- | --- |
| V01 | valid/resistor_divider | VALID / validation | No blocking findings | graph_dc |
| V02 | valid/rc_low_pass | VALID / validation | No blocking findings | graph_dc |
| V03 | valid/rlc_network | VALID / validation | No blocking findings | graph_dc |
| V04 | valid/current_source_load | VALID / validation | No blocking findings | graph_dc |
| V05 | valid/nmos_common_source | VALID / validation | CHECK_DEFERRED (WARNING) | component_value_source |
| V06 | valid/pmos_current_source | VALID / validation | CHECK_DEFERRED, DC_REFERENCE_UNPROVEN (WARNING) | graph_dc |
| V07 | valid/nmos_differential_pair | VALID / validation | CHECK_DEFERRED, DC_REFERENCE_UNPROVEN (WARNING) | graph_dc |
| V08 | valid/equal_parallel_dc_sources | VALID / validation | SOURCE_CONSTRAINT_CONFLICT (WARNING) | graph_dc |
| I01 | invalid/duplicate_component_id | INVALID / validation | DUPLICATE_ID | ids |
| I02 | invalid/duplicate_pin_id | INVALID / validation | DUPLICATE_ID | ids |
| I03 | invalid/missing_ground | INVALID / validation | GROUND_MISSING | ground |
| I04 | invalid/conflicting_grounds | INVALID / validation | GROUND_MISSING | ground |
| I05 | invalid/missing_resistor_role | INVALID / validation | PIN_ROLES_INVALID | pins |
| I06 | invalid/unknown_net_reference | INVALID / validation | BROKEN_REFERENCE | references |
| I07 | invalid/duplicate_connection | INVALID / validation | PIN_NET_INVALID | incidence |
| I08 | invalid/pin_in_two_nets | INVALID / validation | PIN_NET_INVALID | incidence |
| I09 | invalid/voltage_source_short | INVALID / validation | SOURCE_SAME_NET | component_value_source |
| I10 | invalid/current_source_short | INVALID / validation | SOURCE_SAME_NET | component_value_source |
| I11 | invalid/orphan_device | INVALID / validation | ORPHAN_DEVICE | pins |
| I12 | invalid/conflicting_labels | INVALID / validation | LABEL_CONFLICT | labels |
| I13 | invalid/floating_capacitive_node | INVALID / validation | FLOATING_DC_NODE | graph_dc |
| I14 | invalid/isolated_resistor_island | INVALID / validation | ISOLATED_SUBNETWORK | graph_dc |
| I15 | invalid/negative_resistor | INVALID / validation | VALUE_INVALID | component_value_source |
| I16 | invalid/wrong_capacitor_unit | INVALID / validation | VALUE_INVALID | component_value_source |
| I17 | invalid/pulse_timing_conflict | INVALID / validation | SOURCE_INVALID | component_value_source |
| I18 | invalid/conflicting_parallel_dc | INVALID / validation | SOURCE_CONSTRAINT_CONFLICT (ERROR) | graph_dc |
| I19 | invalid/raw_unsupported_type | INVALID classification / typed-load rejection | SCHEMA_INVALID | schema |
| I20 | invalid/broken_warning_reference | INVALID / validation | BROKEN_REFERENCE | references |
| A01 | ambiguous/mos_role_unknown | AMBIGUOUS / validation | PIN_ROLES_INVALID | pins |
| A02 | ambiguous/mos_body_unconnected | AMBIGUOUS / validation | MOS_BODY_UNRESOLVED | component_value_source |
| A03 | ambiguous/unknown_type_pending | AMBIGUOUS / validation | UNSUPPORTED_FEATURE | component_value_source |
| A04 | ambiguous/pin_connection_pending | AMBIGUOUS / validation | PIN_NET_INVALID | pins |
| A05 | ambiguous/label_attachment_pending | AMBIGUOUS / validation | LABEL_UNRESOLVED | labels |
| A06 | ambiguous/crossing_pending | AMBIGUOUS / validation | CROSSING_UNRESOLVED | ambiguity_confidence_provenance |
| A07 | ambiguous/source_dc_missing | AMBIGUOUS / validation | SOURCE_INVALID | component_value_source |
| A08 | ambiguous/value_ocr_alternatives | AMBIGUOUS / validation | VALUE_INVALID | component_value_source |
| A09 | ambiguous/mos_model_missing | AMBIGUOUS / validation | MODEL_INVALID | component_value_source |
| A10 | ambiguous/critical_confidence_unreviewed | AMBIGUOUS / validation | CONFIDENCE_REVIEW_REQUIRED | ambiguity_confidence_provenance |

Unless marked otherwise, invalid findings are ERROR; ambiguous findings are AMBIGUOUS. Expected files enumerate the **complete** fresh warning/root finding set and completed/skipped/deferred stage metadata, not just the primary column. Full prose is not frozen.

I19 never constructs a CircuitDocument: `load_document` returns `document=None`. Its expected contract is `outcome=load_rejected` with schema findings, without a fabricated `technical_state` or validation-stage envelope. The catalog's INVALID label is its benchmark classification. The other 37 cases reach graph building and `validate_document`; six structural failures correctly return no graph and suppress dependent checks.

## Additional Rule Boundaries Covered by Existing Focused Subcases

The approved plan explicitly assigns variants outside the 38 fixed cases to unit subcases. These are executable evidence, not extra catalog entries. Names below refer to the existing [structural tests](../../../tests/test_circuit_ir_validation.py) (`ValidationTests`), [semantic tests](../../../tests/test_circuit_ir_semantics.py) (`SemanticTests`), [graph tests](../../../tests/test_circuit_ir_graph.py), [schema tests](../../../tests/test_circuit_ir_schema.py), [value tests](../../../tests/test_circuit_ir_values.py) and [serialization tests](../../../tests/test_circuit_ir_serialization.py).

| Rule / boundary | Catalog anchors | Named focused subcases |
| --- | --- | --- |
| Closed schema, finite input, versions, no partial typed load | I19 | SchemaTests.test_unknown_nested_fields_are_not_dropped; test_wrong_future_and_malformed_versions; test_bad_shape_never_reaches_constructors; DecodeTests.test_duplicate_keys_rejected_at_any_depth_including_escaped_keys; test_nonfinite_constants_and_numeric_overflow_rejected |
| Global IDs, ownership, candidate/visual/endpoint references | I01–I02, I06, I20 | GraphTests.test_duplicate_definitions_for_every_global_namespace; test_cross_namespace_definition_collision_is_rejected; test_unknown_owner_has_one_root_issue; test_reference_types_do_not_resolve_against_unrelated_namespace; SemanticTests.test_bad_selected_candidate_is_still_the_existing_graph_reference_root |
| Canonical incidence and visual/electrical separation | I07–I08, A04, A06 | GraphTests.test_typed_adjacency_has_only_explicit_ownership_and_incidence; test_connection_views_retain_source_records_without_backwriting; test_round_trip_and_harmless_geometry_changes_preserve_topology |
| Roles/count/unknown mappings for all supported families | I05, A01–A02 | ValidationTests.test_missing_required_role_for_each_device_family; test_duplicate_known_role_is_error_for_each_family; test_wrong_role_and_extra_pin_are_errors; test_role_count_contradiction_takes_precedence_over_unknown_role |
| Ground and orphan suppression, empty document/stubs | I03–I04, I11 | ValidationTests.test_empty_document_is_not_vacuously_valid; test_device_without_connected_terminals_is_orphan; test_unused_and_single_pin_nets_have_no_invented_dangling_rule |
| Label conflict/unattached/reserved labels/aliases | I12, A05 | ValidationTests.test_whitespace_label_is_error; test_reserved_zero_label_must_attach_to_explicit_ground; test_alias_warning_is_fresh_nonblocking_and_requires_no_merge |
| Selected scalar grammar, finite exact SI, dimensions/positivity | I15–I16, A08 | ScalarTests.test_suffix_case_semantics_are_spice_not_generic_si; test_invalid_suffixes_and_expressions_are_rejected; test_low_decimal_context_cannot_round_a_long_coefficient; SemanticTests.test_passive_units_and_strict_positivity; test_selected_literal_si_mismatch_is_not_normalized; test_selected_quantity_without_si_value_does_not_acquire_defaults; test_parse_failure_suppresses_sign_range_duplicate |
| Source polarity, zero/signed DC, same-net failures | V01, V04, I09–I10, A07 | SemanticTests.test_signed_and_zero_source_dc_are_legal; test_source_dimension_is_not_inferred_from_device_name; test_missing_source_pin_suppresses_same_net_and_config_derivatives |
| AC / SINE / PULSE shape, unit, timing and valid sources | I17 | SemanticTests.test_valid_ac_zero_magnitude_and_signed_phase; test_ac_negative_magnitude_and_wrong_phase_dimension; test_sine_contract_and_signed_levels; test_sine_missing_extra_or_wrong_unit_parameters; test_sine_frequency_must_be_positive; test_none_waveform_rejects_parameters; test_pulse_timing_equality_is_exact_under_low_decimal_precision; test_pulse_negative_delay_zero_rise_and_unknown_keys |
| MOS body/model/W/L and forbidden fields on other types | V05–V07, A01–A02, A09 | SemanticTests.test_mos_missing_nonpositive_and_wrong_unit_dimensions; test_non_mos_model_and_sizing_fields_are_invalid; test_wrong_device_source_and_value_fields_are_invalid; test_missing_mos_bulk_role_suppresses_body_and_model_derivatives |
| Unsupported raw type versus unknown pending/not-pending | I19, A03 | SemanticTests.test_unknown_type_with_pending_choice_is_ambiguous_without_choice_is_error |
| R/L/V reference, C/I exclusion, floating/island/conditional nonlinear | V02–V07, I13–I14 | SemanticTests.test_current_source_does_not_prove_voltage_reference; test_mos_gate_does_not_provide_conditional_dc_reference; test_passive_bypass_is_warning_without_deleting_device |
| Exact DC constraints and bounded dynamic deferral | V08, I18 | SemanticTests.test_parallel_dc_source_difference_is_exact_beyond_float_precision; test_reversed_polarity_dc_constraints_use_explicit_sign; test_series_dc_loop_constraints_use_exact_sum; test_inductor_zero_potential_constraint_conflicts_with_nonzero_dc_source; test_parallel_explicit_ac_settings_are_compared_without_solver; test_direct_parallel_sine_and_pulse_conflicts_are_not_simulated; test_general_dynamic_equivalence_is_deferred_not_guessed |
| Declared choices, crossing/wire-gap, resolution contracts | A03, A06, A08 | SemanticTests.test_unresolved_generic_choice_and_resolution_do_not_change_connectivity; test_resolved_choice_requires_candidate_or_nonempty_manual_note; test_crossing_and_wire_gap_records_have_specific_root_codes; test_resolved_declared_wire_gap_remains_a_nonblocking_warning |
| Critical confidence and explicit item-specific resolution | A10 | SemanticTests.test_high_score_and_calibration_flags_do_not_approve_inferred_connections; test_unrelated_resolved_value_does_not_review_inferred_connection; test_bulk_resolution_cannot_review_inferred_gate_connection; test_referenced_inferred_visual_requires_explicit_review |
| Local provenance format, no image/model fetching | A06 | SemanticTests.test_image_origin_requires_reference_without_fetching_asset; test_declared_geometry_bounds_are_checked_without_image_decoding; test_complete_validation_uses_no_asset_model_network_or_process_access |
| Imported findings untrusted; severity and final stage completeness | I20, V05–V08 | ValidationTests.test_stale_imported_findings_are_not_copied_into_fresh_issues; test_independent_error_ambiguous_and_warning_preserve_severity_order; SemanticTests.test_required_stage_absent_cannot_be_valid_with_empty_issues; test_required_stage_skipped_cannot_be_valid_even_when_listed_complete; test_required_stage_deferred_cannot_be_valid_with_empty_issues; test_high_confidence_imported_reviewed_cannot_override_source_short |
| Round-trip, immutable input, deterministic IDs/order/stages | All 38 | [AcceptanceTests](../../../tests/test_circuit_ir_acceptance.py): test_typed_roundtrip_preserves_source_and_fresh_report; test_repeat_reports_include_stable_ids_order_and_stage_metadata; test_array_order_and_visual_geometry_cannot_change_canonical_topology; test_hash_seed_independence_in_separate_interpreters; test_static_fixtures_remain_read_only_without_snapshot_regeneration |

## Independence and Limits

27 new input pairs and their explicit expectations were authored from the plan before running validation. The 12 existing pairs are byte-preserved. A one-time stdlib authoring aid is outside tracked source under ignored `simulation_output/`; it does not import the validator or derive goldens from its results. Acceptance tests load static expected files, prohibit fixture writes during the pipeline, check hashes before/after, and offer no snapshot-update mode. No new semantic rules or issue codes were needed.

This matrix demonstrates scoped contract evidence, not measured code coverage or recognition accuracy. `VALID` means the deterministic **local** M1 profile passed. Model catalog resolution, image asset resolution, calibration, full export readiness and human approval remain deferred. No image/OCR/LLM call, circuit reconstruction, transistor operating-point proof, netlist generation or Circuit IR → LTspice execution is established here. See [M1 Status](status.md) for actual execution counts and the next boundary.
