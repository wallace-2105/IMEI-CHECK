"""Menu lateral e resumo rápido do estado da base offline."""

from __future__ import annotations

from pathlib import Path
import streamlit as st

from services.database_service import get_database_summary

MENU_ITEMS = [
    "Início",
    "Consultar IMEI",
    "Consulta em lote",
    "Histórico",
    "Banco de dados",
    "Sobre o sistema",
]

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo.png"


def render_sidebar() -> str:
    """Renderiza o menu lateral de navegação e retorna a página selecionada."""
    if "pending_page" in st.session_state:
        pending = st.session_state.pop("pending_page")
        if pending in MENU_ITEMS:
            st.session_state["active_page"] = pending

    if "active_page" not in st.session_state or st.session_state["active_page"] not in MENU_ITEMS:
        st.session_state["active_page"] = "Início"

    with st.sidebar:
        col_logo, col_title = st.columns([1, 2.7], vertical_alignment="center")
        with col_logo:
            if LOGO_PATH.exists():
                st.image(str(LOGO_PATH), width=48)
        with col_title:
            st.markdown("### IMEI CHECK")
            st.caption("Telemetria • IoT • M2M")

        st.divider()

        selected = st.radio(
            "Navegação",
            options=MENU_ITEMS,
            key="active_page",
            label_visibility="collapsed",
        )

        st.divider()

        summary = get_database_summary()
        total_tacs = summary.get("total_distinct_tacs", 0)
        last_update = summary.get("last_updated_at") or "Ainda não baixada"

        if total_tacs > 0:
            st.success(f"Base offline pronta ({total_tacs:,} TACs)".replace(",", "."), icon="✅")
        else:
            st.warning("Base TAC vazia — baixe em 'Banco de dados'.", icon="⚠️")

        st.caption(f"**Última atualização:** {last_update}")
        st.caption("**Modo:** 100% local e gratuito (sem anúncios ou APIs pagas)")

    return selected
