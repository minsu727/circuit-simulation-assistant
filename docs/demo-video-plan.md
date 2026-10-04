# Prompt 023 — Demo Video Script & Capture Plan

**Master:** 1:50 (110 seconds), Korean narration with English subtitles. **Purpose:** GitHub/project page, portfolio and engineering interview review. This is a recording plan, not a recorded video or a new validation run.

Use only the public [common_source_amplifier.asc](../examples/common_source_amplifier/common_source_amplifier.asc). The [example guide](../examples/common_source_amplifier/README.md) contains topology, review settings, measured references and model limitations. Keep the existing README unchanged until a real video is available.

## Preparation and exact inputs

Start the current app with LTspice installed separately. Prepare a clean browser session and the public ASC before recording. Use `mock` for AI: the existing developer setup supports `LLM_PROVIDER=mock`, or select **mock** in **AI settings / Advanced → AI Provider** after preparing the prompt. No API key or actual API call is needed. Do not record setup terminals.

The example is in the repository; the published v0.1.1 installer does not bundle it. Download the source example separately if recording the installed app. Do not rebuild or alter the release to make this demo.

### Primary AC request — paste without quotation marks

```text
V(vout)을 10 Hz부터 1 MHz까지 AC simulation하고 gain과 -3 dB bandwidth를 구해줘.
```

| Review field | Value/action |
| --- | --- |
| Analysis Type | AC |
| Target Signal | `V(vout)` |
| Reference / Input Signal | Select **Use suggestion: V(vin)**, or type `V(vin)` |
| Sweep Type | Decade |
| Points | 100 (points per decade) |
| Start / Stop Frequency | 10 Hz / 1 MHz |
| Measurements | Gain, -3 dB Bandwidth |
| Simulation Directive Preview | `.ac dec 100 10 1Meg` |

The request does not specify a Reference signal; selecting its suggestion is an explicit user action. Finish all edits before checking **I reviewed the simulation conditions and directive and approve execution.** Then click **Run Simulation**. Editing conditions invalidates approval, so re-approve if anything changes.

Reference results: low-frequency gain approximately **12.943 dB**, -3 dB level **9.943 dB**, bandwidth **8.256 kHz**. Use the actual values from the recorded run, not an overlay pretending these are exact universal constants.

### Optional Transient request — separate clip

```text
V(vout)을 transient simulation하고 input과 output의 Vpp와 gain을 구해줘.
```

After **Analyze Request**, confirm Transient and `V(vout)`, then enter Reference `V(vin)`, Stop Time **10 ms**, Start Saving Time **5 ms**, Maximum Timestep **2 us**, and measurement **Voltage Gain**. These timing/reference values are review edits, not extracted from this sentence. Preview: `.tran 0 10m 5m 2u`. Review, approve and run again.

Representative results: Input **10.000 mVpp**, Output **44.058 mVpp**, Gain **4.406 V/V**. The gain is a magnitude from the last three complete input cycles; it does not measure inversion. This sine-input example is not a rise/fall or settling-time demonstration.

## Master shot list — 110 seconds

Record the actual approved AC run. The times below are edit targets; simulator wait time varies. If needed, trim waiting only, mark the cut **“Simulation wait shortened”**, and keep approval → Run → completion in order. Never substitute a graph or mock simulation for a successful run.

