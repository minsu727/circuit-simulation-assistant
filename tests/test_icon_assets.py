"""Branding source integrity and malformed-icon rejection without a build."""
from pathlib import Path
import struct
import unittest

from verify_icons import ico_images

PROJECT = Path(__file__).resolve().parents[1]


class IconAssetTests(unittest.TestCase):
    def test_official_ico_has_windows_sizes_and_decodable_images(self):
        from PIL import Image
        path = PROJECT / 'assets/app_icon.ico'
        entries = ico_images(path.read_bytes())
        self.assertTrue({(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)} <= {s for s, _ in entries})
        with Image.open(path) as image:
            for size, _ in entries:
                frame = image.ico.getimage(size)
                frame.load()
                self.assertEqual(frame.size, size)

    def test_png_source_is_valid_square_image(self):
        from PIL import Image
        with Image.open(PROJECT / 'assets/app_icon.png') as image:
            image.load()
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.width, image.height)
            self.assertGreaterEqual(image.width, 256)

    def test_truncated_or_out_of_bounds_icon_is_rejected(self):
        valid = (PROJECT / 'assets/app_icon.ico').read_bytes()
        bad_offset = bytearray(valid)
        struct.pack_into('<I', bad_offset, 18, len(valid) + 1)
        for data in (b'', valid[:5], valid[:21], valid[:-1], bytes(bad_offset)):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                ico_images(data)


if __name__ == '__main__':
    unittest.main()
