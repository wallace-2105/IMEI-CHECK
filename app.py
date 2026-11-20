"""Aplicação principal Streamlit do sistema IMEI CHECK."""

from __future__ import annotations

from pathlib import Path
import streamlit as st

from components.about import render_about_page
from components.batch_search import render_batch_search_page
from components.dashboard import render_dashboard
from components.database_manager import render_database_page
from components.history import render_history_page
from components.search import render_search_page
from components.sidebar import render_sidebar
from components.styles import inject_custom_css
from services.database_service import initialize_database

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "logo.png"


def main() -> None:
    """Inicializa banco local, configura página e roteia o menu lateral."""
    st.set_page_config(
        page_title="IMEI CHECK",
        page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    initialize_database()
    inject_custom_css()

    selected_page = render_sidebar()

    routes = {
        "Início": render_dashboard,
        "Consultar IMEI": render_search_page,
        "Consulta em lote": render_batch_search_page,
        "Histórico": render_history_page,
        "Banco de dados": render_database_page,
        "Sobre o sistema": render_about_page,
    }
    routes[selected_page]()


if __name__ == "__main__":
    main()