| Time | Visible window and action | Highlight | Keep out of frame |
| --- | --- | --- | --- |
| 0:00–0:10 | App title and workflow overview; hold still. | Project name; request → review → approved run → results. | Desktop, other tabs, terminal and personal browser chrome. |
| 0:10–0:22 | App upload area; upload the public ASC and show its filename. Pause capture or cut away during the OS file picker. | `common_source_amplifier.asc`; caption: “Public common-source NMOS example”. | File dialog directories, recent/private files, usernames and absolute paths. |
| 0:22–0:34 | Request field; paste the exact AC text, briefly hold, click **Analyze Request**. | `V(vout)`, 10 Hz–1 MHz, gain / bandwidth. | Clipboard manager, terminal or unrelated browser content. |
| 0:34–0:50 | Review area; select **Use suggestion: V(vin)**, show fields and **Simulation Directive Preview**. Show disabled Run before checking approval; check approval last. | Target / Reference, range, Points, directive and separate approval control. | Available-node lists if too long; any open Evidence/technical panels. Do not present suggested Reference as automatically accepted. |
| 0:50–1:12 | Click **Run Simulation**; show actual running state, then **Simulation completed**, metrics and AC graph. Use one cut from metrics to graph if they do not fit together. | Approximately 12.943 dB and 8.256 kHz; gain curve, threshold and bandwidth marker. | **Simulation Files / Evidence**, **Graph save details** and local output paths. Do not open them. |
| 1:12–1:26 | Scroll once to **Analysis Summary → Confirmed Measurements**. Hold the readable measurement table. | Structured facts; measured values agree with Results. | **View structured summary**, **Result Evidence / Details**, **Point Details / Evidence**, **Warning details**; raw Summary can contain local paths. |
| 1:26–1:42 | Show **AI Interpretation**; click **Prepare AI Interpretation**, open **AI settings / Advanced**, select/confirm **mock**, then separately click **Run AI Interpretation**. Hold the mock notice and response. | Local preparation; separate action; persistent overlay: **“Mock demonstration · No API call · Not circuit interpretation”**. | API credentials/settings outside these controls, path-containing JSON and unreviewed preview text. Keep the app's mock disclaimer visible. |
| 1:42–1:50 | Simple closing card or app Results still; no new run. | “LTspice → RAW → Python/NumPy → Summary → optional interpretation”; public example and repository name. | Private URLs, file paths or claims of universal validation. |

### Visual emphasis

- Request and Review are the first focus. Keep the disabled Run and approval checkbox legible; do not move past them before the viewer can read them.
- Then give metrics and the graph separate holds if necessary. Use a modest editorial crop only when labels are too small; preserve graph axes, units, legend and bandwidth marker.
- Summary uses the human-readable table, not a long JSON scroll. AI follows the deterministic results and stays visibly optional/mock.
- Plan three scroll destinations: Review, Results, Summary/AI. Move the cursor directly to each control, hold it away from numbers after clicking, and avoid circles, repeated zooms or continuous scrolling.

## Korean narration

These blocks follow the shot timestamps. Read naturally; use the remaining hold time for the viewer to inspect controls. If the spoken track needs more time, extend holds up to a total of 120 seconds rather than speeding through approval.

| Time | Narration |
| --- | --- |
| 0:00–0:10 | LTspice 실험에서는 조건 설정, 실행, 측정을 반복합니다. 이 프로젝트는 그 흐름을 자연어 요청과 검토 화면으로 연결합니다. |
| 0:10–0:22 | 사용자가 작성한 회로를 업로드합니다. 여기서는 공개 예제인 공통 소스 NMOS 증폭기를 사용합니다. 원본 회로는 유지하고, 실행에는 복사본을 씁니다. |
| 0:22–0:34 | 출력 노드의 AC 응답을 10 헤르츠부터 1 메가헤르츠까지 요청합니다. 구할 값은 gain과 마이너스 3 데시벨 대역폭입니다. |
| 0:34–0:50 | 추출된 조건과 directive를 확인하고 입력 기준 신호를 선택합니다. 잘못 해석된 조건이 바로 실행되지 않도록, 사용자가 최종 승인해야 Run이 활성화됩니다. |
| 0:50–1:12 | 승인 후 실제 LTspice를 실행합니다. RAW 데이터의 출력과 입력 비율로 gain을 계산합니다. 이 실행에서는 약 12.943 데시벨, 대역폭은 약 8.256 킬로헤르츠입니다. 수치는 Python과 NumPy가 계산하고 LLM에 맡기지 않습니다. |
| 1:12–1:26 | 측정값은 Analysis Summary로 정리됩니다. 확인된 사실과 파생 결과, 경고를 구분해서 이후 해석에 쓸 수 있도록 합니다. |
| 1:26–1:42 | AI 해석은 측정 이후의 선택 단계이며, 별도 실행이 필요합니다. 지금 화면은 API를 호출하지 않는 고정 mock 예시입니다. 실제 모델의 회로 해석이나 API 검증 결과는 아닙니다. |
| 1:42–1:50 | 핵심은 자연어 요청을 검토한 뒤, 원본을 보존하며 실제 시뮬레이션과 수치 분석을 연결하는 것입니다. |

