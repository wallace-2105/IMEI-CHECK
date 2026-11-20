"""Dashboard inicial do sistema IMEI CHECK."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.styles import render_metric_card, render_page_header, style_status_dataframe_cell
from services.database_service import get_dashboard_stats


def _navigate_to(page: str) -> None:
    st.session_state["pending_page"] = page
    st.rerun()


def render_dashboard() -> None:
    """Exibe indicadores gerais, estado da base local e atalhos rápidos."""
    render_page_header(
        "Painel Inicial — IMEI CHECK",
        "Consulta local, gratuita e segura de fabricantes e modelos por código TAC.",
    )

    stats = get_dashboard_stats()
    last_update = stats["ultima_atualizacao_base"] or "Não baixada"
    total_tacs = stats["total_tacs_base"]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_metric_card(
            "Total de consultas",
            str(stats["total_consultas"]),
            "Registradas localmente",
            accent_color="#3B82F6",
        )
    with c2:
        render_metric_card(
            "IMEIs identificados",
            str(stats["identificados"]),
            "TAC localizado na base",
            accent_color="#10B981",
        )
    with c3:
        render_metric_card(
            "Não encontrados",
            str(stats["nao_encontrados"]),
            "IMEI válido sem TAC cadastrado",
            accent_color="#64748B",
        )
    with c4:
        render_metric_card(
            "IMEIs inválidos",
            str(stats["invalidos"]),
            "Erro de tamanho ou Luhn",
            accent_color="#EF4444",
        )
    with c5:
        render_metric_card(
            "Atualização da base",
            last_update.split(" ")[0] if " " in last_update else last_update,
            f"{total_tacs:,} TACs offline".replace(",", "."),
            accent_color="#2563EB",
        )

    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

    col_act1, col_act2, col_act3 = st.columns(3)
    with col_act1:
        if st.button("Consultar IMEI individual", type="primary", use_container_width=True):
            _navigate_to("Consultar IMEI")
    with col_act2:
        if st.button("Consulta em lote (até 10)", use_container_width=True):
            _navigate_to("Consulta em lote")
    with col_act3:
        if st.button("Gerenciar base de dados", use_container_width=True):
            _navigate_to("Banco de dados")

    if not stats["history_enabled"]:
        st.info(
            "O armazenamento local de histórico está desativado no momento. "
            "Você pode reativá-lo na página 'Histórico'.",
            icon="🔒",
        )

    if total_tacs == 0:
        st.warning(
            "A base de dados TAC local ainda não foi baixada. "
            "Acesse 'Banco de dados' no menu lateral para baixar a base oficial gratuita do Osmocom.",
            icon="📥",
        )

    st.subheader("Consultas recentes")
    recent = stats["recent_history"]
    if not recent:
        st.caption("Nenhuma consulta registrada no histórico local até o momento.")
    else:
        df = pd.DataFrame(recent)
        df = df.rename(
            columns={
                "queried_at": "Data/Hora",
                "imei": "IMEI",
                "tac": "TAC",
                "fabricante": "Fabricante",
                "modelo": "Modelo",
                "status": "Status",
                "fonte": "Fonte",
            }
        ).fillna("-")
        styled = df.style.map(style_status_dataframe_cell, subset=["Status"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    st.divider()
    st.caption(
        "Privacidade e confiabilidade: nenhum IMEI consultado é enviado para servidores externos. "
        "Todas as consultas ocorrem exclusivamente contra o arquivo SQLite local."
    )
