# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 The OpenFEMConex contributors
"""Editable Word report (python-docx) from the blocks of :mod:`openfemconex.report`."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openconex.report.docx import latex_to_text

from openfemconex.i18n import tr
from openfemconex.report import Block

__all__ = ["write_docx"]

COLORS = {"ok": RGBColor(0x17, 0x69, 0x2B), "ng": RGBColor(0xB0, 0x00, 0x20),
          "na": RGBColor(0x77, 0x77, 0x77), "note": RGBColor(0x55, 0x55, 0x55)}


def _shade(cell, color: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), color)
    props.append(shading)


def _text(cell, value, bold: bool = False, right: bool = False, size: float = 8.5) -> None:
    status = isinstance(value, tuple)
    text = value[1] if status else str(value)
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold or status
    if status:
        run.font.color.rgb = COLORS.get(value[0], COLORS["na"])
    if right:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT


def _table(doc, headers: list[str], rows: list[list], numeric=frozenset()) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        _text(cell, h, bold=True)
        _shade(cell, "E8ECF0")
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            _text(cells[i], value, right=i in numeric)
    doc.add_paragraph()


def _figures(doc, items: list[tuple[str, str]], figure_dir: Path, width_cm: float) -> None:
    for caption, name in items:
        path = figure_dir / name
        if not path.exists():
            continue
        doc.add_picture(str(path), width=Cm(width_cm))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        p = doc.add_paragraph(caption)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in p.runs:
            run.font.size = Pt(8.5)
            run.italic = True


def write_docx(blocks: list[Block], path: str | Path, figure_dir: str | Path) -> Path:
    """Word document of the report; the figures are read from ``figure_dir``."""
    path, figure_dir = Path(path), Path(figure_dir)
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    for side in ("left_margin", "right_margin"):
        setattr(section, side, Cm(2.0))
    section.top_margin = section.bottom_margin = Cm(2.0)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)
    usable = 17.0
    title = next((b[1] for b in blocks if b[0] == "h1"), "")
    header = section.header.paragraphs[0]
    header.text = f"OpenFEMConex — {title}"
    header.runs[0].font.size = Pt(8)
    header.runs[0].font.color.rgb = COLORS["note"]
    for b in blocks:
        kind = b[0]
        if kind == "h1":
            doc.add_heading(b[1], level=0)
        elif kind == "h2":
            doc.add_heading(b[1], level=1)
        elif kind == "h3":
            doc.add_heading(b[1], level=2)
        elif kind == "p":
            p = doc.add_paragraph()
            run = p.add_run(b[1])
            if b[2] in COLORS:
                run.font.color.rgb = COLORS[b[2]]
                run.bold = b[2] in ("ok", "ng")
            if b[2] == "note":
                run.font.size = Pt(9)
        elif kind == "verdict":
            p = doc.add_paragraph(tr("Resultado global:") + " ")
            run = p.add_run(tr("Cumple") if b[1] else tr("No cumple"))
            run.bold = True
            run.font.color.rgb = COLORS["ok" if b[1] else "ng"]
            p.add_run(b[2])
        elif kind == "ficha":
            table = doc.add_table(rows=0, cols=2)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for label, value in b[1]:
                cells = table.add_row().cells
                _text(cells[0], label, bold=True, size=9.5)
                _shade(cells[0], "E8ECF0")
                _text(cells[1], value, size=9.5)
                cells[0].width, cells[1].width = Cm(5.0), Cm(12.0)
            doc.add_paragraph()
        elif kind == "table":
            _table(doc, b[1], b[2], b[3])
        elif kind == "figs":
            if b[2]:
                doc.add_heading(b[1], level=2)
                wide = len(b) > 3 and b[3]
                _figures(doc, b[2], figure_dir, usable if wide else 0.75 * usable)
        elif kind == "advice":
            p = doc.add_paragraph(b[1])
            p.runs[0].font.size = Pt(9)
            p.runs[0].font.color.rgb = COLORS["note"]
            for title_, items in b[2]:
                item = doc.add_paragraph(style="List Bullet")
                item.add_run(title_).bold = True
                for a in items:
                    doc.add_paragraph(a, style="List Bullet 2")
        elif kind == "traces":
            if b[1]:
                doc.add_heading(tr("Desarrollo de las verificaciones"), level=3)
            for title_, ratio, steps in b[1]:
                p = doc.add_paragraph()
                p.add_run(f"{title_}: ratio {ratio:.2f}").bold = True
                _table(doc, [tr(h) for h in ("Símbolo", "Expresión", "Valor", "Referencia")],
                       [[latex_to_text(sym), latex_to_text(expr), value, clause]
                        for sym, expr, value, clause in steps], {2})
        elif kind == "notes":
            doc.add_heading(b[1], level=1)
            for n in b[2]:
                doc.add_paragraph(n, style="List Bullet")
        elif kind == "image":
            image = Path(b[1])
            if image.exists():
                doc.add_picture(str(image), width=Cm(usable))
    doc.save(str(path))
    return path