## English subtitle / script

Use these as meaning-equivalent subtitles, split into short cues of at most two lines. The timestamps are scene windows, not final subtitle cue lengths; adjust cues to the recorded narration.

| Time | English text |
| --- | --- |
| 0:00–0:10 | LTspice experiments involve repeated setup, simulation and measurement. This project connects those steps through a natural-language request and review workflow. |
| 0:10–0:22 | Upload a user-created schematic. This demo uses the public common-source NMOS example. Simulations run on a copy, preserving the original. |
| 0:22–0:34 | Request the output AC response from 10 Hz to 1 MHz, including gain and the -3 dB bandwidth. |
| 0:34–0:50 | Review the parsed conditions and directive, then select the input reference. Run remains disabled until the user approves the final settings. |
| 0:50–1:12 | LTspice runs the approved simulation. Python and NumPy calculate gain from the output-to-input ratio in the RAW data. This run gives about 12.943 dB and an 8.256 kHz bandwidth. The LLM does not compute these measurements. |
| 1:12–1:26 | Analysis Summary organizes confirmed measurements, derived results and warnings for a separate interpretation stage. |
| 1:26–1:42 | Optional interpretation requires another explicit action. This is a fixed mock demonstration with no API call, not an actual model interpretation or API validation. |
| 1:42–1:50 | Review the request, preserve the schematic, and connect real simulation to deterministic numerical analysis. |

If the recording differs from the reference, update the numeric narration/subtitles to match the real run. Do not relabel the private MOSFET screenshots as results from this example.

## Optional Transient clip — 45 seconds, separate from master

| Time | Capture/action |
| --- | --- |
| 0:00–0:08 | Public ASC already uploaded; paste the exact Transient request and click Analyze Request. |
| 0:08–0:23 | Enter `V(vin)`, 10 ms / 5 ms / 2 us and Voltage Gain in Review. Show the `.tran` preview, then approve. |
| 0:23–0:33 | Run actual LTspice and hold completion plus metrics: about 10.000 mVpp input, 44.058 mVpp output and 4.406 V/V gain. |
| 0:33–0:45 | Hold waveform axes/legend and the gain measurement. Caption: “Vpp gain magnitude · Python calculation · Last three complete input cycles”. |

Optional voice line: “같은 공개 회로에서 시간 조건과 입력 기준을 검토하고 승인합니다. 실제 파형에서 입력과 출력 Vpp를 계산하며, gain은 두 Vpp의 비율입니다.” English: “Review and approve the timing and input reference for the same public circuit. Python measures input and output Vpp from the waveform; gain is their ratio.” Do not call this formal AC–Transient cross-validation.

## Recording setup

| Setting | Starting point |
| --- | --- |
| Capture | Free recorder with window/region capture, such as an already available OBS Studio or Windows screen recorder; no paid tool required. Select the app browser window, not the entire desktop. |
| Resolution / frame rate | 1920 × 1080, 30 fps; keep the app text readable at final 1080p export. |
| Browser | Maximize a clean browser window. Start at 100% browser zoom; try 110% only if text is hard to read and all required fields still fit. This is browser zoom, not an app feature. |
| Frame | Crop browser tabs, address/bookmark bars, profile avatar and Windows taskbar. Full-screen browser mode is optional; inspect the actual capture bounds before recording. |
| Terminal | Hidden throughout. Do not show app launch commands, environment variables, credentials or terminal history. |
| Cursor / audio | Cursor visible for clicks; park it away from metrics afterward. Record Korean voice separately if easier; mute desktop notifications and unrelated audio. |
| Edit | Use simple cuts and short captions. Keep actual execution sequence intact and label trimmed waiting. Preserve graph aspect ratio; no decorative animation needed. |

## Privacy and accuracy checklist

Before recording:

