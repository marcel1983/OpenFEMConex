# SPDX-License-Identifier: AGPL-3.0-or-later
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
    assert window.column_panel.shape.currentText() == "W12X96"
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
    docx = window.export_docx(str(tmp_path / "r.docx"))
    assert docx.exists() and docx.stat().st_size > 5000
    # editing after solving flags the results as outdated
    window.state.set("base_plate", "tp", "2.5 in")
    assert window.state.stale
    assert "desactualizados" in window.status_label.text()


@pytest.fixture
def isolated_settings(monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings

    import openfemconex.gui.main as gui_main

    store = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(gui_main, "settings", lambda: store)
    return store


def test_dark_theme(window, isolated_settings):
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    window.set_dark(True)
    window_color = QApplication.instance().palette().color(QPalette.ColorRole.Window)
    assert window_color.lightness() < 80
    assert isolated_settings.value("dark", type=bool) is True
    window.set_dark(False)
    assert QApplication.instance().palette().color(QPalette.ColorRole.Window).lightness() > 150


def test_help_topics_in_both_languages(qtbot):
    from openfemconex.gui.help import HelpDialog, topics

    es, en = topics("es"), topics("en")
    assert len(es) == len(en) >= 4
    assert es[0][0] == "Inicio rápido" and en[0][0] == "Quick start"
    dialog = HelpDialog(None, 2)
    assert dialog.index.count() == len(es)
    assert "Verificaciones" in dialog.page.toPlainText()


def test_help_figures_load(qtbot):
    import re

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage, QTextDocument

    from openfemconex.gui.help import HelpDialog, topics

    for lang in ("es", "en"):
        text = dict(topics(lang))
        title = "Pernos pasantes en concreto" if lang == "es" else "Through-bolts in concrete"
        figures = re.findall(r"\]\((img/[^)]+)\)", text[title])
        assert len(figures) == 6
    dialog = HelpDialog(None, [t for t, _ in topics()].index("Pernos pasantes en concreto"))
    qtbot.addWidget(dialog)
    for path in figures:
        data = dialog.page.loadResource(QTextDocument.ResourceType.ImageResource.value,
                                        QUrl(path.replace("/en/", "/es/")))
        assert QImage.fromData(data).width() > 600, path


def test_english_interface(qtbot, monkeypatch):
    from openfemconex.i18n import EN, set_language, tr

    set_language("en")
    try:
        w = MainWindow()
        qtbot.addWidget(w)
        monkeypatch.setattr(w, "_confirm_discard", lambda: True)
        assert [w.ribbon.tabs.tabText(i) for i in range(w.ribbon.tabs.count())] == [
            "Project", "Geometry", "Loads", "Analysis", "Checks", "Report", "Help"]
        assert "Ready" in w.status_label.text()
        assert tr("Datos no válidos: {error}", error="x") == "Invalid data: x"
        w.ribbon.select("Geometría")  # internal names stay in Spanish
        assert w.central.currentWidget() is w.viewer
    finally:
        set_language("es")
    # every English text has its fields in common with the Spanish one
    import string

    def fields(text):
        return {f for _, f, _, _ in string.Formatter().parse(text) if f}

    assert all(fields(k) == fields(v) for k, v in EN.items())


def test_shear_lug_form_and_anchor_force_table(window):
    st = window.state
    assert st.model.lug is None
    form = window.lug_form
    form.enabled.setChecked(True)
    assert st.valid, st.error
    assert st.model.lug is not None and st.model.lug.direction == "strong"
    assert st.data["base_plate"]["shear_lug"]["width"] == "200 mm"
    form.widgets["direction"].setCurrentIndex(form.widgets["direction"].findData("both"))
    form._commit()
    assert st.model.lug.direction == "both"
    form.enabled.setChecked(False)
    assert "shear_lug" not in st.data["base_plate"] and st.model.lug is None
    headers = [window.anchor_forces.horizontalHeaderItem(i).text()
               for i in range(window.anchor_forces.columnCount())]
    assert headers[4:8] == ["Axial", "Cortante Vx", "Cortante Vy", "Cortante total"]


def test_cruciform_column_from_the_panel(window):
    panel = window.column_panel
    st = window.state
    panel.cross.setCurrentText("W10X49")
    panel.kind.setCurrentIndex(1)
    panel._commit_kind()
    assert st.ext("column") == {"type": "cruciform", "cross": "W10X49"}
    assert st.valid, st.error
    assert st.model.section.kind.value == "CRUCIFORM"
    assert "W10X49" in panel.preview.section.name
    panel.kind.setCurrentIndex(0)
    panel._commit_kind()
    assert st.ext("column") is None


def test_built_up_section_becomes_the_column(window):
    from openfemconex.gui.library import SectionsDialog

    dialog = SectionsDialog(window.state, window)
    dialog._new()
    dialog.edits["d"].setText("300 mm")
    dialog.edits["d"].editingFinished.emit()
    assert "A" in dialog.props.text()
    dialog._use()
    st = window.state
    assert isinstance(st.get("base_plate", "column"), dict)
    assert st.valid, st.error
    assert st.model.section.d == pytest.approx(300.0)
    assert window.column_panel.shape.currentText() == st.column_label()


def test_material_editor_law_and_rename(window):
    from openfemconex.gui.library import MaterialsDialog

    st = window.state
    dialog = MaterialsDialog(st, window)
    dialog._new_steel()
    dialog.steel_edits["Fy"].setText("300 MPa")
    dialog.steel_edits["Fy"].editingFinished.emit()
    dialog.law.setCurrentIndex(dialog.law.findData("trilineal"))
    dialog._steel_edited()
    assert len(dialog.curve.points) == 5
    dialog.steel_edits["name"].setText("Mi acero")
    dialog.steel_edits["name"].editingFinished.emit()
    dialog._accept()
    assert st.data["materials"][0]["name"] == "Mi acero"
    assert st.data["openfemconex"]["materials"]["Mi acero"]["law"] == "trilineal"
    st.set("base_plate", "plate_grade", "Mi acero")
    assert st.valid, st.error
    assert st.model.plate_steel.plastic_curve()[1] == (300.0, 0.015)
    assert "Mi acero" in [window.forms["Placa"].widgets["plate_grade"].itemText(i)
                          for i in range(window.forms["Placa"].widgets["plate_grade"].count())]


STA = """
 SUMMARY OF JOB INFORMATION
  STEP      INC     ATT  ITRS     TOT TIME     STEP TIME      INC TIME
     1          1     1    13  0.100000E+01  0.100000E+01  0.100000E+01
     2          1     1     9  0.105000E+01  0.500000E-01  0.500000E-01
     2          2    1U    16  0.110000E+01  0.100000E+00  0.500000E-01
     2          2     2     4  0.112500E+01  0.125000E+00  0.250000E-01
"""


def test_progress_window_follows_calculix(window, tmp_path):
    from openfemconex.gui.progress import fraction, read_increments

    sta = tmp_path / "LRFD-1.sta"
    sta.write_text(STA)
    (tmp_path / "LRFD-1.cvg").write_text(
        "     2     3     1     2    7000  0.3015E+00  0.2091E-01  0.0000E+00  0.0000E+00\n")
    incs = read_increments(sta)
    assert len(incs) == 4 and incs[2].cutback
    assert fraction(incs) == pytest.approx(0.1 + 0.9 * 0.125)
    dialog = window.solve_progress
    dialog.start(2, 1000, 1500, 4)
    dialog.combo_started("LRFD-1", sta)
    dialog.stage("CalculiX resolviendo")
    dialog.poll()
    text = dialog.log.toPlainText()
    assert "no convergió" in text and "12.5 %" in text
    assert "residuo" in dialog.detail_label.text()
    assert dialog.overall() == pytest.approx(0.2125 / 2, abs=1e-3)
    cancelled = []
    dialog.cancel_requested.connect(lambda: cancelled.append(True))
    dialog.cancel_button.click()
    assert cancelled
    dialog.finished(cancelled=True)
    assert dialog.cancel_button.text() in ("Cerrar", "Close")


def test_fast_mesh_checkbox(window):
    st = window.state
    window.analysis_panel.fast.setChecked(True)
    assert st.settings.fast
    window._ensure_mesh()
    assert st.mesh.settings.fast
    assert not window.analysis_panel.layers.isEnabled()


def test_view_controls_and_dimensions(window):
    viewer = window.viewer
    assert {"zoom_in", "zoom_out", "fit", "iso", "top"} <= set(viewer.buttons)
    for b in viewer.buttons.values():
        b.click()  # without OpenGL the camera calls are no-ops
    window.state.set_ext("anchors", [["-220 mm", "-150 mm"], ["220 mm", "-150 mm"],
                                     ["220 mm", "150 mm"], ["-220 mm", "150 mm"]])
    viewer.dims.setChecked(False)
    viewer.numbers.setChecked(False)
    assert window.state.valid
    assert window.state.study().length_text(560.0) == "560 mm"


def test_edit_combinations(window):
    from openfemconex.gui.combos import CombinationsDialog, combination_text

    assert combination_text({"D": 1.2, "L": 1.6}) == "1.2D + 1.6L"
    assert combination_text({"D": 0.9, "W": -1.0}) == "0.9D − W"
    st = window.state
    dialog = CombinationsDialog(st, window)
    dialog._copy_code()
    assert not dialog.include.isChecked()
    assert [c["name"] for c in dialog.custom] == ["LRFD-1", "LRFD-2"]
    dialog.table.item(1, 3).setText("1.0")  # factor of L in LRFD-2
    dialog._add()
    dialog._accept()
    combos = {c.name: c for c in st.project.load_combinations()}
    assert set(combos) == {"LRFD-1", "LRFD-2", "Comb"}
    assert combos["LRFD-2"].factors == {"D": 1.2, "L": 1.0}
    assert st.data["combinations"]["include_code"] is False
    texts = [window.loads.combos.item(r, 2).text() for r in range(window.loads.combos.rowCount())]
    assert "1.2D + L" in texts


def test_title_block_heads_the_report(window):
    st = window.state
    form = window.forms["Ficha"]
    for key, value in (("engineer", "Ing. Prueba"), ("revision", "B"),
                       ("connection", "PB-1, eje A-3")):
        form.widgets[key].setText(value)
        form.widgets[key].editingFinished.emit()
    assert st.valid, st.error
    study = st.study()
    rows = dict(study.ficha())
    assert rows["Ingeniero"] == "Ing. Prueba" and rows["Revisión"] == "B"
    assert rows["Conexión"] == "PB-1, eje A-3"
    assert "PB-1" in study.report_title()


def test_title_bar_shows_the_version(window):
    from openfemconex import __version__

    assert window.windowTitle().endswith(f"OpenFEMConex {__version__}")


def test_units_follow_the_project_everywhere(window):
    st = window.state
    st.set_ext("hairpins", {"count": 1, "diameter": "16 mm", "offset": "75 mm",
                            "leg_length": "600 mm"})
    assert st.valid, st.error
    model_tp = st.model.tp
    st.set_units("US")
    assert st.get("base_plate", "tp") == "1.9685 in"
    assert st.ext("hairpins")["leg_length"] == "23.622 in"
    assert st.data["cases"][0]["P"].endswith(" kip")
    assert st.valid, st.error
    assert st.model.tp == pytest.approx(model_tp, rel=1e-4)
    # a bare number typed in a form is taken in the project units
    edit = window.forms["Placa"].widgets["tp"]
    edit.setText("2")
    edit.editingFinished.emit()
    assert st.get("base_plate", "tp") == "2 in"
    assert window.analysis_panel.size.suffix() == " in"
    # lengths of the report in inches, also the plate size (no metres)
    assert st.study().length_text(25.4) == "1 in"
    st.set_units("SI_kN_m")
    assert st.get("base_plate", "tp") == "50.8 mm"
    from openfemconex.units import display_units

    assert display_units(st.project.info).length == "mm"


def test_anchor_rows_facing_the_weak_axis(window):
    st = window.state
    xs = sorted({round(a.x) for a in st.model.anchors})
    box = window.forms["Anclajes"].widgets["rows_weak_axis"]
    box.setChecked(True)
    assert st.ext("rows_weak_axis") is True
    st.set("base_plate", "rod_spacing", "200 mm")
    assert st.valid, st.error
    ys = sorted({round(a.y) for a in st.model.anchors})
    assert ys == xs  # the rows moved from x = ±f to y = ±f
    assert {round(a.x) for a in st.model.anchors} == {-100, 100}
    assert st.model.rows_weak  # the dimension of f is drawn along y
