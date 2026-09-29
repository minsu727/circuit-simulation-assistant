"""Presentation only: consume review state and existing deterministic summaries."""
import streamlit as st
from pathlib import Path

from ui_helpers import human_value, compact_comparison_rows, compact_extrema_rows, GRAPH_WIDTH_FRACTION


def page_style():
    # Theme colors remain Streamlit defaults. Wrap long labels/values on phones.
    st.markdown('''<style>
    .block-container {max-width:1280px; padding-top:2rem; padding-bottom:3rem;}
    [data-testid="stMetricValue"] {font-size:clamp(1.25rem,2.3vw,2rem); white-space:normal; overflow-wrap:anywhere;}
    [data-testid="stMetricLabel"] p, button p {overflow-wrap:anywhere;}
    </style>''', unsafe_allow_html=True)


def workflow_labels(uploaded, request, reviewing, approved, summary):
    status = summary.get('status') if summary else None
    result = {'OK': 'Measured', 'Completed': 'Measured',
              'Partial Measurements': 'Partial measurements',
              'Completed with warnings': 'Review point statuses',
              'Simulation Failed': 'Simulation failed', 'Analysis Failed': 'Analysis failed',
              'No Results': 'No results'}.get(status, 'Not run')
    return ['1 · Circuit — ' + ('Loaded' if uploaded else 'Upload needed'),
            '2 · Request — ' + ('Parsed' if reviewing else 'Ready to analyze' if request.strip() else 'Describe a request'),
            '3 · Review — ' + ('Approved' if approved else 'Approval needed' if reviewing else 'Waiting'),
            '4 · Results — ' + result]


def show_workflow(slot, uploaded, request, state):
    approval_key = 'parameter_approved' if state.get('show_parameter_sweep') else 'execution_approved'
    labels = workflow_labels(uploaded, request, state.get('show_conditions', False),
                             state.get(approval_key, False), state.get('completed_analysis_summary'))
    with slot.container():
        for column, label in zip(st.columns(4), labels):
            column.caption(label)


def review_card(state, analysis, parameter=False):
    def value(field):
        return str(state.get('review_' + field, '') or 'Not specified')
    rows = [('Target', value('target'))]
    if analysis in ('AC', 'Transient'):
        rows.append(('Reference / Input', value('reference')))
    if analysis == 'AC':
        rows.extend([('Frequency range', value('start_frequency') + ' → ' + value('stop_frequency')),
                     ('Sweep / Points', value('sweep_type') + ' / ' + value('points'))])
    elif analysis == 'Transient':
        rows.extend([('Stop time', value('stop_time')),
                     ('Saving start / Max timestep', value('start_saving_time') + ' / ' + value('maximum_timestep'))])
    elif analysis == 'DC Sweep':
        rows.extend([('Sweep source', value('sweep_source')),
                     ('Start / Stop / Step', ' / '.join(value(k) for k in ('dc_start', 'dc_stop', 'dc_step'))),
                     ('Requested point', value('dc_point'))])
    if parameter:
        mode = state.get('parameter_value_mode')
        values = (state.get('parameter_values', '') if mode == 'Explicit Values' else
                  ' / '.join(str(state.get('parameter_' + k, '')) for k in ('start', 'stop', 'step')))
        rows = [('Component', state.get('parameter_component', '')), ('Values', values)] + rows
    with st.container(border=True):
        st.markdown('**' + ('Parameter Sweep · ' if parameter else '') + analysis + ' — Review Settings**')
        columns = st.columns(2)
        for i, (label, text) in enumerate(rows):
            with columns[i % 2]:
                st.caption(label)
                st.text(text)


def approval_note(approved, changed):
    if approved:
        st.caption('Approved. Run starts LTspice using an execution copy of your schematic.')
    elif changed:
        st.caption('Settings changed. Please review and approve again.')
    else:
        st.caption('Review the settings, then approve to enable Run. Analyze Request does not run LTspice.')


def metric_grid(items):
    """Items are already formatted (label, display) pairs; no calculations."""
    items = list(items)
    for start in range(0, len(items), 3):
        chunk = items[start:start + 3]
        for column, (label, value) in zip(st.columns(len(chunk)), chunk):
            column.metric(label, value)


def technical_error(message, error):
    st.error(message)
    with st.expander('Technical details'):
        st.error(str(error))


def directive_details(directive):
    with st.expander('Simulation Directive Preview'):
        st.code(directive, language='text')


