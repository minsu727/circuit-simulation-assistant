# Maintained onedir recipe. Run through scripts/build_windows.ps1.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH)
datas = [(str(root / 'app.py'), '.')]
datas += collect_data_files('streamlit')
datas += copy_metadata('streamlit')

# The first executable failed on Streamlit's AST-injected magic_funcs import.
# app.py is executed dynamically from data, so explicitly analyze its imports.
a = Analysis([str(root / 'launcher.py')], pathex=[str(root)], datas=datas,
             hiddenimports=['app', 'streamlit.runtime.scriptrunner.magic_funcs'],
             excludes=['openai', 'playwright', 'pytest', 'IPython'],
             hooksconfig={'matplotlib': {'backends': ['Agg']}}, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CircuitSimulationAssistant',
          debug=False, strip=False, upx=False, console=True,
          icon=str(root / 'assets' / 'app_icon.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CircuitSimulationAssistant')
