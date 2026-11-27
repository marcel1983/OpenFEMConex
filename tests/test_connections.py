# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Projects with several connections and the through-bolt connection in the interface."""

import copy
import os

import pytest

from openfemconex import through_bolt_project as tbp
from openfemconex.units import display_units

SI = display_units("SI_kN_m")


def test_template_builds_and_checks():
    data = tbp.new_connection("PP-1")
    conn = tbp.build(data, SI)
    assert conn.bolts == 8
    assert conn.back_plate.height == pytest.approx(conn.beam.d + 2 * 3.5 * 25.4 + 50)
    results = tbp.run(data, SI)
    # service load cases D and L: the ASCE 7 combinations 1.4D and 1.2D + 1.6L
    assert [r.combo.name for r in results] == ["LRFD-1", "LRFD-2"]
    assert results[1].combo.V == pytest.approx(100e3) and results[1].combo.M == pytest.approx(180e6)
    assert all(r.ok for r in results)
    assert any(c.id.startswith("through_bolt.") for c in results[0].checks)
    html = tbp.report_html(data, results, SI, {"name": "Edificio"}, figures="img")
    assert "Resumen" in html and "Edificio" in html and "img/corte_friccion.png" in html
    # same order as the base plate report: summary, recommendations and installation
    # requirements at the end; without CalculiX it says so
    assert "sin modelo de elementos finitos" in html
    assert html.index("Verificaciones analíticas") < html.index("Resumen de resultados")
    assert html.index("Resumen de resultados") < html.index("Requisitos de instalación")
    assert "Camisas sin adherencia" in html and "no hay recomendaciones" in html


def test_recommendations_for_failing_checks():
    data = tbp.new_connection("PP-1")
    data["end_plate"]["bolt_diameter"] = "5/8 in"
    data["member"]["fc"] = "14 MPa"
    results = tbp.run(data, SI)
    assert not all(r.ok for r in results)
    html = tbp.report_html(data, results, SI, {})
    assert "Recomendaciones" in html and "Cambios sugeridos" in html


def test_opposite_beam_and_grout_from_the_file():
    data = tbp.new_connection()
    data["opposite"] = copy.deepcopy(tbp.OPPOSITE)
    data["shear"]["type"] = "grout"
    data["combinations"] = [{"name": "E", "V": "120 kN", "M": "130 kN*m", "V2": "60 kN",
                             "M2": "-90 kN*m"}]
    conn = tbp.build(data, SI)
    assert conn.opposite is not None and conn.back_plate is None
    assert conn.grout_length == pytest.approx(150.0)
    (res,) = tbp.run(data, SI)
    assert any("viga 2" in c.combo for c in res.checks)
    assert any(c.id.startswith("through_bolt.grout_bearing") for c in res.checks)


def test_old_factored_combinations_become_load_cases():
    data = tbp.new_connection()
    data.pop("cases")
    data["combinations"] = [{"name": "C1", "V": "100 kN", "M": "180 kN*m"}]
    (combo,) = tbp.combinations(data, SI)
    assert combo.name == "C1" and combo.M == pytest.approx(180e6)
    tbp.migrate(data)
    assert data["cases"][0]["name"] == "C1"
    assert data["combinations"]["include_code"] is False


def test_custom_and_seismic_combinations():
    data = tbp.new_connection()
    data["cases"].append({"name": "E", "type": "E", "M": "50 kN*m"})
    assert not any("E" in c.factors for c in tbp.combinations(data, SI))  # no S_DS
    data["combinations"]["SDS"] = 0.5
    seismic = [c for c in tbp.combinations(data, SI) if "E" in c.factors]
    assert {c.factors["E"] for c in seismic} == {1.0, -1.0}
    data["combinations"]["custom"] = [{"name": "Mía", "factors": {"D": 1.0, "L": 0.5}}]
    mine = tbp.combinations(data, SI)[-1]
    assert mine.name == "Mía" and mine.M == pytest.approx(100e6)
    data["combinations"]["custom"][0]["method"] = "ASD"
    with pytest.raises(ValueError, match="LRFD"):
        tbp.combinations(data, SI)