def simulation_evidence(raw, log, directive):
    with st.expander('Simulation Files / Evidence'):
        st.text(f'RAW: {raw}')
        st.text(f'LOG: {log}')
        if directive:
            st.caption('Applied Simulation Directive')
            st.code(directive, language='text')


def show_saved_result(summary):
    """Restore presentation on UI reruns using existing facts and graph files.

    No RAW reads, measurements, re-execution, or additions to Summary schema.
    Settings changes already clear this summary via the existing callback.
    """
    facts = summary.get('measured_facts', {})
    if summary.get('analysis_type') == 'Parameter Sweep':
        component = summary['simulation_conditions']['component']
        rows = [{component: p['parameter_label'], 'Status': p['status'], **p['measurements']}
                for p in facts.get('points', [])]
        if rows:
            st.subheader('Comparative Results')
            st.dataframe(compact_comparison_rows(rows), hide_index=True, width='stretch')
    else:
        items = []
        def collect(group):
            for label, item in group.items():
                if isinstance(item, dict) and 'value' in item and 'unit' in item:
                    display = human_value(item['value'], item['unit'])
                    if label == '-3 dB Bandwidth' and item['value'] is None:
                        display = 'Not found within sweep range' if any(w['code'] == 'bandwidth_not_found' for w in summary['warnings']) else 'Not available'
                    if label == 'Value at Sweep Point':
                        conditions = summary.get('simulation_conditions', {})
                        point, source = conditions.get('selected_point'), conditions.get('sweep_source', '')
                        if point is not None and source:
                            label = f"Value at {source} = {point:g} {'V' if source.upper().startswith('V') else 'A'}"
                    items.append((label, display))
                elif isinstance(item, dict):
                    collect(item)
        collect(facts)
        if items:
            st.subheader('Measured Results')
            metric_grid(items)
    for path in summary.get('evidence', {}).get('graph_paths', []):
        if not path:
            continue
        try:
            data = Path(path).read_bytes()
        except OSError:
            st.caption('A saved graph is unavailable; verified measurements and evidence references are retained.')
            continue
        side = (1 - GRAPH_WIDTH_FRACTION) / 2
        with st.columns([side, GRAPH_WIDTH_FRACTION, side], gap=None)[1]:
            st.image(data, width='stretch')


def show_summary_sections(summary):
    """Read-only display adapters; original JSON remains the source of truth."""
    facts = summary.get('measured_facts', {})
    rows = []
    def flatten(items, prefix=''):
        for name, item in items.items():
            if isinstance(item, dict) and 'value' in item and 'unit' in item:
                rows.append({'Measurement': prefix + name, 'Value': human_value(item['value'], item['unit']),
                             'Status': item.get('status', '')})
            elif isinstance(item, dict):
                flatten(item, prefix + name + ' / ')
    flatten(facts)
    st.markdown('**Confirmed Measurements**')
    if rows:
        st.dataframe(rows, hide_index=True, width='stretch')
    elif facts.get('points'):
        component = summary['simulation_conditions']['component']
        point_rows = [{component: row['parameter_label'], 'Status': row['status'], **row['measurements']}
                      for row in facts['points']]
        st.dataframe(compact_comparison_rows(point_rows), hide_index=True, width='stretch')
    else:
        st.caption('No verified measurements are available for this result.')
    trends = summary.get('derived_facts', {}).get('trends', {})
    if trends:
        st.markdown('**Derived Results**')
        st.dataframe([{'Measurement': name, 'Trend': trend['monotonic'].replace('_', ' '),
                       'Valid points': f"{trend['valid_points']} / {trend['total_points']}"}
                      for name, trend in trends.items()], hide_index=True, width='stretch')
    comparisons = summary.get('comparison_results', {}).get('extrema_and_changes', [])
    if comparisons:
        st.markdown('**Comparison Findings**')
        st.dataframe(compact_extrema_rows(comparisons), hide_index=True, width='stretch')
    warnings = summary.get('warnings', [])
    if warnings:
        st.markdown('**Warnings**')
        # Free-text messages may contain local error paths; show them in details.
        labels = list(dict.fromkeys(w['code'].replace('_', ' ') for w in warnings))
        st.warning('; '.join(labels) + '. See warning details before interpreting the results.')
        with st.expander('Warning details'):
            for item in warnings:
                where = f" · Point {item['point_index'] + 1}" if 'point_index' in item else ''
                st.text(item['code'].replace('_', ' ') + where + ': ' + item['message'])
    with st.expander('View structured summary'):
        st.json(summary)
