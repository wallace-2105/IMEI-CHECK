"""Tela de consulta em lote (até 10 IMEIs simultâneos) com exportação XLSX."""

from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

from components.styles import render_metric_card, render_page_header, style_status_dataframe_cell
from services.export_service import export_results_to_excel
from services.imei_validator import (
    MAX_BATCH_IMEIS,
    STATUS_IDENTIFICADO,
    STATUS_IMEI_INVALIDO,
    STATUS_TAC_NAO_ENCONTRADO,
    parse_batch_lines,
)
from services.tac_service import IMEILookupResult, query_batch_imeis


def render_batch_search_page() -> None:
    """Renderiza a tela de consulta em lote e exportação para Excel."""
    render_page_header(
        "Consulta em Lote",
        f"Cole até {MAX_BATCH_IMEIS} IMEIs (um por linha) para validar, identificar e exportar para Excel.",
    )

    raw_batch = st.text_area(
        "Lista de IMEIs (1 por linha — máximo de 10)",
        height=190,
        placeholder="356759040000001\n352505000000001\n123456789012345",
        key="batch_imei_textarea",
    )

    accepted_lines, total_lines = parse_batch_lines(raw_batch, max_items=MAX_BATCH_IMEIS)

    col_info, col_btn = st.columns([3, 1.2], vertical_alignment="center")
    with col_info:
        if total_lines > MAX_BATCH_IMEIS:
            st.error(
                f"Foram informadas {total_lines} linhas. O limite por consulta em lote é de "
                f"{MAX_BATCH_IMEIS} IMEIs simultâneos. Remova {total_lines - MAX_BATCH_IMEIS} linha(s) para continuar."
            )
        else:
            st.caption(f"Linhas detectadas: **{total_lines} / {MAX_BATCH_IMEIS}**")
    with col_btn:
        run_batch = st.button(
            "Consultar lote",
            type="primary",
            use_container_width=True,
            disabled=(total_lines == 0 or total_lines > MAX_BATCH_IMEIS),
        )

    if run_batch:
        results = query_batch_imeis(accepted_lines, save_history=True)
        st.session_state["last_batch_results"] = results

    results: list[IMEILookupResult] | None = st.session_state.get("last_batch_results")
    if not results:
        return

    total = len(results)
    identificados = sum(1 for r in results if r.status == STATUS_IDENTIFICADO)
    nao_encontrados = sum(1 for r in results if r.status == STATUS_TAC_NAO_ENCONTRADO)
    invalidos = sum(1 for r in results if r.status == STATUS_IMEI_INVALIDO)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_metric_card("Total analisado", str(total), accent_color="#3B82F6")
    with k2:
        render_metric_card("Identificados", str(identificados), accent_color="#10B981")
    with k3:
        render_metric_card("TAC não encontrado", str(nao_encontrados), accent_color="#64748B")
    with k4:
        render_metric_card("IMEIs inválidos", str(invalidos), accent_color="#EF4444")

    st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)

    rows = [
        {
            "IMEI": r.imei_normalizado or r.imei_informado,
            "TAC": r.tac or "-",
            "Fabricante": r.fabricante or "-",
            "Modelo": r.modelo or ("Não informado na base" if r.status == STATUS_IDENTIFICADO else "-"),
            "Status": r.status,
            "Fonte dos dados": r.fonte or "-",
            "Observação": r.mensagem,
        }
        for r in results
    ]
    df = pd.DataFrame(rows)
    styled = df.style.map(style_status_dataframe_cell, subset=["Status"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    excel_bytes = export_results_to_excel(results, sheet_title="Lote IMEI CHECK")
    filename = f"imei_check_lote_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    st.download_button(
        label="Exportar resultados para Excel (.xlsx)",
        data=excel_bytes,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )
