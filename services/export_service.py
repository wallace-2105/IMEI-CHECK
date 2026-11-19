"""Exportação profissional de resultados e histórico para planilha Excel (.xlsx)."""

from __future__ import annotations

import io
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from services.imei_validator import (
    STATUS_ERRO_CONSULTA,
    STATUS_IDENTIFICADO,
    STATUS_IMEI_INVALIDO,
    STATUS_TAC_NAO_ENCONTRADO,
)

EXCEL_HEADERS = [
    "Data da consulta",
    "IMEI",
    "TAC",
    "Fabricante",
    "Modelo",
    "Status",
    "Fonte dos dados",
]

_HEADER_FILL = PatternFill(start_color="0F4C81", end_color="0F4C81", fill_type="solid")
_HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
_ZEBRA_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
_BODY_FONT = Font(name="Calibri", size=10, color="0F172A")

_THIN_BORDER_SIDE = Side(style="thin", color="CBD5E1")
_CELL_BORDER = Border(
    left=_THIN_BORDER_SIDE,
    right=_THIN_BORDER_SIDE,
    top=_THIN_BORDER_SIDE,
    bottom=_THIN_BORDER_SIDE,
)

_STATUS_STYLES = {
    STATUS_IDENTIFICADO: (
        PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid"),
        Font(name="Calibri", size=10, bold=True, color="166534"),
    ),
    STATUS_TAC_NAO_ENCONTRADO: (
        PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid"),
        Font(name="Calibri", size=10, bold=True, color="334155"),
    ),
    STATUS_IMEI_INVALIDO: (
        PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"),
        Font(name="Calibri", size=10, bold=True, color="991B1B"),
    ),
    STATUS_ERRO_CONSULTA: (
        PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid"),
        Font(name="Calibri", size=10, bold=True, color="92400E"),
    ),
}


def _extract_row_values(item: object) -> list[str]:
    """Extrai valores normalizados de IMEILookupResult ou dict de histórico."""
    if isinstance(item, dict):
        queried_at = item.get("queried_at") or ""
        imei = item.get("imei") or item.get("imei_normalizado") or item.get("imei_informado") or ""
        tac = item.get("tac") or ""
        fabricante = item.get("fabricante") or "-"
        modelo = item.get("modelo") or "-"
        status = item.get("status") or ""
        fonte = item.get("fonte") or "-"
    else:
        queried_at = getattr(item, "queried_at", "") or ""
        imei = getattr(item, "imei_normalizado", None) or getattr(item, "imei_informado", "") or ""
        tac = getattr(item, "tac", None) or ""
        fabricante = getattr(item, "fabricante", None) or "-"
        modelo = getattr(item, "modelo", None) or "-"
        status = getattr(item, "status", "") or ""
        fonte = getattr(item, "fonte", None) or "-"

    return [
        str(queried_at),
        str(imei),
        str(tac) if tac else "-",
        str(fabricante),
        str(modelo),
        str(status),
        str(fonte),
    ]


def export_results_to_excel(
    results: Iterable[object],
    sheet_title: str = "Consultas IMEI",
) -> bytes:
    """Gera arquivo XLSX formatado em memória a partir de resultados ou histórico."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.views.sheetView[0].showGridLines = True

    ws.append(EXCEL_HEADERS)
    ws.row_dimensions[1].height = 26

    for col_idx in range(1, len(EXCEL_HEADERS) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=False)
        cell.border = _CELL_BORDER

    row_count = 1
    for item in results:
        row_count += 1
        values = _extract_row_values(item)
        ws.append(values)
        ws.row_dimensions[row_count].height = 20

        is_zebra = row_count % 2 == 1
        status_value = values[5]

        for col_idx in range(1, len(EXCEL_HEADERS) + 1):
            cell = ws.cell(row=row_count, column=col_idx)
            cell.border = _CELL_BORDER
            cell.font = _BODY_FONT

            # Garante formato texto para IMEI e TAC evitando notação científica ou perda de zeros à esquerda
            if col_idx in (2, 3):
                cell.number_format = "@"
                cell.alignment = Alignment(horizontal="center", vertical="center")
            elif col_idx in (1, 6):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if col_idx == 6 and status_value in _STATUS_STYLES:
                fill, font = _STATUS_STYLES[status_value]
                cell.fill = fill
                cell.font = font
            elif is_zebra:
                cell.fill = _ZEBRA_FILL

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(EXCEL_HEADERS))}{max(row_count, 1)}"

    min_widths = {1: 20, 2: 19, 3: 12, 4: 20, 5: 28, 6: 22, 7: 30}
    for col_idx in range(1, len(EXCEL_HEADERS) + 1):
        max_len = max(
            len(str(ws.cell(row=r, column=col_idx).value or ""))
            for r in range(1, row_count + 1)
        )
        width = max(min_widths.get(col_idx, 14), min(max_len + 4, 48))
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
