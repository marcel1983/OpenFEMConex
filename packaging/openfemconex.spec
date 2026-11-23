# -*- mode: python ; coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# PyInstaller spec, one-folder build:  pyinstaller packaging/openfemconex.spec
#
# A CalculiX executable is bundled when one is found: $OPENFEMCONEX_CCX or ccx on PATH.
import os
import shutil
import sys
from pathlib import Path

import gmsh
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
libname = {"win32": "gmsh-4.15.dll", "darwin": "libgmsh.4.15.dylib"}.get(sys.platform,
                                                                        "libgmsh.so.4.15")
gmsh_dir = Path(gmsh.__file__).resolve().parent
gmsh_lib = next(p for p in (gmsh_dir / libname, gmsh_dir / "lib" / libname,
                            gmsh_dir.parent / libname, gmsh_dir.parent / "lib" / libname,
                            gmsh_dir.parent.parent / libname,
                            gmsh_dir.parent.parent / "lib" / libname,
                            gmsh_dir.parent.parent / "bin" / libname,
                            gmsh_dir.parent.parent / "Lib" / libname) if p.exists())
binaries = [(str(gmsh_lib), ".")]
ccx = os.environ.get("OPENFEMCONEX_CCX") or shutil.which("ccx")
if ccx:
    binaries.append((ccx, "ccx"))

datas = (collect_data_files("openconex") + collect_data_files("pyvista")
         + collect_data_files("latex2mathml") + collect_data_files("pint")
         + collect_data_files("docx"))
hidden = collect_submodules("openconex") + ["vtkmodules.all", "pyvistaqt"]

a = Analysis(
    [str(root / "packaging" / "launch.py")],
    pathex=[str(root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib.tests", "IPython", "PySide6.QtWebEngineCore",
              "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="openfemconex", console=False,
          upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="openfemconex", upx=False)
if sys.platform == "darwin":
    app = BUNDLE(coll, name="OpenFEMConex.app", bundle_identifier="org.openfemconex.app",
                 info_plist={"NSHighResolutionCapable": True})
