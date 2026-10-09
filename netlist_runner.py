"""M2 generated-copy adapter; real simulator imports are lazy and opt-in.

The v0.1 simulation_runner accepts uploads ending .asc, edits AscEditor blocks,
and uses SpiceEditor for ASC conversion. It is intentionally not called here.
The private M2F backend uses the public SimRunner Path API to preserve exact
text bytes. Test-only evidence is never RAW parsing/physics.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol
from uuid import uuid4
import json

from circuit_ir.execution import CompositionResult, ExecutionArtifact, ExecutionIssue, compose_execution_netlist
from circuit_ir.serialization import dump_document


@dataclass(frozen=True, slots=True)
class RunnerResult:
    success: bool
    return_code: int | None
    raw_file: Path | None
    log_file: Path | None
    message: str = ""

    def __post_init__(self):
        if type(self.success) is not bool:
            raise TypeError("success must be a native bool")
        if self.return_code is not None and type(self.return_code) is not int:
            raise TypeError("return_code must be an integer or None")
        for value in (self.raw_file, self.log_file):
            if value is not None and not isinstance(value, Path):
                raise TypeError("runner evidence must be a Path or None")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")


class NetlistRunner(Protocol):
    def run(self, netlist_path: Path, output_folder: Path) -> RunnerResult:
        """Run one generated copy; return process evidence without editing input."""
        ...


class RunStatus(str, Enum):
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class NetlistRunResult:
    """Paths/messages are local operational data; artifact provenance is portable."""
    status: RunStatus
    artifact: ExecutionArtifact | None
    working_file: Path | None
    raw_file: Path | None
    log_file: Path | None
    runner_result: RunnerResult | None
    issues: tuple[ExecutionIssue, ...]

    def __post_init__(self):
        if not isinstance(self.status, RunStatus):
            raise TypeError("status must be RunStatus")
        if type(self.issues) is not tuple:
            raise TypeError("issues must be an immutable tuple")
        if self.status is RunStatus.BLOCKED and any(v is not None for v in (
                self.artifact, self.working_file, self.raw_file, self.log_file, self.runner_result)):
            raise ValueError("Blocked runs contain no artifact, path or runner result")
        if self.status is RunStatus.SUCCESS and (self.issues or any(v is None for v in (
                self.artifact, self.working_file, self.raw_file, self.log_file, self.runner_result))):
            raise ValueError("Success requires complete verified process/file evidence")


def _safe_path(root: Path, path: Path):
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Workspace paths must be absolute without traversal")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Generated path escapes the caller-owned workspace")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or getattr(ancestor, "is_junction", lambda: False)():
            raise ValueError("Symlink/junction paths are not admitted")


def _write_new(root, path, content):
    _safe_path(root, path)
    with path.open("xb") as output:
        output.write(content)
    _safe_path(root, path)
    if path.read_bytes() != content:
        raise ValueError("Generated file did not preserve the exact approved bytes")


def _evidence(artifact):
    p = artifact.provenance
    # Explicit portable projection; no runtime folder, username or timestamp.
    return {"adapter_contract": p.adapter_contract, "exporter_contract": p.exporter_contract,
            "model_registry_version": p.model_registry_version, "model_registry_sha256": p.model_registry_sha256,
            "document_sha256": p.document_sha256, "electrical_sha256": p.electrical_sha256,
            "validation_sha256": p.validation_sha256, "circuit_approval_sha256": p.circuit_approval_sha256,
            "mapping_sha256": p.mapping_sha256, "base_netlist_sha256": p.base_netlist_sha256,
            "representation_approval_sha256": p.representation_approval_sha256, "request_sha256": p.request_sha256,
            "execution_approval_sha256": p.execution_approval_sha256, "execution_netlist_sha256": p.execution_netlist_sha256,
            "directive": artifact.directive, "trace_map": [list(row) for row in artifact.trace_map],
            "sweep_source_map": None if artifact.sweep_source_map is None else list(artifact.sweep_source_map)}


def run_generated_netlist(document, export_result, circuit_approval, representation_approval, request,
                            execution_approval, *, model_context, workspace_root: Path,
                            runner: NetlistRunner) -> NetlistRunResult:
    """Validate the entire chain before any filesystem/runner call.

    Fresh unique app-owned folders and exclusive writes preserve existing data.
    Failure evidence stays in the workspace; this API never deletes user files.
    Path checks reject existing traversal/symlinks/junctions, not a privileged
    security guarantee against a concurrent attacker changing the filesystem.
    """
    composed: CompositionResult = compose_execution_netlist(document, export_result, circuit_approval,
        representation_approval, request, execution_approval, model_context=model_context)
    if composed.artifact is None:
        return NetlistRunResult(RunStatus.BLOCKED, None, None, None, None, None, composed.issues)
    try:
        if not isinstance(workspace_root, Path) or not workspace_root.is_absolute() or ".." in workspace_root.parts:
            raise ValueError("workspace_root must be an existing absolute caller-owned Path")
        _safe_path(workspace_root, workspace_root)
        if not workspace_root.is_dir():
            raise ValueError("workspace_root must already exist")
        if not callable(getattr(runner, "run", None)):
            raise TypeError("runner must implement the injected NetlistRunner protocol")
        run_id = uuid4().hex
        input_folder = workspace_root / "simulation_input" / run_id / "m2"
        output_folder = workspace_root / "simulation_output" / run_id
        for path in (input_folder, output_folder):
            _safe_path(workspace_root, path)
        if input_folder.parent.exists() or output_folder.exists():
            raise ValueError("Generated run folder already exists; refusing overwrite")
    except (TypeError, ValueError, OSError) as error:
        return NetlistRunResult(RunStatus.BLOCKED, None, None, None, None, None,
                               (ExecutionIssue("WORKSPACE_INVALID", "workspace_root", str(error)),))
    artifact, working_file, process = composed.artifact, None, None
    try:
        # All current approval gates above precede this first side effect.
        input_folder.mkdir(parents=True, exist_ok=False)
        _safe_path(workspace_root, output_folder)
        output_folder.mkdir(parents=True, exist_ok=False)
        source_bytes = dump_document(document).encode("utf-8")
        base_bytes = export_result.spice_text.encode("utf-8")
        source_file, base_file = input_folder / "source.circuit.json", input_folder / "base.cir"
        _write_new(workspace_root, source_file, source_bytes)
        _write_new(workspace_root, base_file, base_bytes)
        evidence = (json.dumps(_evidence(artifact), sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
        _write_new(workspace_root, input_folder / "export-evidence.json", evidence)
        working_file = input_folder / "execution.cir"
        _write_new(workspace_root, working_file, artifact.netlist_bytes)
        for path, expected in ((source_file, source_bytes), (base_file, base_bytes), (working_file, artifact.netlist_bytes)):
            _safe_path(workspace_root, path)
            if path.read_bytes() != expected:
                raise ValueError("Saved execution/source/base differs from approved bytes")
        process = runner.run(working_file, output_folder)
        if not isinstance(process, RunnerResult):
            raise TypeError("runner must return RunnerResult")
        for path, expected in ((source_file, source_bytes), (base_file, base_bytes), (working_file, artifact.netlist_bytes)):
            _safe_path(workspace_root, path)
            if path.read_bytes() != expected:
                raise ValueError("Runner changed an approved source/base/execution copy")
        if not process.success or process.return_code != 0:
            return NetlistRunResult(RunStatus.FAILED, artifact, working_file, None, None, process,
                                   (ExecutionIssue("RUNNER_FAILED", "runner", process.message or "Runner did not report exit 0 success."),))
        for label, path in (("RAW", process.raw_file), ("LOG", process.log_file)):
            if path is None:
                raise ValueError(f"Runner did not return {label} evidence")
            _safe_path(output_folder, path)
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Runner did not produce nonempty {label} evidence")
        if process.raw_file.resolve() == process.log_file.resolve():
            raise ValueError("RAW and LOG evidence must be distinct files")
        return NetlistRunResult(RunStatus.SUCCESS, artifact, working_file, process.raw_file, process.log_file, process, ())
    except Exception as error:
        # Runner/editor failures are local failures, never approval/simulator success.
        return NetlistRunResult(RunStatus.FAILED, artifact, working_file, None, None,
                               process if isinstance(process, RunnerResult) else None,
                               (ExecutionIssue("RUN_ADAPTER_FAILED", None, str(error)),))


@dataclass(frozen=True, slots=True)
class NetlistSimulationResult:
    """Process/file evidence is distinct from successfully parsed analysis."""
    run: NetlistRunResult
    analysis: object | None
    diagnostics: tuple[str, ...]
    warnings: tuple[str, ...]
    executable: Path | None
    simulator_version: str | None

    @property
    def status(self):
        if self.run.status is not RunStatus.SUCCESS:
            return self.run.status
        return RunStatus.FAILED if self.diagnostics or self.analysis is None else RunStatus.SUCCESS


def _read_log(path):
    data = path.read_bytes()
    encoding = ("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff"))
                else "utf-16-le" if b"\x00" in data[:100] else "utf-8-sig")
    text = data.decode(encoding)
    if not text.strip():
        raise ValueError("Simulator LOG is empty")
    return text


def _log_warnings(text):
    import re
    # LTspice 26 emits this Level-1 advisory without a 'Warning:' prefix.
    return tuple(line.strip() for line in text.splitlines()
                 if re.search(r"\bwarning\b|Length shorter than recommended", line, re.I))


class _LTspiceRunner:
    """Private real backend, bound by the high-level API to verified bytes.

    Passing a Path to SimRunner copies it rather than editor-reserializing it.
    A per-run LTspice subclass checks that second copy before process launch;
    it also keeps create_from from modifying the v0.1 global simulator class.
    The library subprocess.run timeout terminates only its owned subprocess.
    No broad kill_all_spice/cleanup call is used.
    """
    def __init__(self, artifact, timeout):
        import math
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self.artifact, self.timeout = artifact, timeout
        self.executable, self.version, self.warnings = None, None, ()

    def run(self, netlist_path, output_folder):
        import hashlib
        import re
        from runtime_paths import locate_ltspice, MISSING_LTSPICE
        expected = self.artifact.netlist_bytes
        digest = self.artifact.provenance.execution_netlist_sha256
        def check(path):
            if (path.suffix.lower() != ".cir" or path.read_bytes() != expected
                    or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
                raise ValueError("Execution working-copy digest mismatch")
        check(netlist_path)
        self.executable = locate_ltspice()
        if self.executable is None:
            return RunnerResult(False, None, None, None, MISSING_LTSPICE)
        from PyLTSpice import SimRunner, LTspice
        artifact_root = output_folder.resolve()
        class VerifiedLTspice(LTspice):
            @classmethod
            def run(cls, netlist_file, *args, **kwargs):
                path = Path(netlist_file)
                _safe_path(artifact_root, path)
                check(path)
                return super().run(path, *args, **kwargs)
        simulator = VerifiedLTspice.create_from(self.executable)
        runner = SimRunner(simulator=simulator, parallel_sims=1, timeout=self.timeout,
                           output_folder=str(output_folder), verbose=False)
        # M2E supplies a new output directory. Do not consume pre-existing output.
        if any(output_folder.iterdir()):
            raise ValueError("Real runner requires a fresh empty output folder")
        raw, log = runner.run_now(netlist_path, run_filename="execution.cir", timeout=self.timeout, exe_log=True)
        task = runner.completed_tasks[-1]
        if task.is_alive():
            return RunnerResult(False, None, None, None, "Simulator task did not complete within its timeout")
        copy = output_folder / "execution.cir"
        check(copy)
        if runner.okSim != 1 or task.retcode != 0:
            return RunnerResult(False, task.retcode, raw, log, task.exception_text or f"LTspice exit code: {task.retcode}")
        for label, path in (("RAW", raw), ("LOG", log)):
            if path is None:
                raise ValueError(f"LTspice did not return {label}")
            _safe_path(output_folder, Path(path))
            if Path(path).resolve() != copy.with_suffix("." + label.lower()).resolve():
                raise ValueError(f"Unexpected {label} output location")
            if not Path(path).is_file() or Path(path).stat().st_size == 0:
                raise ValueError(f"LTspice did not generate nonempty {label}")
        text = _read_log(Path(log))
        match = re.search(r"(?im)^LTspice[^\r\n]*", text)
        self.version = match.group(0) if match else None
        self.warnings = _log_warnings(text)
        if re.search(r"(?im)^\s*(fatal error|error on line|unknown subcircuit|can't find|singular matrix|.*failed to converge)", text):
            return RunnerResult(False, task.retcode, Path(raw), Path(log), "Simulator LOG reports an error; inspect retained evidence")
        return RunnerResult(True, task.retcode, Path(raw), Path(log))


def run_ltspice_netlist(document, export_result, circuit_approval, representation_approval, request,
                        execution_approval, *, model_context, workspace_root=None, timeout=60):
    """Real M2 entry point: complete approval chain, never arbitrary raw paths.

    Production never creates approvals. RAW/analysis failure is FAILED even if
    the underlying process/file evidence was successful; both remain inspectable.
    Importing this module does not discover or start LTspice.
    """
    composed = compose_execution_netlist(document, export_result, circuit_approval, representation_approval,
        request, execution_approval, model_context=model_context)
    if composed.artifact is None:
        run = NetlistRunResult(RunStatus.BLOCKED, None, None, None, None, None, composed.issues)
        return NetlistSimulationResult(run, None, (), (), None, None)
    try:
        backend = _LTspiceRunner(composed.artifact, timeout)
    except (TypeError, ValueError) as error:
        run = NetlistRunResult(RunStatus.BLOCKED, None, None, None, None, None,
                              (ExecutionIssue("RUNNER_CONFIGURATION_INVALID", "timeout", str(error)),))
        return NetlistSimulationResult(run, None, (), (), None, None)
    if workspace_root is None:
        from runtime_paths import simulation_data_root
        workspace_root = simulation_data_root()
    run = run_generated_netlist(document, export_result, circuit_approval, representation_approval, request,
        execution_approval, model_context=model_context, workspace_root=workspace_root, runner=backend)
    if run.status is not RunStatus.SUCCESS:
        return NetlistSimulationResult(run, None, (), backend.warnings, backend.executable, backend.version)
    try:
        from netlist_result_analysis import read_netlist_analysis
        analysis = read_netlist_analysis(run.raw_file, run.artifact, request)
        return NetlistSimulationResult(run, analysis, (), backend.warnings, backend.executable, backend.version)
    except Exception as error:
        available = getattr(error, "available", None)
        detail = str(error) + (f"; available traces: {available}" if available is not None else "")
        return NetlistSimulationResult(run, None, (detail,), backend.warnings, backend.executable, backend.version)
