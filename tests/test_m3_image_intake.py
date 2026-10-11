"""In-memory intake/security/EXIF tests; no image recognition or new public raster."""
from dataclasses import replace
from io import BytesIO
import hashlib
import unittest
from unittest.mock import patch
from PIL import Image, ImageFile
import circuit_image as ci
from tests.m3c_helpers import image_bytes, M3B


class ImageIntakeTests(unittest.TestCase):
    def assert_code(self,data,code,**options):
        result = ci.ingest_image(data,**options)
        self.assertIsNone(result.artifact)
        self.assertEqual(result.diagnostics[0].code,code)

    def test_representative_m3b_pngs(self):
        for name in ("divider","rc","nmos","pmos","cross_open","cross_dot","cross_ambiguous","near_gap","unreadable_value","unsupported_bjt"):
            with self.subTest(name=name):
                source = (M3B/"cases"/name/"schematic.png").read_bytes()
                result = ci.ingest_image(source)
                self.assertEqual(result.diagnostics,())
                self.assertEqual(result.artifact.identity.format,"PNG")
                self.assertEqual(result.artifact.original_bytes,source)

    def test_valid_jpeg(self):
        result = ci.ingest_image(image_bytes("JPEG"))
        self.assertEqual(result.diagnostics,())
        self.assertEqual(result.artifact.identity.format,"JPEG")

    def test_identical_source_identity_and_normalization(self):
        data = image_bytes()
        a,b = ci.ingest_image(data).artifact,ci.ingest_image(data).artifact
        self.assertEqual(a,b)
        self.assertEqual(a.identity.source_sha256,hashlib.sha256(data).hexdigest())
        self.assertEqual(a.identity.byte_length,len(data))

    def test_normalization_has_no_metadata(self):
        result = ci.ingest_image(image_bytes(orientation=6)).artifact
        with Image.open(BytesIO(result.normalized_png)) as image:
            self.assertEqual(image.mode,"RGBA")
            self.assertEqual(image.info,{})
            self.assertEqual(dict(image.getexif()),{})
        self.assertNotIn("original_bytes",repr(result))

    def test_all_eight_exif_transforms_match_pixel_centers(self):
        expected = {1:(2,3),2:(93,3),3:(93,60),4:(2,60),5:(3,2),6:(60,2),7:(60,93),8:(3,93)}
        for orientation,(column,line) in expected.items():
            with self.subTest(orientation=orientation):
                artifact = ci.ingest_image(image_bytes(orientation=orientation)).artifact
                self.assertIsNotNone(artifact)
                x,y = artifact.identity.transform.to_display(2.5,3.5)
                self.assertEqual((x,y),(column+.5,line+.5))
                self.assertEqual(artifact.identity.transform.to_original(x,y),(2.5,3.5))
                with Image.open(BytesIO(artifact.normalized_png)) as normalized:
                    self.assertEqual(normalized.getpixel((column,line)),(255,0,0,255))
                    self.assertEqual(normalized.size,(64,96) if orientation>=5 else (96,64))

    def test_jpeg_orientation_dimensions(self):
        image = ci.ingest_image(image_bytes("JPEG",orientation=6)).artifact
        self.assertEqual((image.identity.width,image.identity.height),(96,64))
        self.assertEqual((image.identity.display_width,image.identity.display_height),(64,96))

    def test_invalid_exif_orientation(self):
        self.assert_code(image_bytes(orientation=9),"IMAGE_ORIENTATION_INVALID")

    def test_empty_bytes(self): self.assert_code(b"","IMAGE_EMPTY")

    def test_local_path_is_not_an_input(self):
        self.assert_code("not-an-image.png","IMAGE_INPUT_INVALID")

    def test_malformed_bytes(self): self.assert_code(b"garbage","IMAGE_MALFORMED")

    def test_svg_gif_and_pdf_unsupported(self):
        for data in (b'<svg></svg>',image_bytes("GIF"),b'%PDF-1.7'):
            self.assert_code(data,"IMAGE_FORMAT_UNSUPPORTED")

    def test_spoofed_png_signature(self):
        data = b"\x89PNG\r\n\x1a\n" + b"not-a-png" + b"\x00\x00\x00\x00IEND\xaeB`\x82"
        self.assert_code(data,"IMAGE_MALFORMED")

    def test_truncated_png_and_jpeg(self):
        for fmt in ("PNG","JPEG"):
            self.assert_code(image_bytes(fmt)[:-10],"IMAGE_TRUNCATED")

    def test_corrupt_png_crc(self):
        data = bytearray(image_bytes()); data[29] ^= 1
        self.assert_code(bytes(data),"IMAGE_MALFORMED")

    def test_byte_limit_precedes_decode(self):
        with patch("circuit_image.intake.Image.open",side_effect=AssertionError("decoder reached")):
            self.assert_code(image_bytes(),"IMAGE_BYTES_EXCEEDED",limits=ci.ImageLimits(max_bytes=10))

    def test_dimensions_and_pixels_are_bounded(self):
        self.assert_code(image_bytes(size=(63,64)),"IMAGE_DIMENSIONS_EXCEEDED")
        self.assert_code(image_bytes(),"IMAGE_PIXELS_EXCEEDED",limits=ci.ImageLimits(max_pixels=100))
        self.assert_code(image_bytes(),"IMAGE_DIMENSIONS_EXCEEDED",limits=ci.ImageLimits(max_side=64))

    def test_oversized_header_never_loads_pixels(self):
        data = image_bytes(size=(200,100))
        with patch("PIL.PngImagePlugin.PngImageFile.load",side_effect=AssertionError("pixels loaded")):
            self.assert_code(data,"IMAGE_PIXELS_EXCEEDED",limits=ci.ImageLimits(max_pixels=1000))

    def test_permissive_truncation_policy_is_refused_not_changed(self):
        with patch.object(ImageFile,"LOAD_TRUNCATED_IMAGES",True):
            self.assert_code(image_bytes(),"IMAGE_DECODER_POLICY_UNSAFE")
            self.assertTrue(ImageFile.LOAD_TRUNCATED_IMAGES)

    def test_animation_rejected(self):
        out = BytesIO()
        a,b = Image.new("RGB",(64,64),"white"),Image.new("RGB",(64,64),"black")
        a.save(out,format="PNG",save_all=True,append_images=[b],duration=100)
        self.assert_code(out.getvalue(),"IMAGE_ANIMATION_UNSUPPORTED")

    def test_invalid_limit_configuration(self):
        for kwargs in ({"max_pixels":True},{"max_bytes":0},{"min_side":100,"max_side":64}):
            with self.assertRaises(ValueError): ci.ImageLimits(**kwargs)

    def test_identity_is_frozen(self):
        from dataclasses import FrozenInstanceError
        artifact = ci.ingest_image(image_bytes()).artifact
        with self.assertRaises(FrozenInstanceError): artifact.identity.width = 1

    def test_source_metadata_changes_original_digest(self):
        a,b = ci.ingest_image(image_bytes()).artifact,ci.ingest_image(image_bytes(orientation=1)).artifact
        self.assertNotEqual(a.identity.source_sha256,b.identity.source_sha256)
        self.assertEqual(a.normalized_png,b.normalized_png)
