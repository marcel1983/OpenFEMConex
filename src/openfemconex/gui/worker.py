# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Background thread that solves the selected combinations with CalculiX."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from openfemconex.diagnostics import diagnose
from openfemconex.i18n import tr
from openfemconex.mesh import Mesh
from openfemconex.model import BasePlateModel
from openfemconex.runner import CcxCancelled
from openfemconex.solve import ColumnOverloaded
from openfemconex.study import Study


class SolveWorker(QThread):
    started_combo = Signal(str)
    combo_done = Signal(str, object)
    """Combination name and its ComboReport."""
    combo_failed = Signal(str, str)
    combo_warning = Signal(str, str)
    """Combination name and a note of the pre-analysis diagnostics."""
    cancelled = Signal()

    def __init__(self, study: Study, combos: list, out: Path, model: BasePlateModel,
                 mesh: Mesh, reuse: bool = True) -> None:
        super().__init__()
        self.study, self.combos, self.out = study, combos, out
        self.model, self.mesh, self.reuse = model, mesh, reuse
        self.cancel = threading.Event()

    def run(self) -> None:
        for combo, loads in self.combos:
            if self.cancel.is_set():
                self.cancelled.emit()
                return
            self.started_combo.emit(combo.name)
            for note in diagnose(self.model, loads):
                self.combo_warning.emit(combo.name, note)
            try:
                report = self.study.run(combo, loads, self.out, mesh=self.mesh,
                                        model=self.model, reuse=self.reuse, cancel=self.cancel)
            except ColumnOverloaded:
                self.combo_failed.emit(combo.name, tr(
                    "no se resolvió porque la columna no resiste las cargas."))
                continue
            except CcxCancelled:
                self.cancelled.emit()
                return
            except Exception as exc:
                self.combo_failed.emit(combo.name, f"{type(exc).__name__}: {exc}")
                continue
            self.combo_done.emit(combo.name, report)
