"""Offline extraction seam. M3C enables static replay only, never remote inference."""
from dataclasses import dataclass, field
from math import isfinite
from time import monotonic
from typing import Protocol
import re

from .intake import ImageArtifact, ImageLimits, validate_artifact
from .models import ObservationSet, ProviderInfo, Diagnostic, diagnostic
from .observations import ObservationLimits, parse_observations, validate_provider_info


STATIC_PROVIDER = ProviderInfo("static-replay","1",None,None,"m3-static-1","m3-images-1",None,"replay")


class VisionObservationProvider(Protocol):
    info: ProviderInfo

    def extract(self, image: ImageArtifact, *, timeout_s: float) -> str | bytes:
        """Return untrusted JSON or raise TimeoutError/ProviderUnavailable.

        The caller passes a cooperative deadline budget, not permission to upload.
        Future live/local implementations require separately reviewed policies.
        """
        ...


class ProviderUnavailable(Exception):
    pass


@dataclass(frozen=True, slots=True)
class StaticReplayProvider:
    payload: str | bytes = field(repr=False)
    info: ProviderInfo = STATIC_PROVIDER

    def extract(self, image, *, timeout_s):
        # No path resolution, image inspection, golden lookup or prediction.
        return self.payload


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    status: str
    observation_set: ObservationSet | None
    diagnostics: tuple[Diagnostic, ...]


def _fail(code,field="provider"):
    return ExtractionResult("FAILED",None,(diagnostic(code,field),))


def extract_observations(image, provider: VisionObservationProvider, *, timeout_s=60.0,
                         extraction_key="replay", limits=ObservationLimits(), image_limits=ImageLimits()):
    """One offline attempt, shape validation, no automatic retry/approval.

    Timeouts are cooperative: TimeoutError or late return fails; no thread/process
    can safely preempt arbitrary Python code. Static replay does not block.
    """
    if type(timeout_s) not in (int,float) or not isfinite(timeout_s) or not 0<timeout_s<=60:
        return _fail("PROVIDER_OPTIONS_INVALID","timeout_s")
    if type(extraction_key) is not str or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}",extraction_key):
        return _fail("PROVIDER_OPTIONS_INVALID","extraction_key")
    if not isinstance(limits,ObservationLimits):
        return _fail("OBS_LIMITS_INVALID","limits")
    issue = validate_artifact(image,image_limits)
    if issue: return ExtractionResult("FAILED",None,(issue,))
    try:
        info = provider.info
        issue = validate_provider_info(info)
        if issue: return ExtractionResult("FAILED",None,(issue,))
        if info.mode=="remote": return _fail("PROVIDER_REMOTE_DISABLED")
        if info.mode!="replay": return _fail("PROVIDER_UNAVAILABLE")
        start = monotonic()
        payload = provider.extract(image,timeout_s=float(timeout_s))
        if monotonic()-start > timeout_s: return _fail("PROVIDER_TIMEOUT")
    except TimeoutError:
        return _fail("PROVIDER_TIMEOUT")
    except ProviderUnavailable:
        return _fail("PROVIDER_UNAVAILABLE")
    except Exception:
        # Do not expose exception text: it may contain image data, paths or keys.
        return _fail("PROVIDER_FAILED")
    parsed = parse_observations(payload,image,provider=info,extraction_key=extraction_key,
                                limits=limits,image_limits=image_limits)
    if parsed.observation_set is None:
        return ExtractionResult("FAILED",None,parsed.diagnostics)
    status = "INCOMPLETE" if parsed.observation_set.coverage=="partial" else "SUCCESS"
    issues = (diagnostic("OBS_INCOMPLETE","coverage"),) if status=="INCOMPLETE" else ()
    return ExtractionResult(status,parsed.observation_set,issues)
