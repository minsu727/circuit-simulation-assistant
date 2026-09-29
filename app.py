import streamlit as st
import json
import hashlib
import re
from pathlib import Path
from runtime_paths import is_packaged, locate_ltspice, MISSING_LTSPICE, LTspiceNotFoundError
from simulation_runner import run_ltspice
from ac_analysis import parse_request, build_ac_directive, apply_analysis_directive
from ac_reference import suggest_ac_references
from ac_result_analysis import read_ac_result, MissingTraceError, format_frequency, gain_figure
from transient_analysis import is_transient_request, parse_transient_request, build_transient_directive, MEASUREMENTS
from transient_result_analysis import read_transient_result, waveform_figure, format_value
from dc_analysis import (is_dc_request, parse_dc_request, build_dc_directive, dc_value,
                         source_unit, validate_sweep_source, MEASUREMENTS as DC_MEASUREMENTS)
from dc_result_analysis import read_dc_result, dc_figure, trace_unit
from parameter_sweep import (is_parameter_sweep_request, parse_parameter_sweep, validate_parameter_sweep,
                             ANALYSES as PARAMETER_ANALYSES, MEASUREMENTS as PARAMETER_MEASUREMENTS,
                             generate_sweep_values, validate_asc_component, ComponentNotFoundError)
from parameter_sweep_execution import (run_parameter_sweep, validate_sweep_analysis, comparison_table,
                                       comparison_summary, comparison_figures, overlay_figure)
from analysis_summary import build_analysis_summary, build_sweep_summary
from ai_interpretation import build_interpretation_prompt, prompt_as_text
from dataclasses import replace
from llm_client import load_config, interpret_analysis, input_estimate, SECTIONS
from ui_helpers import (REUSABLE_FIELDS, review_defaults, requested_dc_point,
                        asc_voltage_traces, trace_suggestion, human_value, show_graph,
                        compact_comparison_rows, compact_extrema_rows,
                        show_point_evidence, show_dc_requested_point)
from ui_presentation import (page_style, show_workflow, review_card, approval_note,
                             metric_grid, technical_error, directive_details,
                             simulation_evidence, show_summary_sections, show_saved_result)

PROJECT_DIR = Path(__file__).resolve().parent


def circuit_history():
    if circuit_file is None:
        return {}
    digest = hashlib.sha256(circuit_file.getvalue()).hexdigest()
    return st.session_state.setdefault('successful_review_conditions', {}).setdefault(digest, {})


def remember_successful_review(analysis):
    circuit_history()[analysis] = {field: st.session_state.get(f'review_{field}', '')
                                   for field in REUSABLE_FIELDS.get(analysis, ())}


def accept_trace(field, candidate):
    st.session_state[field] = candidate
    reset_approval()


def show_ac_reference_suggestions():
    # Explicit edits and same-circuit successful history already populate this
    # field. Never overwrite either; candidates require a separate user click.
    if st.session_state.get('review_reference', '').strip() or circuit_file is None:
        return
    hints = suggest_ac_references(circuit_file.getvalue())
    for notice in hints.notices:
        st.caption(notice + ' Manual reference entry is available.')
    if hints.candidates:
        st.caption(('Possible AC references' if hints.ambiguous else 'Suggested from AC excitation')
                   + ': ' + ', '.join(hints.candidates))
        if hints.ambiguous:
            st.caption('Multiple sources or labels may be involved. No reference has been selected.')
        for candidate in hints.candidates:
            st.button(f'Use suggestion: {candidate}', key=f'ac_reference_{candidate}',
                      on_click=accept_trace, args=('review_reference', candidate))


def show_trace_suggestions(available, source='circuit labels'):
    fields = [('review_target','Target'), ('review_dc_comparison','Comparison')] if st.session_state.get('review_analysis_type') == 'DC Sweep' else [('review_target','Target'), ('review_reference','Reference')]
    for field, label in fields:
        requested = st.session_state.get(field,'')
        candidate = trace_suggestion(requested, available)
        if candidate:
            st.warning(f'{requested} not found in {source}. Did you mean {candidate}?')
            st.caption(f'Suggested from available traces: {candidate}. Select to use it, then review and approve again.')
            st.button(f'Use {candidate} for {label}', key=f'trace_suggestion_{source}_{field}',
                      on_click=accept_trace, args=(field,candidate))
    if available:
        with st.expander(f'Available {source}'):
            st.text(', '.join(available))
            if source == 'circuit labels':
                st.caption('Named ASC voltage nodes only; RAW may contain additional nodes and device currents. Suggestions require your selection and renewed approval.')


