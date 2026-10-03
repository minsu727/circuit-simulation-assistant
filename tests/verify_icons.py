"""Opt-in PE icon verification; requires pefile from the Windows build environment.

Compare every ICO image with the first Windows RT_GROUP_ICON and its RT_ICON
payloads. Exact payload checks bypass Explorer's cached display. No binary edits.
Run: python tests/verify_icons.py EXE [EXE ...]
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

PROJECT = Path(__file__).resolve().parents[1]


def ico_images(data):
    """Read image sizes/payloads; reject malformed or truncated ICO containers."""
    if len(data) < 6:
        raise ValueError('Truncated ICO header')
    reserved, kind, count = struct.unpack_from('<HHH', data)
    if reserved != 0 or kind != 1 or count == 0 or len(data) < 6 + 16 * count:
        raise ValueError('Invalid ICO directory')
    images = []
    for index in range(count):
        w, h, colors, zero, planes, bits, length, offset = struct.unpack_from('<BBBBHHII', data, 6 + 16 * index)
        if zero or length == 0 or offset < 6 + 16 * count or offset + length > len(data):
            raise ValueError('Invalid ICO image bounds')
        images.append(((w or 256, h or 256), data[offset:offset + length]))
    return images


def verify_executable_icon(executable, icon=PROJECT / 'assets/app_icon.ico'):
    import pefile  # Build-only dependency; not imported by the application.
    expected = ico_images(Path(icon).read_bytes())
    with pefile.PE(str(executable)) as pe:
        types = {entry.id: entry.directory.entries for entry in pe.DIRECTORY_ENTRY_RESOURCE.entries}
        groups = types[14]  # RT_GROUP_ICON; first group is Windows icon index 0.
        images = {entry.id: entry.directory.entries for entry in types[3]}
        group = groups[0]
        variants = 0
        for language in group.directory.entries:
            item = language.data.struct
            data = pe.get_data(item.OffsetToData, item.Size)
            reserved, kind, count = struct.unpack_from('<HHH', data)
            assert (reserved, kind, count) == (0, 1, len(expected)), 'Default icon image count differs'
            for index, (size, payload) in enumerate(expected):
                w, h, colors, zero, planes, bits, length, resource_id = struct.unpack_from('<BBBBHHIH', data, 6 + 14 * index)
                assert (w or 256, h or 256) == size, 'Embedded icon size differs'
                assert length == len(payload), 'Embedded icon payload length differs'
                candidates = images[resource_id]
                for candidate in candidates:
                    resource = candidate.data.struct
                    actual = pe.get_data(resource.OffsetToData, resource.Size)
                    assert actual == payload, 'Embedded icon pixels/bytes differ from official ICO'
            variants += 1
    return {'default_icon_matches': True, 'image_sizes': [list(size) for size, _ in expected],
            'language_variants_checked': variants, 'ico_sha256': hashlib.sha256(Path(icon).read_bytes()).hexdigest()}


def verify_shell_icon(path, output):
    """Render through Windows Shell and compare with the official ICO rendering."""
    from PIL import Image
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    is_shortcut = Path(path).suffix.lower() == '.lnk'
    reference = output.parent / ('official-shortcut-shell.png' if is_shortcut else 'official-shell.png')
    for source, destination in ((PROJECT / 'assets/app_icon.ico', reference), (path, output)):
        options = ['-ShortcutReference'] if is_shortcut and destination == reference else []
        subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                        str(PROJECT / 'tests/verify_icon_shell.ps1'), '-Source', str(source),
                        '-Output', str(destination), *options], check=True, capture_output=True, timeout=30)
    with Image.open(reference) as expected, Image.open(output) as actual:
        assert actual.size == expected.size, 'Shell icon size differs'
        assert actual.convert('RGBA').tobytes() == expected.convert('RGBA').tobytes(), 'Shell icon differs; check resources and Windows cache separately'
        return {'shell_pixels_match': True, 'rendered_size': list(actual.size), 'shortcut_overlay_expected': is_shortcut}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executables', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps({p.name: verify_executable_icon(p) for p in args.executables}, indent=2))


if __name__ == '__main__':
    main()
