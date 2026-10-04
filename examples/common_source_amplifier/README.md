# Public Common-Source NMOS Example

This small amplifier lets a fresh-clone user try real AC and Transient simulation without the private MOSFET coursework schematic. It was created specifically for this repository from generic circuit elements and a self-contained educational NMOS model; it is not derived from private coursework material.

## Circuit

- `VDD`: 10 V supply; `R1`: 2 kΩ from `vdd` to `vout`.
- `M1`: common-source NMOS, drain at `vout`, gate at `vin`, source/body grounded. The schematic defines `DEMO_NMOS`, a simplified Level-1 model (`VTO=1`, `KP=1m`, `LAMBDA=0.02`, `W/L=20u/10u`).
- `V1`: gate bias of 2 V, with a 1 kHz sine of 5 mV peak amplitude (`SINE(2 5m 1k)`); AC amplitude is 1 V.
- `C1`: 10 nF from `vout` to ground, providing a low-pass output response.

The circuit uses standard LTspice symbols. No separate vendor model or private include file is needed. The transistor model demonstrates the workflow rather than characterizing a real device.

## Open and run

**Install LTspice separately.** Open [common_source_amplifier.asc](common_source_amplifier.asc) with **File → Open** in LTspice. Its saved directive is `.ac dec 100 10 1Meg`, so native Run performs AC analysis.

For the assistant, follow the main [Getting Started](../../README.md#getting-started), upload this ASC, and use either request below. The app runs an execution copy after approval; it does not edit the included source. The example is supplied with the repository, not bundled into the already-published v0.1.1 installer.

### AC

```text
V(vout)을 10 Hz부터 1 MHz까지 AC simulation하고 gain과 -3 dB bandwidth를 구해줘.
```

In Review, confirm Target `V(vout)` and Reference / Input `V(vin)` (select **Use suggestion: V(vin)** or enter it). Confirm Decade, 100 points per decade, Start 10 Hz, Stop 1 MHz. Approve, then Run Simulation.

Applied directive: `.ac dec 100 10 1Meg`.

### Transient

```text
V(vout)을 transient simulation하고 input과 output의 Vpp와 gain을 구해줘.
```

The request does not specify timing or the reference. In Review, set Target `V(vout)`, Reference / Input `V(vin)`, Stop Time **10 ms**, Start Saving Time **5 ms**, Maximum Timestep **2 us**, and measurement **Voltage Gain**. Approve, then Run Simulation. The app replaces the AC directive only in the execution copy.

Applied directive: `.tran 0 10m 5m 2u`.

## Representative results

Measured on Windows with LTspice 26.0.1 on 2026-10-04, using the existing assistant execution and Python analysis paths:

| Analysis | Measurement | Reference value |
| --- | --- | --- |
| AC | Low-frequency gain | 12.943 dB (approximately 4.438 V/V) |
| AC | -3 dB level | 9.943 dB |
| AC | -3 dB bandwidth | 8.256 kHz |
| Transient | Input Vpp | 10.000 mV |
| Transient | Output Vpp | 44.058 mV |
| Transient | Voltage gain | 4.406 V/V (12.881 dB) |

These are demo references, not hardcoded expectations. A difference of a few percent (roughly 5% as an initial comparison guide) can warrant checking simulator version, sweep resolution and timestep. Changes to bias, model, load, input frequency or amplitude can change results substantially.

AC uses `V(vout) / V(vin)`, the median of the first 10 gain samples, and log-frequency interpolation at the baseline minus 3 dB. Transient uses the last three complete input cycles, approximately 7–10 ms, and Output Vpp / Input Vpp. These gains are magnitudes; the Vpp result does not measure phase or inversion. Low-frequency AC and 1 kHz Transient results are different measurements, not a direct physical cross-validation. This sine input is not a step-response demo.

LTspice logged `Length shorter than recommended for a level 1 MOSFET` for `M1`. Both simulations completed; retain this warning when assessing the simplified model. Do not interpret these values as verified real-device performance.

## Compatibility evidence

Targeted Streamlit AppTest checks uploaded this file, parsed both requests, verified approval blocking, then ran actual LTspice once per analysis. The ASC parsed with all five components, node labels were recognized, and both RAW files contained `V(vin)` and `V(vout)`. RAW/LOG files, numerical metrics, Analysis Summary and graphs were produced.

The source was byte-identical before and after both runs. SHA-256:

```text
5736eb12ba0e4526381c89eb67a99d00150739c13d29954eeba2aa6c6e2338af
```

Only the source ASC and this guide are published. Execution copies and generated evidence remain in ignored `simulation_input/` and `simulation_output/` directories; packaged runs use the existing application data location. Native LTspice may create output beside the schematic, so keep those generated files out of commits.