def clear_analysis_preview():
    st.session_state.pop('completed_analysis_summary', None)
    st.session_state.pop('prepared_interpretation', None)
    clear_ai_result()


def clear_ai_result():
    st.session_state.pop('ai_interpretation_result', None)


def remember_analysis_summary(summary):
    st.session_state['completed_analysis_summary'] = summary
    st.session_state.pop('prepared_interpretation', None)
    clear_ai_result()


def show_ai_execution(prompt):
    try:
        # Missing secrets.toml is normal. Never display or cache the credential.
        try:
            secrets = st.secrets.to_dict()
        except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
            secrets = {}
        config = load_config(secrets)
        if config.provider not in ('openai', 'mock'):
            raise ValueError('Unsupported provider')
    except (ValueError, TypeError):
        st.error('Invalid LLM configuration. Check environment variables or Streamlit secrets.')
        return
    with st.expander('AI settings / Advanced'):
        provider = st.selectbox('AI Provider', ['openai', 'mock'],
                            index=['openai', 'mock'].index(config.provider),
                            key='ai_provider', on_change=clear_ai_result)
        model = st.text_input('AI Model', value=config.model, key='ai_model', on_change=clear_ai_result)
    config = replace(config, provider=provider, model=model.strip())
    estimate = input_estimate(prompt)
    with st.expander('Request size and model details'):
        st.caption(f"Selected model: {config.model} | Input characters: {estimate['characters']} | "
                   f"Conservative token estimate: ~{estimate['token_estimate']} (UTF-8 bytes; not billing tokens).")
    st.caption('OpenAI sends this prepared prompt to the API and may incur cost. Only Run AI Interpretation makes a call.')
    if provider == 'mock':
        st.caption('Demonstration mode · No API call or cost. Output is a fixed example, not circuit analysis.')
    elif not config.api_key:
        st.info('API key not configured')
        st.caption('Deterministic simulation analysis is fully available. Optional AI interpretation is unavailable until a key is configured.')
    too_large = estimate['characters'] > config.max_input_characters
    if too_large:
        st.warning('Prompt exceeds the configured input limit. Reduce sweep points before preparing again.')
    if st.button('Run AI Interpretation', disabled=(provider == 'openai' and not config.api_key) or too_large or not model.strip()):
        clear_ai_result()
        with st.spinner('Preparing AI interpretation...' if provider == 'mock' else 'Calling OpenAI...'):
            st.session_state['ai_interpretation_result'] = interpret_analysis(prompt, config)
    result = st.session_state.get('ai_interpretation_result')
    if result is None:
        return
    if result['status'] == 'error':
        st.error(result['error'])
        return
    with st.expander('Interpretation details'):
        st.caption(f"Interpretation provider: {result['provider']} | model: {result['model']}")
    st.caption('AI text is separate from verified measurements. Numerical checks do not prove correct trace/point attribution or physical causes.')
    if result['warnings']:
        st.warning('AI response validation warning')
        with st.expander('AI validation details'):
            st.json(result['warnings'])
    if result['data'] is not None:
        for key, title in SECTIONS.items():
            st.subheader(title)
            st.text('\n'.join(result['data'][key]) or 'No supported content supplied.')
    else:
        st.warning('Unverified raw response — not confirmed measurement results.')
        st.text(result['raw_text'] or '(empty response)')


def begin_results():
    global results_rendered
    if not results_rendered:
        st.divider()
        st.subheader('4. Results')
        results_rendered = True


