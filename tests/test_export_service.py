"""Testes de exportação Excel (.xlsx) com openpyxl."""

from __future__ import annotations

import io
from openpyxl import load_workbook

from services.export_service import EXCEL_HEADERS, export_results_to_excel
from services.imei_validator import (
    STATUS_IDENTIFICADO,
    STATUS_IMEI_INVALIDO,
    STATUS_TAC_NAO_ENCONTRADO,
)
from services.tac_service import IMEILookupResult


def test_export_results_to_excel_structure_and_text_formatting():
    sample_results = [
        IMEILookupResult(
            queried_at="2026-11-19 17:30:00",
            imei_informado="011948001234561",
            imei_normalizado="011948001234561",
            tac="01194800",
            snr="123456",
            digito_verificador="1",
            fabricante="Fabricante Teste Excel",
            modelo="Modelo Teste Excel",
            nomes_alternativos=None,
            detalhes=None,
            status=STATUS_IDENTIFICADO,
            fonte="Osmocom TAC Database",
            referencia_url=None,
            contribuidor=None,
            data_registro_base=None,
            ultima_atualizacao_base="2026-11-19 17:00:00",
            mensagem="OK",
        ),
        IMEILookupResult(
            queried_at="2026-11-19 17:30:01",
            imei_informado="999999990000001",
            imei_normalizado="999999990000001",
            tac="99999999",
            snr="000000",
            digito_verificador="1",
            fabricante=None,
            modelo=None,
            nomes_alternativos=None,
            detalhes=None,
            status=STATUS_TAC_NAO_ENCONTRADO,
            fonte=None,
            referencia_url=None,
            contribuidor=None,
            data_registro_base=None,
            ultima_atualizacao_base="2026-11-19 17:00:00",
            mensagem="Não encontrado",
        ),
        IMEILookupResult(
            queried_at="2026-11-19 17:30:02",
            imei_informado="12345",
            imei_normalizado="12345",
            tac=None,
            snr=None,
            digito_verificador=None,
            fabricante=None,
            modelo=None,
            nomes_alternativos=None,
            detalhes=None,
            status=STATUS_IMEI_INVALIDO,
            fonte=None,
            referencia_url=None,
            contribuidor=None,
            data_registro_base=None,
            ultima_atualizacao_base="2026-11-19 17:00:00",
            mensagem="Inválido",
        ),
    ]

    xlsx_bytes = export_results_to_excel(sample_results)
    assert len(xlsx_bytes) > 0

    wb = load_workbook(io.BytesIO(xlsx_bytes))
    ws = wb.active

    headers = [ws.cell(row=1, column=i).value for i in range(1, len(EXCEL_HEADERS) + 1)]
    assert headers == EXCEL_HEADERS
    assert ws.freeze_panes == "A2"

    # Garante que zeros à esquerda e 15 dígitos sejam preservados como texto ('@')
    assert ws.cell(row=2, column=2).value == "011948001234561"
    assert ws.cell(row=2, column=2).number_format == "@"
    assert ws.cell(row=2, column=3).value == "01194800"
    assert ws.cell(row=2, column=3).number_format == "@"
    assert ws.cell(row=2, column=6).value == STATUS_IDENTIFICADO
    assert ws.cell(row=3, column=6).value == STATUS_TAC_NAO_ENCONTRADO
    assert ws.cell(row=4, column=6).value == STATUS_IMEI_INVALIDO