def test_bare_numbers_take_the_project_units():
    data = tbp.new_connection()
    data["member"]["thickness"] = "20"
    us = display_units("US")
    assert tbp.build(data, us).member.thickness == pytest.approx(20 * 25.4)


def test_invalid_data_is_reported():
    data = tbp.new_connection()
    data["member"]["kind"] = "column"
    with pytest.raises(ValueError, match="ancho de la columna"):
        tbp.build(data, SI)
    data["member"]["width"] = "600 mm"
    data["beam"] = "W99X1"
    with pytest.raises(ValueError, match="perfil"):
        tbp.build(data, SI)


# ---------------------------------------------------------------------------- interface
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["OPENFEMCONEX_NO_3D"] = "1"

from openfemconex.gui.connection_picker import TYPES, ConnectionPicker, type_pixmap  # noqa: E402
from openfemconex.gui.main import MainWindow  # noqa: E402
from openfemconex.gui.state import ProjectState  # noqa: E402


@pytest.fixture
def window(qtbot, monkeypatch):
    w = MainWindow()
    qtbot.addWidget(w)
    monkeypatch.setattr(w, "_confirm_discard", lambda: True)
    return w


def test_project_with_several_connections_round_trips(qtbot, tmp_path):
    st = ProjectState()
    assert st.has_base_plate and st.connections() == []
    i = st.add_connection("through_bolt")
    j = st.add_connection("through_bolt")
    assert (i, j) == (0, 1)
    assert [c["name"] for c in st.connections()] == ["PP-1", "PP-2"]
    assert st.valid  # the base plate is untouched
    path = st.save(tmp_path / "varias.ocnx")
    other = ProjectState()
    other.open(path)
    assert [c["name"] for c in other.connections()] == ["PP-1", "PP-2"]
    other.remove_connection(-1)
    assert not other.has_base_plate and not other.valid
    other.remove_connection(0)
    with pytest.raises(ValueError):
        other.remove_connection(0)  # the last connection stays
    with pytest.raises(ValueError):
        st.add_connection("base_plate")  # one base plate per project


def test_new_project_of_another_type(qtbot, tmp_path):
    st = ProjectState()
    st.new("through_bolt")
    assert not st.has_base_plate
    assert len(st.connections()) == 1
    path = st.save(tmp_path / "pp.ocnx")
    st.open(path)
    assert st.connections()[0]["type"] == "through_bolt"
    st.set_units("US")
    conn = st.connections()[0]
    assert conn["member"]["thickness"].endswith("in")
    assert tbp.build(conn, st.units).member.thickness == pytest.approx(500.0, rel=1e-3)


def test_picker_shows_every_type_with_its_picture(qtbot):
    picker = ConnectionPicker(disabled={"base_plate": "ya existe"})
    qtbot.addWidget(picker)
    assert set(picker.buttons) == {t.key for t in TYPES}
    assert not picker.buttons["base_plate"].isEnabled()
    assert not picker.buttons["splice"].isEnabled()  # not available yet
    assert picker.selected == "through_bolt"
    for t in TYPES:
        assert not type_pixmap(t.key).isNull()


def test_window_edits_and_checks_a_through_bolt_connection(window):
    st = window.state
    index = st.add_connection("through_bolt")
    window.set_mode("through_bolt", index)
    assert window.ribbons.currentWidget() is window.tb_ribbon
    assert "Pernos pasantes" in window.viewer.description
    edit = window.tb.forms["Muro o columna"].widgets[("member", "thickness")]
    edit.setText("450")
    edit.editingFinished.emit()
    assert st.connections()[index]["member"]["thickness"] == "450 mm"
    assert st.dirty
    window.calculate_tb()
    assert window.tb.checks.rowCount() > 20
    assert "Cumple" in window.status_label.text()
    window.tb.checks.selectRow(0)
    assert "Símbolo" in window.tb.trace.toHtml()
    window.tb.update(("shear", "mu"), 0.3)
    assert "desactualizados" in window.status_label.text()
    window._fill_tree()
    top = window.tree.topLevelItem(0)
    assert top.childCount() == 2  # base plate and PP-1
    window.set_mode("base_plate")
    assert window.ribbons.currentWidget() is window.ribbon
    assert st.valid


