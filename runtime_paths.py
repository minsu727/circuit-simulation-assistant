"""Portable resources, writable data, and external LTspice discovery only."""
import os
from pathlib import Path
import shutil
import sys


MISSING_LTSPICE = ('LTspice was not found on this computer. Install LTspice separately '
                   'or set LTSPICE_EXECUTABLE to its full executable path, then restart.')


class LTspiceNotFoundError(RuntimeError):
    pass


def is_packaged():
    return bool(getattr(sys, 'frozen', False))


def resource_root():
    return Path(sys._MEIPASS) if is_packaged() else Path(__file__).resolve().parent


def locate_app_resource(name='app.py'):
    root = resource_root().resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FileNotFoundError('Required application resource is unavailable.')
    return path


def user_data_root():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    return base / 'CircuitSimulationAssistant'


def simulation_data_root():
    return user_data_root() if is_packaged() else Path(__file__).resolve().parent


def locate_ltspice():
    # An explicit invalid setting must not silently select a different binary.
    configured = os.environ.get('LTSPICE_EXECUTABLE', '').strip()
    if configured:
        path = Path(configured).expanduser()
        return path.resolve() if path.is_absolute() and path.suffix.lower() == '.exe' and path.is_file() else None
    local = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    candidates = [local / 'Programs' / 'ADI' / 'LTspice' / 'LTspice.exe']
    for variable in ('ProgramFiles', 'ProgramFiles(x86)'):
        base = os.environ.get(variable)
        if base:
            candidates.extend([Path(base) / 'ADI/LTspice/LTspice.exe',
                               Path(base) / 'LTC/LTspiceXVII/XVIIx64.exe',
                               Path(base) / 'LTC/LTspiceIV/scad3.exe'])
    for name in ('LTspice.exe', 'XVIIx64.exe', 'scad3.exe'):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    return next((path.resolve() for path in candidates if path.is_file()), None)


def configure_ltspice():
    path = locate_ltspice()
    if path is None:
        raise LTspiceNotFoundError(MISSING_LTSPICE)
    from PyLTSpice import LTspice
    # Path avoids interpreting spaces or punctuation as command-line arguments.
    return LTspice.create_from(path)