- [ ] Only the public `common_source_amplifier.asc` is used; no private schematic or coursework files.
- [ ] File picker and recent-files views are outside capture; no personal absolute path appears.
- [ ] RAW/LOG/Evidence, graph-save details, original Summary JSON and technical error panels are closed.
- [ ] No API key, email, username, Git credential or sensitive terminal output is visible.
- [ ] Private browser tabs/windows are closed; profile name, bookmarks, address bar and taskbar are cropped.
- [ ] Desktop notifications are disabled; short test recording reviewed frame by frame.
- [ ] Review fields, Reference selection and approval are visible before Run.
- [ ] AI provider is confirmed `mock` before Run AI Interpretation; its disclaimer and overlay remain visible.
- [ ] Results and captions reflect the actual recorded run; graph labels and units are legible.

After editing, review the entire export again, including transition frames and any overlays. Prompt path filtering is not a substitute for reviewing the recording. If an error occurs, inspect details off camera and record a new valid take; do not edit failure into apparent success.

### Claim boundaries and supporting records

| Claim | Supported basis / permitted wording |
| --- | --- |
| Public example and real AC/Transient results | [Example guide](../examples/common_source_amplifier/README.md): actual LTspice 26.0.1 runs, graph/Summary generation and source hash preservation. References vary with model/settings/version; the Level-1 channel-length warning remains documented. |
| Approval and copy-based execution | Example compatibility evidence and current app Review/Run controls. No silently accepted Reference suggestion. |
| Deterministic analysis | LTspice provides RAW; Python/NumPy computes measurements. AC bandwidth assumes low-pass response. |
| AI stage | [AI architecture](devlog/08-ai-interpretation-architecture.md): Summary-only prompt, separate action, mock/fake tests. Master shows fixed mock output, not real AI inference. |
| 183 automated tests | [Validation record](validation.md): historical full-suite/fresh-clone result with core plus optional LLM dependencies. Not a new test run in this planning task. |
| DC / Parameter Sweep | Existing implemented and recorded workflows in Validation; not demonstrated or validated with this public amplifier in the master clip. |
| Windows v0.1.1 and graceful shutdown | [Release notes](releases/v0.1.1.md): developer-host packaging and repeated shutdown evidence; not a new packaging test here. |

Do not claim clean Windows VM validation, universal Windows compatibility, actual OpenAI API smoke validation, formal AC–Transient/DC–Transient physical cross-validation, or AI numerical measurement. LTspice remains a separate installation. The installer is unsigned and SmartScreen warnings are possible. Do not imply the simplified model is a validated real transistor.

Keep the master focused on the shown AC path; test counts and release/shutdown history can stay in the linked documentation rather than becoming extra shots.

## Ready-to-use captions

- **GitHub:** “Public NMOS demo: natural-language AC request → review and approval → real LTspice run → deterministic gain and bandwidth. Optional interpretation is shown in mock mode.”
- **Portfolio:** “A reviewed simulation workflow that preserves the source schematic, measures LTspice RAW results in Python, and separates quantitative evidence from optional interpretation.”
- **Resume/project description:** “Developed a Windows/Streamlit LTspice assistant with explicit execution approval, deterministic Python analysis and a reproducible public NMOS demo circuit.”

Use these once an actual recording is ready. No video URL, placeholder image or fabricated GIF is added by this task.

## Optional silent GIF — 26 seconds

| Time | Frame/action | Short caption |
| --- | --- | --- |
| 0:00–0:05 | Public ASC already uploaded; paste AC request. | Request: 10 Hz–1 MHz |
| 0:05–0:12 | Analyze; select `V(vin)` and hold range/Points. | Review Target / Reference |
| 0:12–0:16 | Show disabled Run, check approval, click Run. | Explicit approval |
| 0:16–0:19 | Actual running state; label a cut if wait is trimmed. | Real LTspice execution |
| 0:19–0:26 | Completed metrics and AC graph, using one cut if needed. | Python gain / -3 dB bandwidth |

No AI, narration, terminals, Evidence or JSON. Keep axes and metric labels readable; use 8–12 fps for the GIF and avoid a busy cursor. Export only after recording a genuine successful run; no GIF binary is created here.

## Planning verification

The fixture path exists. Requests and settings match the example guide and current AC/Transient parser and Review controls. UI action/expander labels and mock semantics were checked against the current source without editing or running it. Representative metrics match the public example documentation; validation claims come from the linked records. No simulation, API call, test suite, binary rebuild or capture was performed for Prompt 023. Final link/privacy/whitespace checks and source preservation are reported with delivery.
