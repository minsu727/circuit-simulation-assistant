"""Synthetic display fixtures using existing analyzers; no simulator/API."""
import numpy as np
from ac_result_analysis import analyze_ac
from transient_result_analysis import analyze_transient
from dc_result_analysis import analyze_dc
from parameter_sweep_execution import SweepPoint


def display_results():
    frequency = np.logspace(1, 6, 501)
    ac = analyze_ac(frequency, 10 / (1 + 1j * frequency / 10000), np.ones(501))
    ac.target_name, ac.reference_name = 'V(vout)', 'V(vin)'
    time = np.linspace(0, .001, 2001)
    transient = analyze_transient(time, .5 * np.sin(2 * np.pi * 10000 * time),
                                  .01 * np.sin(2 * np.pi * 10000 * time),
                                  measurements=['Voltage Gain', 'Output Swing'])
    transient.target_name, transient.reference_name = 'V(vout)', 'V(vin)'
    dc = analyze_dc(np.linspace(3.4, 3.7, 31), np.linspace(1.7, 1.85, 31),
                    measurements=['Minimum', 'Maximum', 'Value at Sweep Point'], point=3.55)
    dc.sweep_source, dc.target_name = 'V2', 'V(vout)'
    points = [SweepPoint('1k', 1000, 'OK', {'Low-Frequency Gain [dB]': ac.low_frequency_gain_db,
                                          '-3 dB Bandwidth [Hz]': ac.bandwidth_hz}, result=ac),
              SweepPoint('2k', 2000, 'Simulation Failed', {}, notes=['Intentional display-fixture failure.'])]
    return ac, transient, dc, points