def show_analysis_summary():
    show_workflow(workflow_slot, circuit_file is not None, simulation_request, st.session_state)
    summary = st.session_state.get('completed_analysis_summary')
    if summary is None:
        if not results_rendered:
            begin_results()
            st.caption('Results will appear here after an approved simulation run.')
        return
    had_result_ui = results_rendered
    begin_results()
    if not had_result_ui:
        show_saved_result(summary)
    st.subheader('Analysis Summary')
    st.caption('Verified measurements and deterministic comparisons only. No circuit-cause inference.')
    show_summary_sections(summary)
    if summary.get('analysis_type') != 'Parameter Sweep' and not had_result_ui:
        evidence = summary.get('evidence', {})
        with st.expander('Result Evidence / Details'):
            st.text('RAW: ' + str(evidence.get('raw_file') or 'Not generated'))
            st.text('LOG: ' + str(evidence.get('log_file') or 'Not generated'))
            st.text('Directive: ' + str(evidence.get('applied_directive') or 'Not applied'))
            for note in summary.get('simulation_conditions', {}).get('calculation_notes', []):
                st.text(note)
    show_point_evidence(summary)
    st.divider()
    st.subheader('AI Interpretation')
    st.caption('Optional · Deterministic results above do not require AI. Actual API response quality has not yet been validated.')
    st.info('Prepare locally, then explicitly run AI interpretation. Simulation approval does not authorize an API call.')
    if st.button('Prepare AI Interpretation'):
        clear_ai_result()
        try:
            st.session_state['prepared_interpretation'] = build_interpretation_prompt(summary)
        except (ValueError, TypeError) as error:
            st.error(f'Prompt preparation failed: {error}')
    prompt = st.session_state.get('prepared_interpretation')
    if prompt is not None:
        with st.expander('Interpretation Prompt Preview'):
            st.text(prompt_as_text(prompt))
        with st.expander('Structured Facts Preview'):
            st.json(prompt['user']['analysis_summary'])
        st.caption('Prepared locally only. Local evidence paths are omitted; numerical facts retain their supplied values.')
        st.download_button('Download Interpretation Prompt JSON',
                           data=json.dumps(prompt, ensure_ascii=False, allow_nan=False, indent=2),
                           file_name='interpretation_prompt.json', mime='application/json')
        show_ai_execution(prompt)


def show_evidence_figure(figure, raw_file, filename):
    show_graph(figure)
    if not raw_file:
        return []
    path = Path(raw_file).parent / filename
    try:
        figure.savefig(path, dpi=130)
    except OSError as error:
        st.caption('Graph displayed; evidence file could not be saved.')
        with st.expander('Graph save details'):
            st.text(str(error))
        return []
    return [str(path.resolve())]



def reset_approval():
    if st.session_state.get('execution_approved') or st.session_state.get('parameter_approved'):
        st.session_state['ui_approval_changed'] = True
    st.session_state["execution_approved"] = False
    st.session_state["parameter_approved"] = False
    clear_analysis_preview()


def reset_review():
    reset_approval()
    st.session_state["show_conditions"] = False

st.set_page_config(
    page_title="Circuit Simulation Assistant",
    layout="wide"
)

page_style()
st.title("Circuit Simulation Assistant")
st.write('Natural-language setup and deterministic LTspice analysis.')
st.caption('Upload an LTspice schematic, describe your simulation, review the settings, and run only after approval.')
if is_packaged() and locate_ltspice() is None:
    st.warning(MISSING_LTSPICE)
workflow_slot = st.empty()
results_rendered = False


# -------------------------
# 1. Circuit file
# -------------------------

st.subheader('Circuit & Request')
circuit_column, request_column = st.columns([1, 2], gap='large')
with circuit_column:
    st.markdown('**1. Circuit**')
    circuit_file = st.file_uploader(
        "Upload an LTspice schematic file", type=["asc"], on_change=reset_review
    )
    if circuit_file is None:
        st.caption('Upload an LTspice .asc schematic to begin.')
    else:
        st.caption('Schematic loaded')
        st.text(circuit_file.name)
        st.caption(f'{len(circuit_file.getvalue()) / 1024:.1f} KB · ASC schematic')
    st.caption('.asc only · Your source file is preserved. Runs use a separate execution copy.')


# -------------------------
# 2. Natural-language request
# -------------------------

with request_column:
    st.markdown('**2. Request**')
    simulation_request = st.text_area(
        "Describe what simulation you want to run",
        placeholder='V(out)을 10 Hz부터 1 MHz까지 AC simulation하고 V(vin) 대비 gain과 -3 dB bandwidth를 구해줘.',
        on_change=reset_review, height=130
    )
    with st.expander('Request examples'):
        st.caption('Use trace and component names from your own circuit; review every extracted condition.')
        st.text('AC: V(out) V(in), 10 Hz to 1 MHz, gain and -3 dB bandwidth.\n'
                'Transient: V(out) V(in), 1 ms, voltage gain and output swing.\n'
                'DC: V1 from 0 V to 5 V step 0.1 V; V(out) at V1=3 V.\n'
                'Parameter: R1을 1k, 2k, 5k로 바꿔가며 AC gain 비교.')
    st.caption('Analyze Request prepares editable settings. It does not run a simulation.')


# -------------------------
# Rule-based parser
# -------------------------

with request_column:
    analyze_requested = st.button('Analyze Request', type='primary')