def test_window_report_of_a_through_bolt_connection(window, tmp_path):
    index = window.state.add_connection("through_bolt")
    window.set_mode("through_bolt", index)
    path = window.generate_tb_report()
    assert path is not None and "Resumen" in path.read_text(encoding="utf-8")
    pdf = window.export_tb_pdf(str(tmp_path / "pp.pdf"))
    assert pdf.stat().st_size > 10_000
    # the HTML names its images relative to its folder (a browser does not resolve
    # "file:" URLs of a relative path) and carries the help diagrams with it
    import re

    srcs = re.findall(r'<img src="([^"]+)"', path.read_text(encoding="utf-8"))
    assert srcs and all(not s.startswith(("file:", "/")) for s in srcs)
    assert all((path.parent / s).exists() for s in srcs)
    docx = window.export_tb_docx(str(tmp_path / "pp.docx"))
    assert docx.stat().st_size > 10_000


def test_new_project_dialog_picks_the_type(window, monkeypatch):
    def pick(self):
        self.selected = "through_bolt"
        return True

    monkeypatch.setattr(ConnectionPicker, "exec", pick)
    window.new_project()
    assert not window.state.has_base_plate
    assert window.mode == "through_bolt" and window.tb.index == 0


def test_example_project_opens_on_its_first_connection(window):
    from pathlib import Path

    window.open_project(str(Path(__file__).parents[1] / "examples" / "pernos_pasantes.ocnx"))
    assert window.mode == "through_bolt" and window.tb.index == 0
    assert len(window.state.connections()) == 2
    for i in range(2):
        window.set_mode("through_bolt", i)
        window.calculate_tb()
        assert all(r.ok for r in window.tb.results)


def test_through_bolt_loads_tab_works_like_the_base_plate(window):
    index = window.state.add_connection("through_bolt")
    window.set_mode("through_bolt", index)
    loads = window.tb.combinations
    assert loads.cases.rowCount() == 2 and loads.combos.rowCount() == 2
    assert loads.cases.isColumnHidden(7)  # P2: no opposite beam
    assert not loads.asd.isVisible() or not loads.asd.isEnabled()
    loads._add_case()  # W
    st_conn = window.state.connections()[index]
    assert [c["name"] for c in st_conn["cases"]] == ["D", "L", "W"]
    assert loads.combos.rowCount() > 2  # the wind combinations
    first = loads.combos.item(0, 0)
    first.setCheckState(first.checkState().Unchecked)
    assert first.text() not in loads.selected()
    loads.seismic["SDS"].setText("0.6")
    loads.seismic["SDS"].editingFinished.emit()
    assert window.state.connections()[index]["combinations"]["SDS"] == 0.6


def test_fem_results_join_the_checks_table(window):
    from types import SimpleNamespace

    index = window.state.add_connection("through_bolt")
    window.set_mode("through_bolt", index)
    window.calculate_tb()
    rows = window.tb.checks.rowCount()
    first = window.tb.results[0]
    extra = first.checks[0].model_copy(update={"id": "through_bolt.fem_bolt_tension"})
    window.tb.attach_fem(first.combo.name, [SimpleNamespace(side="viga 1", checks=[extra],
                                                            vtu=None)])
    assert window.tb.checks.rowCount() == rows + 1
    assert window.tb_fem_box.count() == 1
    assert window.tb.calculate(keep_fem=True)
    assert window.tb.results[0].fem  # kept while the data does not change


def test_the_picture_draws_the_reinforcement():
    pytest.importorskip("pyvista")
    from openfemconex import tb_scene

    data = tbp.new_connection()
    names = {p.name for p in tb_scene.parts(tbp.build(data, SI))}
    assert "refuerzo" in names
    data["member"].update(kind="column", width="600 mm")
    bars = next(p for p in tb_scene.parts(tbp.build(data, SI)) if p.name == "refuerzo")
    assert bars.mesh.n_points > 0
