"""Hand-composed synthetic observation records, never M3B electrical truth."""
from pathlib import Path
from io import BytesIO
import json
from PIL import Image
import circuit_image as ci
from circuit_image.serialization import provider_to_dict

ROOT = Path(__file__).resolve().parents[1]
M3B = ROOT / "tests/fixtures/schematic_images"
REPLAYS = ROOT / "tests/fixtures/image_observations"


def fixture_image(name="divider"):
    return ci.ingest_image((M3B / "cases" / name / "schematic.png").read_bytes()).artifact


def image_bytes(fmt="PNG", size=(96,64), orientation=None):
    image = Image.new("RGB",size,"white")
    image.putpixel((2,3),(255,0,0))
    out = BytesIO()
    options = {}
    if orientation is not None:
        exif = Image.Exif(); exif[274] = orientation
        options["exif"] = exif
    image.save(out,format=fmt,**options)
    return out.getvalue()


def geometry(bbox=None, points=(), pose="unknown"):
    return {"bbox":bbox,"points":[list(p) for p in points],"orientation":pose}


def row(identity="symbol", kind="symbol", data=None, g=None, state="provisional", reasons=(), related=(), alternatives=()):
    if data is None:
        data = {"classification":"supported","component_type":"resistor","observed_name":"resistor","reference_text":"R1"}
    if g is None and kind=="symbol": g = geometry([10,10,40,20])
    return {"id":identity,"kind":kind,"source_sha256":"BOUND_BY_TEST_IMAGE",
            "geometry":g,"data":data,"confidence":{"score":None,"basis":"synthetic","calibrated":False},
            "uncertainty":{"state":state,"reasons":list(reasons),"related_refs":list(related),"alternatives":list(alternatives)}}


def envelope(artifact, rows=None, coverage="reported_complete", frame="original_pixels", provider=ci.STATIC_PROVIDER):
    identity = artifact.identity
    rows = [row()] if rows is None else rows
    # Bind image hashes only; do not inspect pixels or read any expected.json.
    rows = json.loads(json.dumps(rows))
    for r in rows: r["source_sha256"] = identity.source_sha256
    return {"version":ci.OBSERVATION_VERSION,"image":{"source_identity_sha256":identity.identity_sha256,
            "source_sha256":identity.source_sha256,"normalized_sha256":identity.normalized_sha256,
            "transform_sha256":identity.transform.sha256},"coordinate_frame":frame,
            "provider":provider_to_dict(provider),"coverage":coverage,"observations":rows}


def encode(data):
    return json.dumps(data,ensure_ascii=False,allow_nan=False)