if analyze_requested:
    reset_approval()

    if circuit_file is None:
        st.warning("Please upload an LTspice .asc file first.")

    elif not simulation_request.strip():
        st.warning("Please enter a simulation request.")

    else:
        st.session_state["show_conditions"] = True
        parameter_request = is_parameter_sweep_request(simulation_request)
        st.session_state["show_parameter_sweep"] = parameter_request
        history = circuit_history()
        if parameter_request:
            parsed = parse_parameter_sweep(simulation_request)
            analysis = parsed['analysis_type']
            for field, value in parsed.items():
                st.session_state[f'parameter_{field}'] = ', '.join(value) if field == 'values' else value
        else:
            dc_followup = (requested_dc_point(simulation_request) and 'DC Sweep' in history
                           and not re.search(r'\b(?:ac|tran|transient)\b|교류',simulation_request,re.I))
            analysis = ('Transient' if is_transient_request(simulation_request) else
                        'DC Sweep' if is_dc_request(simulation_request) or dc_followup else
                        parse_request(simulation_request)['analysis_type'])
        detail, reused = review_defaults(simulation_request, analysis, history.get(analysis))
        for field, value in detail.items():
            st.session_state[f'review_{field}'] = value
        st.session_state['review_reference'] = detail.get('reference', '')
        st.session_state['reused_review_fields'] = reused
        if parameter_request and analysis == 'DC Sweep' and detail.get('dc_point'):
            st.session_state['parameter_measurements'] = list(dict.fromkeys(
                st.session_state['parameter_measurements'] + ['Value at Sweep Point']))


# -------------------------
# 3. Structured conditions
# -------------------------

parameter_mode = st.session_state.get("show_parameter_sweep", False)
parameter_valid = True
if st.session_state.get("show_conditions", False) and parameter_mode:
    st.divider()
    st.subheader("3. Simulation Review")
    st.markdown('**Parameter Sweep · Component values**')
    st.caption("Review every value and the analysis settings below. Execution requires final approval.")
    sweep_type = st.selectbox("Sweep Type", ["Component Value"], key="parameter_sweep_type", on_change=reset_approval)
    component = st.text_input("Component", key="parameter_component", on_change=reset_approval)
    mode = st.selectbox("Value Input", ["Explicit Values", "Start / Stop / Step"], key="parameter_value_mode", on_change=reset_approval)
    # Review both input forms; file edits and simulation runs require final approval.
    values = st.text_input("Values (comma-separated)", key="parameter_values", disabled=mode != "Explicit Values", on_change=reset_approval)
    start = st.text_input("Start", key="parameter_start", disabled=mode != "Start / Stop / Step", on_change=reset_approval)
    stop = st.text_input("Stop", key="parameter_stop", disabled=mode != "Start / Stop / Step", on_change=reset_approval)
    step = st.text_input("Step", key="parameter_step", disabled=mode != "Start / Stop / Step", on_change=reset_approval)
    analysis = st.selectbox("Analysis Type", PARAMETER_ANALYSES, key="parameter_analysis_type", on_change=reset_approval)
    measurements = st.multiselect("Measurements", PARAMETER_MEASUREMENTS, key="parameter_measurements", on_change=reset_approval)
    st.caption("Execution supports resistors and capacitors. SPICE suffixes: k = 1000, m/M = 0.001, Meg = 1000000. Maximum 100 points; an off-grid Stop is not appended.")
    conditions = dict(sweep_type=sweep_type, component=component.strip(), value_mode=mode,
                      values=[value.strip() for value in values.split(",")], start=start, stop=stop, step=step,
                      analysis_type=analysis, measurements=measurements)
    valid = True
    try:
        found_component = validate_asc_component(circuit_file.getvalue(), component)
        st.success(f"Component found: {found_component}")
    except ComponentNotFoundError as error:
        valid = False
        st.error(str(error))
        st.write("Available components in uploaded ASC:")
        st.code(", ".join(error.available) or "(none)", language="text")
    except ValueError as error:
        valid = False
        st.error(str(error))
    try:
        parameter_values = generate_sweep_values(conditions)
        if component.strip()[0].upper() not in 'RC':
            raise ValueError('Execution supports resistors and capacitors only.')
        st.write(f"Sweep points: {len(parameter_values)}")
        st.code(', '.join(str(value) for value in parameter_values), language='text')
    except ValueError as error:
        valid = False
        st.error(str(error))
    parameter_valid = valid
    parameter_conditions = conditions
    parameter_measurements = measurements
    if analysis == 'Not specified':
        st.checkbox('Select analysis settings before approval.', key='parameter_approved', disabled=True)
        show_analysis_summary()
        st.stop()
    st.session_state['review_analysis_type'] = analysis

