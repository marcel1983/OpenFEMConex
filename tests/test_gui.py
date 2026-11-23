# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Interface tests without OpenGL: the 3D widget is replaced by a placeholder."""

import os
import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["OPENFEMCONEX_NO_3D"] = "1"

from openfemconex.gui.main import MainWindow, plain_math  # noqa: E402

EXAMPLE = Path(__file__).parents[1] / "examples" / "dg1_2ed_ej_4_7.ocnx"


@pytest.fixture
def window(qtbot, monkeypatch):
    w = MainWindow()
    qtbot.addWidget(w)
    monkeypatch.setattr(w, "_confirm_discard", lambda: True)
    return w


def test_new_project_is_valid_and_previews(window):
    st = window.state
    assert st.valid, st.error
    window._refresh_view()
    assert st.mesh is not None
    assert "hexaedros" in window.viewer.description
    assert window.loads.combos.rowCount() >= 2
    assert window.solve_button.isEnabled()


def test_editing_a_field_revalidates_and_marks_dirty(window):
    st = window.state
    form = window.forms["Placa"]
    edit = form.widgets["tp"]
    edit.setText("60 mm")
    edit.editingFinished.emit()
    assert st.dirty and st.valid
    assert st.model.tp == pytest.approx(60.0)
    assert window.windowTitle().startswith("sin título *")
    edit.setText("sesenta")
    edit.editingFinished.emit()
    assert not st.valid
    assert "no válidos" in window.status_label.text()
    assert not window.solve_button.isEnabled()


def test_anchor_outside_plate_is_reported(window):
    window.state.set("base_plate", "f", "400 mm")
    assert not window.state.valid
    assert "washer" in window.state.error


def test_open_save_roundtrip(window, tmp_path):
    window.open_project(str(EXAMPLE))
    st = window.state
    assert st.valid and st.get("base_plate", "column") == "W12X96"
    assert window.forms["Columna"].widgets["column"].currentText() == "W12X96"
    assert window.loads.cases.rowCount() == 2
    target = tmp_path / "copia.ocnx"
    st.set("base_plate", "tp", "2.5 in")
    st.save(target)
    assert not st.dirty
    window.open_project(str(target))
    assert window.state.get("base_plate", "tp") == "2.5 in"
    assert window.state.output_dir() == tmp_path / "copia_fem"


def test_load_cases_drive_the_combinations(window):
    window.loads._add_case()
    assert len(window.state.data["cases"]) == 3
    window.loads.asd.setChecked(True)
    methods = {window.loads.combos.item(r, 1).text()
               for r in range(window.loads.combos.rowCount())}
    assert methods == {"LRFD", "ASD"}
    first = window.loads.combos.item(0, 0)
    first.setCheckState(first.checkState().Unchecked)
    assert first.text() not in window.loads.selected()


def test_ribbon_switches_the_work_area(window):
    window.ribbon.select("Cargas")
    assert window.central.currentWidget() is window.loads
    window.ribbon.select("Análisis")
    assert window.central.currentWidget() is window.viewer
    assert window.properties.currentWidget() is window.analysis_panel
    window.ribbon.select("Verificación")
    assert window.bottom.currentWidget() is window.checks


def test_plain_math():
    assert plain_math(r"\phi N_{cbg}") == "φ N_cbg"
    assert plain_math(r"\frac{A_{Nc}}{A_{Nco}}\psi_{ec,N}") == "(A_Nc)/(A_Nco)ψ_ec,N"


@pytest.mark.ccx
@pytest.mark.skipif(shutil.which("ccx") is None, reason="CalculiX no está instalado")
def test_solve_check_and_report(window, qtbot, tmp_path):
    shutil.copy(EXAMPLE, tmp_path / "caso.ocnx")
    window.open_project(str(tmp_path / "caso.ocnx"))
    window.state.set_setting("size", 20.0)
    window.state.set_setting("edition", "dg1-2ed")
    for r in range(window.loads.combos.rowCount()):
        item = window.loads.combos.item(r, 0)
        if item.text() != "LRFD-2":
            item.setCheckState(item.checkState().Unchecked)
    window.solve()
    assert window.worker is not None
    qtbot.waitUntil(lambda: window.worker is None, timeout=600_000)
    report = window.state.reports["LRFD-2"]
    assert report.results.converged
    assert window.checks.rowCount() == len(report.fem_checks) >= 6
    assert "Gobierna" in window.status_label.text()
    window.show_checks()
    assert "Referencia" in window.detail.toPlainText()
    html = window.generate_report()
    assert html.exists() and "ACI 318-08" in html.read_text(encoding="utf-8")
    pdf = window.export_pdf(str(tmp_path / "r.pdf"))
    assert pdf.exists() and pdf.stat().st_size > 5000
    # editing after solving flags the results as outdated
    window.state.set("base_plate", "tp", "2.5 in")
    assert window.state.stale
    assert "desactualizados" in window.status_label.text()
