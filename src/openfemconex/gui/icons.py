# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Icons drawn with QPainter, so the program ships no image files."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

STEEL = QColor("#3d5a80")
ACCENT = QColor("#e07a1f")
CONCRETE = QColor("#9aa0a6")
GREEN = QColor("#2e8b57")
RED = QColor("#c0392b")
SIZE = 64


def _pen(color: QColor, width: float = 4.0) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _poly(*pts: tuple[float, float]) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in pts])


def _column(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(STEEL)
    p.drawRect(QRectF(12, 10, 40, 9))
    p.drawRect(QRectF(12, 45, 40, 9))
    p.drawRect(QRectF(28, 19, 8, 26))


def _plate(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 3))
    p.setBrush(QColor("#c9d6e8"))
    p.drawRect(QRectF(8, 8, 48, 48))
    p.setBrush(Qt.GlobalColor.white)
    for x in (18, 46):
        for y in (18, 46):
            p.drawEllipse(QPointF(x, y), 4, 4)


def _anchor(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 6))
    p.drawLine(QPointF(32, 8), QPointF(32, 50))
    p.setPen(_pen(ACCENT, 6))
    p.drawLine(QPointF(22, 16), QPointF(42, 16))
    p.drawLine(QPointF(22, 52), QPointF(42, 52))


def _concrete(p: QPainter) -> None:
    p.setPen(_pen(QColor("#6b7075"), 3))
    p.setBrush(CONCRETE)
    p.drawPolygon(_poly((8, 24), (32, 14), (56, 24), (56, 50), (32, 58), (8, 50)))
    p.drawLine(QPointF(8, 24), QPointF(32, 34))
    p.drawLine(QPointF(56, 24), QPointF(32, 34))
    p.drawLine(QPointF(32, 34), QPointF(32, 58))


def _weld(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 6))
    p.drawLine(QPointF(8, 50), QPointF(56, 50))
    p.drawLine(QPointF(24, 8), QPointF(24, 50))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(ACCENT)
    p.drawPolygon(_poly((27, 47), (27, 26), (48, 47)))


def _load(p: QPainter) -> None:
    p.setPen(_pen(RED, 6))
    p.drawLine(QPointF(32, 8), QPointF(32, 44))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(RED)
    p.drawPolygon(_poly((18, 38), (46, 38), (32, 58)))


def _combo(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 5))
    for y in (16, 32, 48):
        p.drawLine(QPointF(24, y), QPointF(54, y))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(ACCENT)
    for y in (16, 32, 48):
        p.drawEllipse(QPointF(12, y), 5, 5)


def _mesh(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 3))
    for i in range(5):
        v = 8 + 12 * i
        p.drawLine(QPointF(v, 8), QPointF(v, 56))
        p.drawLine(QPointF(8, v), QPointF(56, v))


def _play(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(GREEN)
    p.drawPolygon(_poly((18, 10), (52, 32), (18, 54)))


def _stop(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(RED)
    p.drawRoundedRect(QRectF(14, 14, 36, 36), 5, 5)


def _results(p: QPainter) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    for i, color in enumerate(("#30123b", "#28bbec", "#a2fc3c", "#fb8022", "#7a0403")):
        p.setBrush(QColor(color))
        p.drawRect(QRectF(10 + 9 * i, 12, 9, 40))


def _check(p: QPainter) -> None:
    p.setPen(_pen(GREEN, 8))
    path = QPainterPath(QPointF(10, 34))
    path.lineTo(26, 50)
    path.lineTo(54, 14)
    p.drawPath(path)


def _table(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 3))
    p.setBrush(Qt.GlobalColor.white)
    p.drawRect(QRectF(8, 10, 48, 44))
    p.drawLine(QPointF(8, 24), QPointF(56, 24))
    p.drawLine(QPointF(8, 39), QPointF(56, 39))
    p.drawLine(QPointF(28, 10), QPointF(28, 54))


def _page(p: QPainter, fold: bool = True) -> None:
    p.setPen(_pen(STEEL, 3))
    p.setBrush(Qt.GlobalColor.white)
    p.drawPolygon(_poly((14, 6), (40, 6), (52, 18), (52, 58), (14, 58)))
    if fold:
        p.drawLine(QPointF(40, 6), QPointF(40, 18))
        p.drawLine(QPointF(40, 18), QPointF(52, 18))


def _report(p: QPainter) -> None:
    _page(p)
    p.setPen(_pen(ACCENT, 3))
    for y in (28, 38, 48):
        p.drawLine(QPointF(22, y), QPointF(44, y))


def _new(p: QPainter) -> None:
    _page(p)
    p.setPen(_pen(GREEN, 5))
    p.drawLine(QPointF(33, 28), QPointF(33, 50))
    p.drawLine(QPointF(22, 39), QPointF(44, 39))


def _open(p: QPainter) -> None:
    p.setPen(_pen(QColor("#a66a00"), 3))
    p.setBrush(QColor("#f2c14e"))
    p.drawPolygon(_poly((6, 16), (24, 16), (30, 22), (56, 22), (56, 52), (6, 52)))


def _save(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 3))
    p.setBrush(QColor("#c9d6e8"))
    p.drawPolygon(_poly((8, 8), (46, 8), (56, 18), (56, 56), (8, 56)))
    p.setBrush(Qt.GlobalColor.white)
    p.drawRect(QRectF(18, 8, 22, 14))
    p.drawRect(QRectF(16, 34, 32, 22))


def _browser(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 3))
    p.setBrush(Qt.GlobalColor.white)
    p.drawEllipse(QPointF(32, 32), 24, 24)
    p.drawEllipse(QPointF(32, 32), 10, 24)
    p.drawLine(QPointF(8, 32), QPointF(56, 32))


def _pdf(p: QPainter) -> None:
    _page(p)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(RED)
    p.drawRect(QRectF(8, 30, 40, 18))


def _view(p: QPainter) -> None:
    p.setPen(_pen(STEEL, 3))
    p.setBrush(QColor("#c9d6e8"))
    p.drawPolygon(_poly((32, 8), (54, 20), (32, 32), (10, 20)))
    p.drawPolygon(_poly((10, 20), (32, 32), (32, 56), (10, 44)))
    p.drawPolygon(_poly((54, 20), (32, 32), (32, 56), (54, 44)))


_PAINTERS: dict[str, Callable[[QPainter], None]] = {
    "column": _column, "plate": _plate, "anchor": _anchor, "concrete": _concrete,
    "weld": _weld, "load": _load, "combo": _combo, "mesh": _mesh, "play": _play,
    "stop": _stop, "results": _results, "check": _check, "table": _table, "report": _report,
    "new": _new, "open": _open, "save": _save, "browser": _browser, "pdf": _pdf, "view": _view,
}


def icon(name: str) -> QIcon:
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _PAINTERS[name](painter)
    painter.end()
    return QIcon(pixmap)


def app_icon() -> QIcon:
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _concrete(painter)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(STEEL)
    painter.drawRect(QRectF(26, 2, 12, 24))
    painter.setBrush(ACCENT)
    painter.drawRect(QRectF(14, 22, 36, 6))
    painter.end()
    return QIcon(pixmap)
