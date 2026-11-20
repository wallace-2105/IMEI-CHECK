"""Tela de histórico local de consultas com controle de privacidade e exportação."""

from __future__ import annotations

from datetime import datetime
import pandas as pd
import streamlit as st

from components.styles import render_page_header, style_status_dataframe_cell
from services.database_service import (
    clear_history,
    get_history,
    is_history_enabled,
    set_history_enabled,
)
from services.export_service import export_results_to_excel
from services.imei_validator import (
    STATUS_ERRO_CONSULTA,
    STATUS_IDENTIFICADO,
    STATUS_IMEI_INVALIDO,
    STATUS_TAC_NAO_ENCONTRADO,
)


def render_history_page() -> None:
    """Renderiza histórico local, configuração de privacidade, exportação e limpeza."""
    render_page_header(
        "Histórico de Consultas",
        "Armazenado exclusivamente neste computador (SQLite local). Nenhum IMEI é enviado para fora.",
    )

    current_enabled = is_history_enabled()
    new_enabled = st.toggle(
        "Salvar histórico de consultas localmente neste computador",
        value=current_enabled,
        help="Quando desativado, novas consultas não serão gravadas no histórico local.",
    )
    if new_enabled != current_enabled:
        set_history_enabled(new_enabled)
        if new_enabled:
            st.success("Armazenamento local do histórico ativado.")
        else:
            st.info("Armazenamento local do histórico desativado. Novas consultas não serão salvas.")
        st.rerun()

    col_filter, col_search = st.columns([1.4, 2.6])
    with col_filter:
        status_filter = st.selectbox(
            "Filtrar por status",
            options=[
                "Todos",
                STATUS_IDENTIFICADO,
                STATUS_TAC_NAO_ENCONTRADO,
                STATUS_IMEI_INVALIDO,
                STATUS_ERRO_CONSULTA,
            ],
        )
    with col_search:
        search_text = st.text_input(
            "Buscar no histórico (IMEI, TAC, fabricante ou modelo)",
            placeholder="Digite parte do IMEI, TAC ou fabricante...",
        )

    records = get_history(limit=500, status_filter=status_filter, search_text=search_text)

    if not records:
        st.info("Nenhum registro encontrado no histórico com os filtros atuais.")
    else:
        df = pd.DataFrame(records)[
            ["queried_at", "imei", "tac", "fabricante", "modelo", "status", "fonte"]
        ].rename(
            columns={
                "queried_at": "Data/Hora",
                "imei": "IMEI",
                "tac": "TAC",
                "fabricante": "Fabricante",
                "modelo": "Modelo",
                "status": "Status",
                "fonte": "Fonte dos dados",
            }
        ).fillna("-")
        styled = df.style.map(style_status_dataframe_cell, subset=["Status"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        excel_bytes = export_results_to_excel(records, sheet_title="Historico IMEI CHECK")
        filename = f"imei_check_historico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        st.download_button(
            label="Exportar histórico exibido para Excel (.xlsx)",
            data=excel_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )

    st.divider()
    st.subheader("Gerenciar histórico local")
    all_records = get_history(limit=1)
    if not all_records:
        st.caption("O histórico local já está vazio.")
    else:
        if "confirm_clear_history" not in st.session_state:
            st.session_state["confirm_clear_history"] = False

        if not st.session_state["confirm_clear_history"]:
            if st.button("Apagar todo o histórico local"):
                st.session_state["confirm_clear_history"] = True
                st.rerun()
        else:
            st.warning("Tem certeza? Esta ação apagará permanentemente todo o histórico local.")
            col_c1, col_c2 = st.columns([1, 1])
            with col_c1:
                if st.button("Confirmar exclusão do histórico", type="primary"):
                    removed = clear_history()
                    st.session_state["confirm_clear_history"] = False
                    st.success(f"Histórico apagado ({removed} registro(s) removido(s)).")
                    st.rerun()
            with col_c2:
                if st.button("Cancelar"):
                    st.session_state["confirm_clear_history"] = False
                    st.rerun()
