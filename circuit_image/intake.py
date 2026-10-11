"""Bounded in-memory PNG/JPEG intake. No paths, disk writes or network."""
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import json
import warnings

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError
from .models import Diagnostic, INTAKE_VERSION, diagnostic


def canonical_json(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_digest(data):
    return sha256(canonical_json(data).encode("utf8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ImageLimits:
    max_bytes: int = 8 * 1024 * 1024
    min_side: int = 64
    max_side: int = 4096
    max_pixels: int = 8_000_000

    def __post_init__(self):
        for value in (self.max_bytes, self.min_side, self.max_side, self.max_pixels):
            if type(value) is not int or value <= 0:
                raise ValueError("Image limits must be positive integers.")
        if self.min_side > self.max_side:
            raise ValueError("Minimum side exceeds maximum side.")


@dataclass(frozen=True, slots=True)
class ImageTransform:
    exif_orientation: int
    forward: tuple[int, int, int, int, int, int]
    inverse: tuple[int, int, int, int, int, int]
    sha256: str

    def to_display(self, x, y):
        a,b,c,d,e,f = self.forward
        return a*x+b*y+c, d*x+e*y+f

    def to_original(self, x, y):
        a,b,c,d,e,f = self.inverse
        return a*x+b*y+c, d*x+e*y+f


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    contract_version: str
    source_sha256: str
    byte_length: int
    format: str
    width: int
    height: int
    display_width: int
    display_height: int
    normalized_sha256: str
    transform: ImageTransform
    identity_sha256: str


@dataclass(frozen=True, slots=True)
class ImageArtifact:
    identity: SourceIdentity
    original_bytes: bytes = field(repr=False)
    normalized_png: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class IntakeResult:
    artifact: ImageArtifact | None
    diagnostics: tuple[Diagnostic, ...]


def _fail(code, field="image"):
    return IntakeResult(None, (diagnostic(code, field),))


def _transform(orientation, w, h):
    # Continuous pixel-edge coordinates. Centers are (column+.5,row+.5).
    forward = {1:(1,0,0,0,1,0), 2:(-1,0,w,0,1,0), 3:(-1,0,w,0,-1,h),
               4:(1,0,0,0,-1,h), 5:(0,1,0,1,0,0), 6:(0,-1,h,1,0,0),
               7:(0,-1,h,-1,0,w), 8:(0,1,0,-1,0,w)}[orientation]
    a,b,c,d,e,f = forward
    det = a*e-b*d
    inverse = (e//det,-b//det,(b*f-e*c)//det,-d//det,a//det,(d*c-a*f)//det)
    digest = content_digest({"version":INTAKE_VERSION,"orientation":orientation,
                             "original_size":[w,h],"forward":forward,"inverse":inverse})
    return ImageTransform(orientation, forward, inverse, digest)


def ingest_image(data: bytes, *, limits: ImageLimits = ImageLimits()) -> IntakeResult:
    """Decode only bounded actual PNG/JPEG bytes; return immutable source + PNG.

    Normalized PNG is oriented RGBA and has no source metadata. No resize/deskew.
    Pillow's permissive truncated-image mode is refused, never globally changed.
    """
    if not isinstance(limits, ImageLimits):
        return _fail("IMAGE_LIMITS_INVALID", "limits")
    if type(data) is not bytes:
        return _fail("IMAGE_INPUT_INVALID")
    if not data:
        return _fail("IMAGE_EMPTY")
    if len(data) > limits.max_bytes:
        return _fail("IMAGE_BYTES_EXCEEDED")
    png = data.startswith(b"\x89PNG\r\n\x1a\n")
    jpeg = data.startswith(b"\xff\xd8\xff")
    if not png and not jpeg:
        unsupported = data.startswith((b"GIF8", b"BM", b"II*", b"MM\x00", b"RIFF", b"<", b"%PDF"))
        return _fail("IMAGE_FORMAT_UNSUPPORTED" if unsupported else "IMAGE_MALFORMED")
    if ImageFile.LOAD_TRUNCATED_IMAGES:
        return _fail("IMAGE_DECODER_POLICY_UNSAFE")
    if png and not data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82") or jpeg and not data.endswith(b"\xff\xd9"):
        return _fail("IMAGE_TRUNCATED")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with Image.open(BytesIO(data), formats=("PNG", "JPEG")) as original:
                fmt, (w,h) = original.format, original.size
                if fmt != ("PNG" if png else "JPEG"):
                    return _fail("IMAGE_FORMAT_MISMATCH")
                if not limits.min_side <= w <= limits.max_side or not limits.min_side <= h <= limits.max_side:
                    return _fail("IMAGE_DIMENSIONS_EXCEEDED")
                if w*h > limits.max_pixels:
                    return _fail("IMAGE_PIXELS_EXCEEDED")
                original.verify()
            with Image.open(BytesIO(data), formats=("PNG", "JPEG")) as decoded:
                if getattr(decoded, "n_frames", 1) != 1:
                    return _fail("IMAGE_ANIMATION_UNSUPPORTED")
                orientation = decoded.getexif().get(274, 1)
                if type(orientation) is not int or orientation not in range(1,9):
                    return _fail("IMAGE_ORIENTATION_INVALID")
                decoded.load()
                oriented = ImageOps.exif_transpose(decoded).convert("RGBA")
                dw,dh = oriented.size
                # Reconstruct from pixels so EXIF, comments and filenames cannot persist.
                with Image.frombytes("RGBA", oriented.size, oriented.tobytes()) as clean:
                    stream = BytesIO()
                    clean.save(stream, format="PNG", compress_level=6, optimize=False)
                    normalized = stream.getvalue()
        if ImageFile.LOAD_TRUNCATED_IMAGES:
            return _fail("IMAGE_DECODER_POLICY_UNSAFE")
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return _fail("IMAGE_DECOMPRESSION_UNSAFE")
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, TypeError, RuntimeError, Warning):
        return _fail("IMAGE_MALFORMED")
    transform = _transform(orientation,w,h)
    values = {"contract_version":INTAKE_VERSION,"source_sha256":sha256(data).hexdigest(),
              "byte_length":len(data),"format":fmt,"width":w,"height":h,
              "display_width":dw,"display_height":dh,"normalized_sha256":sha256(normalized).hexdigest(),
              "transform_sha256":transform.sha256}
    identity = SourceIdentity(INTAKE_VERSION,values["source_sha256"],len(data),fmt,w,h,dw,dh,
                              values["normalized_sha256"],transform,content_digest(values))
    return IntakeResult(ImageArtifact(identity,data,normalized), ())


def validate_artifact(artifact, limits=ImageLimits()):
    """Recheck caller-created/replaced artifacts at each observation/provider boundary."""
    if type(artifact) is not ImageArtifact:
        return diagnostic("IMAGE_ARTIFACT_INVALID", "image")
    result = ingest_image(artifact.original_bytes, limits=limits)
    if result.artifact is None:
        return result.diagnostics[0]
    if result.artifact != artifact:
        return diagnostic("IMAGE_IDENTITY_MISMATCH", "image")
    return None
