# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Floating window that follows the CalculiX analysis, with a cancel button."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from openfemconex.i18n import tr

AXIAL_SHARE = 0.1
"""Share of the progress bar given to step 1 (axial load alone)."""


@dataclass(frozen=True)
class Increment:
    step: int
    number: int
    attempt: str
    iterations: int
    step_time: float
    increment: float

    @property
    def cutback(self) -> bool:
        """An attempt that did not converge and is repeated with a smaller increment."""
        return self.attempt.endswith("U")


def read_increments(sta: Path) -> list[Increment]:
    """Increments listed in the CalculiX status file (.sta)."""
    out = []
    try:
        text = sta.read_text(errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        p = line.split()
        if len(p) == 7 and p[0].isdigit():
            try:
                out.append(Increment(int(p[0]), int(p[1]), p[2], int(p[3]), float(p[5]),
                                     float(p[6])))
            except ValueError:
                continue
    return out


def last_iteration(cvg: Path) -> tuple[int, float] | None:
    """(iteration, largest residual force) of the last line of the .cvg file."""
    try:
        lines = cvg.read_text(errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        p = line.split()
        if len(p) >= 6 and p[0].isdigit():
            try:
                return int(p[3]), float(p[5])
            except ValueError:
                return None
    return None


def fraction(increments: list[Increment], steps: int = 2) -> float:
    """Fraction of the combination reached by the converged increments."""
    done = [i for i in increments if not i.cutback]
    if not done:
        return 0.0
    last = done[-1]
    if steps == 1:
        return last.step_time
    if last.step == 1:
        return AXIAL_SHARE * last.step_time
    return AXIAL_SHARE + (1 - AXIAL_SHARE) * last.step_time


def describe(inc: Increment) -> str:
    load = tr("carga axial") if inc.step == 1 else tr("momentos y cortantes")
    if inc.cutback:
        return tr("Paso {step} ({load}), incremento {n}: no convergió en {it} iteraciones; se "
                  "reintenta con un incremento menor", step=inc.step, load=load, n=inc.number,
                  it=inc.iterations)
    return tr("Paso {step} ({load}), incremento {n}: {pct} % aplicado, {it} iteraciones",
              step=inc.step, load=load, n=inc.number, pct=f"{100 * inc.step_time:.1f}",
              it=inc.iterations)


def _clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class SolveProgress(QDialog):
    """Combination, stage, CalculiX increments and elapsed time; Cancel stops ccx."""

    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Resolviendo con CalculiX"))
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.resize(700, 460)
        self.combo_label = QLabel()
        bold = self.combo_label.font()
        bold.setBold(True)
        self.combo_label.setFont(bold)
        self.stage_label = QLabel()
        self.stage_label.setWordWrap(True)
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.combo_bar = QProgressBar()
        self.combo_bar.setRange(0, 1000)
        self.combo_bar.setFormat("%p %")
        self.total_bar = QProgressBar()
        self.total_bar.setRange(0, 1000)
        self.total_bar.setFormat("%p %")
        self.time_label = QLabel()
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.cancel_button = QPushButton(tr("Cancelar"))
        self.cancel_button.clicked.connect(self._cancel)
        self.hide_button = QPushButton(tr("Ocultar"))
        self.hide_button.setToolTip(tr("El análisis sigue; el avance queda en la barra de estado"))
        self.hide_button.clicked.connect(self.hide)
        layout = QVBoxLayout(self)
        layout.addWidget(self.combo_label)
        layout.addWidget(self.stage_label)
        layout.addWidget(self.combo_bar)
        layout.addWidget(self.detail_label)
        layout.addWidget(QLabel(tr("Total")))
        layout.addWidget(self.total_bar)
        layout.addWidget(self.time_label)
        layout.addWidget(self.log, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.hide_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self.poll)
        self._sta: Path | None = None
        self._seen = 0
        self._done = self._total = 0
        self._t0 = self._tc = 0.0
        self._finished = False

    # -- driven by the main window
    def start(self, total: int, elements: int, nodes: int, threads: int) -> None:
        self._done, self._total, self._finished = 0, total, False
        self._t0 = time.monotonic()
        self.log.clear()
        self.cancel_button.setText(tr("Cancelar"))
        self.cancel_button.setEnabled(True)
        self.hide_button.show()
        self.combo_bar.setValue(0)
        self.total_bar.setValue(0)
        self.add(tr("Malla de {elements} hexaedros y {nodes} nodos; {n} combinaciones; "
                    "CalculiX con {t} hilos.", elements=elements, nodes=nodes, n=total,
                    t=threads))
        self._timer.start()
        self.show()
        self.raise_()

    def combo_started(self, name: str, sta: Path) -> None:
        self._sta, self._seen = sta, 0
        self._tc = time.monotonic()
        self.combo_label.setText(tr("Combinación {i} de {n}: {name}", i=self._done + 1,
                                    n=self._total, name=name))
        self.stage_label.setText("")
        self.detail_label.setText("")
        self.combo_bar.setValue(0)
        self.add("")
        self.add(tr("— {name} —", name=name))

    def stage(self, text: str) -> None:
        self.stage_label.setText(text)
        self.add(text)
        if text == tr("CalculiX no convergió: se reintenta con la ley de anclaje suavizada"):
            self._seen = 0

    def combo_finished(self, summary: str) -> None:
        self._done += 1
        self.combo_bar.setValue(1000)
        self.add(summary)
        self._update_total(0.0)

    def finished(self, cancelled: bool = False) -> None:
        self._timer.stop()
        self._finished = True
        self.poll()
        text = tr("Análisis detenido.") if cancelled else tr("Análisis terminado.")
        self.stage_label.setText(text)
        self.add(text + " " + tr("Tiempo total {t}.", t=_clock(time.monotonic() - self._t0)))
        self.cancel_button.setText(tr("Cerrar"))
        self.cancel_button.setEnabled(True)
        self.hide_button.hide()

    def add(self, text: str) -> None:
        self.log.appendPlainText(text)

    # -- CalculiX files
    def poll(self) -> None:
        now = time.monotonic()
        self.time_label.setText(tr("Tiempo: {t} en esta combinación, {all} en total",
                                   t=_clock(now - self._tc) if self._tc else "0:00",
                                   all=_clock(now - self._t0)))
        if self._sta is None or self._finished:
            return
        incs = read_increments(self._sta)
        for inc in incs[self._seen:]:
            self.add("  " + describe(inc))
        self._seen = len(incs)
        f = fraction(incs)
        if incs:
            self.combo_bar.setValue(int(1000 * f))
            last = incs[-1]
            it = last_iteration(self._sta.with_suffix(".cvg"))
            detail = describe(last)
            if it is not None:
                detail += "\n" + tr("Iteración {i} del incremento siguiente; residuo de fuerza "
                                    "máximo {r} N", i=it[0], r=f"{it[1]:.3g}")
            self.detail_label.setText(detail)
        self._update_total(f)

    def _update_total(self, current: float) -> None:
        total = (self._done + (0.0 if self._done >= self._total else current)) / max(
            self._total, 1)
        self.total_bar.setValue(int(1000 * total))

    def overall(self) -> float:
        return self.total_bar.value() / 1000

    def _cancel(self) -> None:
        if self._finished:
            self.close()
            return
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText(tr("Cancelando…"))
        self.stage_label.setText(tr("Deteniendo CalculiX…"))
        self.cancel_requested.emit()