if st.session_state.get("show_conditions", False):

    if not parameter_mode:
        st.divider()
        st.subheader("3. Simulation Review")
    st.caption("Conditions were extracted using rules. Review and correct them before approval.")
    if st.session_state.get('reused_review_fields'):
        st.caption('Initial values reused from the last successful analysis of this circuit: '
                   + ', '.join(st.session_state['reused_review_fields']) + '. Review and approve before execution.')

    analysis_type = st.session_state['parameter_analysis_type'] if parameter_mode else st.selectbox(
        "Analysis Type",
        [
            "AC",
            "DC Sweep",
            "Transient",
            "Operating Point",
            "Noise",
            "Transfer Function",
            "Fourier"
        ],
        key="review_analysis_type",
        on_change=reset_approval
    )

    signal_columns = st.columns(2)
    target = signal_columns[0].text_input(
        "Target Signal / Current" if analysis_type == "DC Sweep" else "Target Signal",
        key="review_target",
        on_change=reset_approval
    )

    ac_conditions = None
    transient_conditions = None
    dc_conditions = None
    directive_error = None
    if analysis_type == "AC":
        # Restore parsed defaults if switching analysis removed hidden widget state.
        for field, value in parse_request(simulation_request).items():
            st.session_state.setdefault(f"review_{field}", value)

        reference = signal_columns[1].text_input(
            "Reference / Input Signal", key="review_reference",
            placeholder="Enter the input voltage trace name from your circuit",
            on_change=reset_approval
        )
        with signal_columns[1]:
            show_ac_reference_suggestions()

        sweep_columns = st.columns(2)
        sweep_type = sweep_columns[0].selectbox(
            "Sweep Type",
            ["Decade", "Octave", "Linear"],
            key="review_sweep_type",
            on_change=reset_approval
        )

        points = sweep_columns[1].number_input(
            "Points", min_value=1, step=1, key="review_points",
            help="Points per decade/octave; total points for a linear sweep.",
            on_change=reset_approval
        )

        frequency_columns = st.columns(2)
        start_frequency = frequency_columns[0].text_input(
            "Start Frequency",
            key="review_start_frequency",
            on_change=reset_approval
        )

        stop_frequency = frequency_columns[1].text_input(
            "Stop Frequency",
            key="review_stop_frequency",
            on_change=reset_approval
        )

        measurements = parameter_measurements if parameter_mode else st.multiselect(
            "Measurements",
            [
                "Gain",
                "-3 dB Bandwidth",
                "Phase",
                "Peak Gain"
            ],
            key="review_measurements",
            on_change=reset_approval
        )
        st.caption("Voltage gain uses Target / Reference from RAW data. Low-frequency gain and -3 dB bandwidth assume a low-pass response. Phase and Peak Gain measurements are not implemented yet.")
        ac_conditions = dict(sweep_type=sweep_type, points=points,
                             start_frequency=start_frequency, stop_frequency=stop_frequency)
        try:
            directive_preview = build_ac_directive(**ac_conditions)
            directive_details(directive_preview)
            if not target.strip() or not reference.strip():
                raise ValueError("Enter both Target Signal and Reference / Input Signal before approval.")
        except ValueError as error:
            directive_error = str(error)
            st.error(directive_error)
    elif analysis_type == "Transient":
        for field, value in parse_transient_request(simulation_request).items():
            st.session_state.setdefault(f"review_{field}", value)
        reference = signal_columns[1].text_input("Reference / Input Signal", key="review_reference",
                                  help="Optional unless Voltage Gain is requested.", on_change=reset_approval)
        time_columns = st.columns(3)
        stop_time = time_columns[0].text_input("Stop Time", key="review_stop_time", on_change=reset_approval)
        start_saving_time = time_columns[1].text_input("Start Saving Time (optional)", key="review_start_saving_time", on_change=reset_approval)
        maximum_timestep = time_columns[2].text_input("Maximum Timestep (optional)", key="review_maximum_timestep", on_change=reset_approval)
        measurements = parameter_measurements if parameter_mode else st.multiselect("Measurements", MEASUREMENTS, key="review_transient_measurements", on_change=reset_approval)
        st.caption("Vpp gain requires stable periodic input/output. Edge and step-response metrics are shown only when the waveform supports them.")
        transient_conditions = dict(stop_time=stop_time, start_saving_time=start_saving_time, maximum_timestep=maximum_timestep)
        try:
            directive_preview = build_transient_directive(**transient_conditions)
            directive_details(directive_preview)
            if not target.strip():
                raise ValueError("Enter Target Signal before approval.")
            if "Voltage Gain" in measurements and not reference.strip():
                raise ValueError("Enter Reference / Input Signal for Voltage Gain.")
        except ValueError as error:
            directive_error = str(error)
            st.error(directive_error)
    elif analysis_type == "DC Sweep":
        for field, value in parse_dc_request(simulation_request).items():
            st.session_state.setdefault(f"review_{field}", value)
        sweep_source = st.text_input("Sweep Source", key="review_sweep_source", on_change=reset_approval)
        value_columns = st.columns(3)
        dc_start = value_columns[0].text_input("Start Value", key="review_dc_start", on_change=reset_approval)
        dc_stop = value_columns[1].text_input("Stop Value", key="review_dc_stop", on_change=reset_approval)
        dc_step = value_columns[2].text_input("Step Value", key="review_dc_step", on_change=reset_approval)
        comparison = signal_columns[1].text_input("Optional Comparison Signal / Current", key="review_dc_comparison", on_change=reset_approval)
        measurements = parameter_measurements if parameter_mode else st.multiselect("Measurements", DC_MEASUREMENTS, key="review_dc_measurements", on_change=reset_approval)
        selected_point = st.text_input("Selected Sweep Point (for Value at Sweep Point)", key="review_dc_point", on_change=reset_approval)
        st.caption("One ascending voltage/current source sweep. Difference = Target − Comparison. Matching Error = abs(Target − Comparison) / abs(Target) × 100%; Target is the denominator. Near-zero denominators have no result.")
        dc_conditions = dict(sweep_source=sweep_source, start_value=dc_start, stop_value=dc_stop, step_value=dc_step)
        dc_point = None
        try:
            directive_preview = build_dc_directive(**dc_conditions)
            directive_details(directive_preview)
            target_unit = trace_unit(target.strip())
            if comparison.strip():
                trace_unit(comparison.strip())
            if any(name in measurements for name in ("Difference", "Absolute Difference", "Matching Error")):
                if not comparison.strip() or trace_unit(comparison.strip()) != target_unit:
                    raise ValueError("Enter a comparison trace with the same physical unit for Difference / Matching Error.")
            if "Value at Sweep Point" in measurements:
                unit = source_unit(sweep_source.strip())
                point = dc_value(selected_point, unit)
                if not dc_value(dc_start, unit) <= point <= dc_value(dc_stop, unit):
                    raise ValueError("Selected Sweep Point must be within Start/Stop; no extrapolation.")
                dc_point = float(point)
        except ValueError as error:
            directive_error = str(error)
            st.error(directive_error)
    else:
        st.warning(
            "For this analysis, this version runs the directive already saved in the uploaded .asc file. "
            "Review the circuit's saved directive before approving execution."
        )

    with st.expander('Original request'):
        st.text(simulation_request)
    if circuit_file is not None:
        show_trace_suggestions(asc_voltage_traces(circuit_file.getvalue()))
    review_card(st.session_state, analysis_type, parameter_mode)
    approval_box = st.container(border=True)
    approval_box.markdown('**Approve & Run**')

    if parameter_mode:
        settings = ac_conditions if analysis_type == 'AC' else transient_conditions if analysis_type == 'Transient' else dc_conditions
        parameter_reference = comparison if analysis_type == 'DC Sweep' else reference
        parameter_point = dc_point if analysis_type == 'DC Sweep' else None
        try:
            validate_sweep_analysis(analysis_type, settings, target, parameter_reference, measurements, parameter_point)
        except ValueError as error:
            directive_error = str(error)
            st.error(directive_error)
        approved = approval_box.checkbox('I reviewed all Parameter Sweep values and analysis conditions and approve execution.',
                               key='parameter_approved', disabled=not parameter_valid or directive_error is not None)
        with approval_box:
            approval_note(approved, st.session_state.get('ui_approval_changed', False))
            run_requested = st.button('Run Parameter Sweep', type='primary', disabled=not approved or not parameter_valid or directive_error is not None)
        if run_requested:
            begin_results()
            clear_analysis_preview()
            try:
                if not approved or not parameter_valid or directive_error is not None:
                    raise ValueError('Review and approve valid Parameter Sweep conditions before execution.')
                progress = st.progress(0.)
                with st.spinner('Running Parameter Sweep...'):
                    sweep_results = run_parameter_sweep(circuit_file, parameter_conditions, settings, target,
                                                        parameter_reference, parameter_point, approved=approved,
                                                        progress=lambda done, total: progress.progress(done/total))
                st.subheader('Comparative Results')
                completed = sum(entry.result is not None for entry in sweep_results)
                st.info(f'Parameter Sweep finished: {completed}/{len(sweep_results)} points analyzed. See each point status and notes.')
                st.dataframe(compact_comparison_rows(comparison_table(sweep_results, component)), hide_index=True)
                summary = comparison_summary(sweep_results)
                if summary:
                    st.caption('Extrema use valid measurements only; ties use the first point. Delta is last minus first valid value in requested order.')
                    st.dataframe(compact_extrema_rows(summary), hide_index=True)
                for index, entry in enumerate(sweep_results):
                    if getattr(entry, 'failure', None) and entry.failure.get('available_traces'):
                        show_trace_suggestions(entry.failure['available_traces'], f'RAW point {index+1}')
                graph_paths = []
                evidence_raw = next((entry.raw for entry in sweep_results if entry.result is not None), None)
                for index, figure in enumerate(comparison_figures(sweep_results, component).values()):
                    graph_paths.extend(show_evidence_figure(figure, evidence_raw, f'parameter_comparison_{index}.png'))
                overlay = overlay_figure(sweep_results, component, analysis_type)
                if overlay is not None:
                    st.caption('Overlay shows up to the first 8 available curves; all points remain in the table.')
                    graph_paths.extend(show_evidence_figure(overlay, evidence_raw, 'parameter_overlay.png'))
                remember_analysis_summary(build_sweep_summary(sweep_results, component, analysis_type,
                    conditions=dict(parameter_conditions, analysis_settings=settings, target_signal=target,
                                    reference_signal=parameter_reference, selected_point=parameter_point), graph_paths=graph_paths))
                if any(entry.result is not None for entry in sweep_results):
                    remember_successful_review(analysis_type)
            except Exception as error:
                technical_error('Parameter Sweep failed. Review the details before trying again.', error)
        show_analysis_summary()
        st.stop()

    approved = approval_box.checkbox(
        "I reviewed the simulation conditions and directive and approve execution.",
        key="execution_approved", disabled=directive_error is not None
    )
    with approval_box:
        approval_note(approved, st.session_state.get('ui_approval_changed', False))
        run_requested = st.button(
            'Run Simulation', type='primary',
            disabled=not approved or circuit_file is None or not simulation_request.strip() or directive_error is not None
        )
    if run_requested:
        begin_results()
        clear_analysis_preview()
        summary_result, summary_error = None, None
        raw_file, log_file, applied_directive = None, None, None
        simulation_failed = False
        graph_paths = []
        try:
            if not approved or circuit_file is None or not simulation_request.strip():
                raise ValueError("Review the circuit and approve execution before running.")
            if directive_error:
                raise ValueError(directive_error)
            with st.spinner("Running LTspice simulation..."):
                raw_file, log_file, applied_directive = run_ltspice(
                    circuit_file, ac_conditions, transient_conditions=transient_conditions,
                    dc_conditions=dc_conditions, approved=approved
                )

            st.success("Simulation completed")

            simulation_evidence(raw_file, log_file, applied_directive)

        except Exception as e:
            summary_error, simulation_failed = e, True
            raw_file, log_file = getattr(e, 'raw_file', None), getattr(e, 'log_file', None)
            technical_error(MISSING_LTSPICE if isinstance(e, LTspiceNotFoundError) else 'LTspice simulation failed.', f'{type(e).__name__}: {e}')
        else:
            if applied_directive and analysis_type == "AC":
                st.subheader("Measured Results")
                try:
                    with st.spinner('Reading RAW data and analyzing the AC response...'):
                        result = read_ac_result(raw_file, target, reference)
                    summary_result = result
                    metric_grid([('Low-Frequency Gain', f'{result.low_frequency_gain_db:.3f} dB'),
                                 ('-3 dB Level', f'{result.threshold_db:.3f} dB'),
                                 ('-3 dB Bandwidth', human_value(result.bandwidth_hz, 'Hz')
                                  if result.bandwidth_hz is not None else result.bandwidth_status)])
                    st.caption(
                        f"{result.target_name} / {result.reference_name}. Low-pass estimate: median of "
                        f"{result.baseline_count} valid initial samples from {format_frequency(result.frequency[0])} "
                        f"to {format_frequency(result.baseline_stop_hz)}. Crossing interpolated in dB vs log10(frequency)."
                    )
                    if result.notes:
                        with st.expander('AC analysis notes'):
                            for note in result.notes:
                                st.warning(note)
                    graph_paths = show_evidence_figure(gain_figure(result), raw_file, 'gain_frequency.png')
                except MissingTraceError as error:
                    summary_error = error
                    st.error(str(error))
                    st.write("Available RAW traces:")
                    st.code("\n".join(error.available), language="text")
                    show_trace_suggestions(error.available, 'RAW traces')
                except Exception as error:
                    summary_error = error
                    technical_error('AC result analysis failed. Simulation files remain available.', error)
            elif applied_directive and analysis_type == "Transient":
                st.subheader("Measured Results")
                try:
                    with st.spinner('Reading RAW data and analyzing the waveform...'):
                        result = read_transient_result(raw_file, target, reference, measurements)
                    summary_result = result
                    st.caption(f"Waveform assessment: {result.kind}. Measurements use saved data only.")
                    for name, measurement in result.measurements.items():
                        if measurement.values:
                            st.markdown(f'**{name}**')
                            metric_grid((label, human_value(value, unit)) for label, (value, unit) in measurement.values.items())
                        else:
                            st.info(f"{name}: Measurement not applicable / could not be reliably determined. {measurement.reason}")
                    if result.notes:
                        with st.expander('Transient analysis notes'):
                            for note in result.notes:
                                st.caption(note)
                    graph_paths = show_evidence_figure(waveform_figure(result), raw_file, 'transient_waveform.png')
                except MissingTraceError as error:
                    summary_error = error
                    st.error(str(error))
                    st.write("Available RAW traces:")
                    st.code("\n".join(error.available), language="text")
                    show_trace_suggestions(error.available, 'RAW traces')
                except Exception as error:
                    summary_error = error
                    technical_error('Transient result analysis failed. Simulation files remain available.', error)
            elif applied_directive and analysis_type == "DC Sweep":
                st.subheader("Measured Results")
                try:
                    with st.spinner('Reading RAW data and analyzing the DC sweep...'):
                        result = read_dc_result(raw_file, target, comparison, measurements, dc_point,
                                                sweep_source=sweep_source.strip())
                    summary_result = result
                    st.caption(f"Target: {result.target_name}; Comparison: {result.comparison_name if result.comparison is not None else 'none'}. Sweep: {result.sweep_source}.")
                    if result.point is not None:
                        st.caption(f"Selected point: {result.sweep_source} = {result.point:.9g} {source_unit(result.sweep_source)}")
                    show_dc_requested_point(result)
                    metric_grid((label, human_value(value, unit)) for label, (value, unit) in result.metrics.items()
                                if not (label == 'Value at Sweep Point' and result.point is not None))
                    if result.notes:
                        with st.expander('DC analysis notes'):
                            for note in result.notes:
                                st.info(note)
                    if result.curves:
                        table = {f"{result.sweep_source} [{source_unit(result.sweep_source)}]": result.sweep,
                                 result.target_name: result.target, result.comparison_name: result.comparison}
                        table.update({f"{name} [{unit}]": values for name, (values, unit) in result.curves.items()})
                        with st.expander('DC comparison samples'):
                            st.dataframe(table, hide_index=True, width='stretch')
                    graph_paths = show_evidence_figure(dc_figure(result), raw_file, 'dc_sweep.png')
                except MissingTraceError as error:
                    summary_error = error
                    st.error(str(error))
                    st.write("Available RAW traces:")
                    st.code("\n".join(error.available), language="text")
                    show_trace_suggestions(error.available, 'RAW traces')
                except Exception as error:
                    summary_error = error
                    technical_error('DC result analysis failed. Simulation files remain available.', error)
        if analysis_type in ('AC', 'Transient', 'DC Sweep'):
            if summary_result is not None and summary_error is None:
                remember_successful_review(analysis_type)
            summary_settings = ac_conditions if analysis_type == 'AC' else transient_conditions if analysis_type == 'Transient' else dc_conditions
            remember_analysis_summary(build_analysis_summary(analysis_type, summary_result,
                conditions=dict(summary_settings or {}, target_signal=target, measurements=measurements,
                                reference_signal=comparison if analysis_type == 'DC Sweep' else reference),
                evidence=dict(raw_file=raw_file, log_file=log_file, applied_directive=applied_directive, graph_paths=graph_paths),
                error=summary_error, status='Simulation Failed' if simulation_failed else None))

show_analysis_summary()
