# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Interface of the moment end-plate connection, without OpenGL."""

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["OPENFEMCONEX_NO_3D"] = "1"

from openfemconex.gui.connection_picker import ConnectionPicker  # noqa: E402
from openfemconex.gui.main import MainWindow  # noqa: E402

EXAMPLE = Path(__file__).parents[1] / "examples" / "placa_extremo.ocnx"


@pytest.fixture
def window(qtbot, monkeypatch):
    w = MainWindow()
    qtbot.addWidget(w)
    monkeypatch.setattr(w, "_confirm_discard", lambda: True)
    return w


def add_end_plate(window):
    index = window.state.add_connection("moment_end_plate")
    window.set_mode("moment_end_plate", index)
    return index


def test_picker_offers_the_end_plate(qtbot):
    picker = ConnectionPicker()
    qtbot.addWidget(picker)
    assert picker.buttons["moment_end_plate"].isEnabled()


def test_new_connection_and_shared_stages(window):
    index = add_end_plate(window)
    conn = window.state.connections()[index]
    assert conn["type"] == "moment_end_plate" and conn["name"] == "PE-1"
    assert window.ribbons.currentWidget() is window.ep_ribbon
    assert {"Cargas", "Análisis", "Reporte"} <= set(window.ep_ribbon._names)
    assert window.ep.error == ""
    calls = []
    window.solve_ep = lambda: calls.append("ep")
    window.analysis_panel.solve_requested.emit()
    assert calls == ["ep"]


def test_solve_fills_checks_and_tree(window):
    add_end_plate(window)
    window.solve_ep()
    assert window.ep.results and all(r.ok for r in window.ep.results)
    assert window.ep.checks.rowCount() > 10
    assert "Cumple" in window.status_label.text()
    texts = []

    def walk(item):
        texts.append(item.text(0))
        for i in range(item.childCount()):
            walk(item.child(i))

    walk(window.tree.topLevelItem(0))
    assert any(t.startswith("U: ") and "ratio" in t for t in texts)


def test_editing_a_page_updates_the_connection(window):
    index = add_end_plate(window)
    window.solve_ep()
    window.ep.update(("end_plate", "thickness"), "3/4 in")
    assert window.state.connections()[index]["end_plate"]["thickness"] == "3/4 in"
    assert window.ep.stale
    form = window.ep.forms["Placa de extremo"]
    window.ep.update(("end_plate", "layout"), "extended_8_stiffened")
    assert window.ep.error  # 8ES needs p_b
    assert form.widgets[("end_plate", "pb")].isEnabled()
    window.ep.update(("end_plate", "pb"), "3 in")
    window.ep.update(("end_plate", "pext"), "6 in")
    assert window.ep.error == ""


def test_seismic_toggle(window):
    add_end_plate(window)
    form = window.ep.forms["Diseño sísmico"]
    assert form.toggle.isEnabled()  # 4E is prequalified
    form.toggle.setChecked(True)
    assert window.ep.data["seismic"]["system"] == "smf"
    window.solve_ep()
    assert any(r.combo.name == "AISC 358" for r in window.ep.results)
    form.toggle.setChecked(False)
    assert window.ep.data["seismic"] is None
    window.ep.update(("end_plate", "layout"), "flush_2")
    assert not form.toggle.isEnabled()


def test_panel_zone_shows_column_forces(window):
    add_end_plate(window)
    source = window.ep.combinations.source
    assert source.hidden() == {"Vc", "Pc"}
    window.ep.update(("column_side", "panel_zone"), True)
    assert source.hidden() == set()


def test_example_opens_and_reports(window, tmp_path):
    window.state.open(EXAMPLE)
    modes = [c["type"] for c in window.state.connections()]
    assert "moment_end_plate" in modes
    index = modes.index("moment_end_plate")
    window.set_mode("moment_end_plate", index)
    window.state.path = tmp_path / "p.ocnx"
    path = window.generate_ep_report()
    html = path.read_text(encoding="utf-8")
    assert "Reporte de verificación" in html and "esquemas/placa_extremo_fuerzas.png" in html
    assert (path.parent / "esquemas" / "placa_extremo_fuerzas.png").exists()
    docx = window.export_ep_docx(str(tmp_path / "r.docx"))
    assert docx.exists()
    pdf = window.export_ep_pdf(str(tmp_path / "r.pdf"))
    assert pdf.exists() and pdf.stat().st_size > 10000


def test_example_file_is_valid():
    from openconex.units import UnitSystem

    from openfemconex import end_plate_project as epp

    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    conns = [c for c in data["openfemconex"]["connections"] if c["type"] == epp.TYPE]
    assert len(conns) >= 2
    for c in conns:
        assert epp.run(c, UnitSystem()).combos
