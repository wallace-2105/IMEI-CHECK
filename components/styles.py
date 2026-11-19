"""Estilos CSS e helpers visuais padronizados para o sistema IMEI CHECK."""

from __future__ import annotations

import html
import streamlit as st

from services.imei_validator import (
    STATUS_ERRO_CONSULTA,
    STATUS_IDENTIFICADO,
    STATUS_IMEI_INVALIDO,
    STATUS_TAC_NAO_ENCONTRADO,
)

STATUS_COLORS = {
    STATUS_IDENTIFICADO: {
        "bg": "rgba(16, 185, 129, 0.14)",
        "border": "#10B981",
        "text": "#34D399",
        "pill_bg": "#065F46",
        "pill_text": "#ECFDF5",
        "icon": "✓",
    },
    STATUS_TAC_NAO_ENCONTRADO: {
        "bg": "rgba(100, 116, 139, 0.16)",
        "border": "#64748B",
        "text": "#CBD5E1",
        "pill_bg": "#334155",
        "pill_text": "#F1F5F9",
        "icon": "•",
    },
    STATUS_IMEI_INVALIDO: {
        "bg": "rgba(239, 68, 68, 0.14)",
        "border": "#EF4444",
        "text": "#F87171",
        "pill_bg": "#7F1D1D",
        "pill_text": "#FEF2F2",
        "icon": "✕",
    },
    STATUS_ERRO_CONSULTA: {
        "bg": "rgba(245, 158, 11, 0.14)",
        "border": "#F59E0B",
        "text": "#FBBF24",
        "pill_bg": "#78350F",
        "pill_text": "#FFFBEB",
        "icon": "!",
    },
}


def inject_custom_css() -> None:
    """Aplica o tema escuro profissional com identidade visual azul/verde/vermelho/cinza."""
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #0B1120;
            color: #F1F5F9;
        }
        [data-testid="stSidebar"] {
            background-color: #0F172A;
            border-right: 1px solid #1E293B;
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
            max-width: 1180px;
        }
        .imei-page-header {
            margin-bottom: 1.25rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #1E293B;
        }
        .imei-page-title {
            font-size: 1.65rem;
            font-weight: 700;
            color: #F8FAFC;
            margin: 0 0 0.25rem 0;
            letter-spacing: -0.01em;
        }
        .imei-page-subtitle {
            font-size: 0.94rem;
            color: #94A3B8;
            margin: 0;
        }
        .imei-metric-card {
            background: #111827;
            border: 1px solid #1E293B;
            border-radius: 10px;
            padding: 1rem 1.1rem;
            height: 100%;
        }
        .imei-metric-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #94A3B8;
            margin-bottom: 0.35rem;
        }
        .imei-metric-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: #F8FAFC;
            line-height: 1.2;
        }
        .imei-metric-hint {
            font-size: 0.78rem;
            color: #64748B;
            margin-top: 0.25rem;
        }
        .imei-result-card {
            border-radius: 12px;
            padding: 1.25rem 1.35rem;
            margin: 0.75rem 0 1rem 0;
        }
        .imei-status-pill {
            display: inline-block;
            padding: 0.24rem 0.75rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            margin-bottom: 0.65rem;
        }
        .imei-device-title {
            font-size: 1.45rem;
            font-weight: 700;
            color: #F8FAFC;
            margin: 0.15rem 0 0.35rem 0;
        }
        .imei-info-panel {
            background: #111827;
            border: 1px solid #1E293B;
            border-radius: 10px;
            padding: 1rem 1.2rem;
        }
        .imei-tech-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 0.85rem;
            margin-top: 0.6rem;
        }
        .imei-tech-item {
            background: #0F172A;
            border: 1px solid #1E293B;
            border-radius: 8px;
            padding: 0.65rem 0.8rem;
        }
        .imei-tech-label {
            font-size: 0.75rem;
            color: #94A3B8;
            margin-bottom: 0.18rem;
        }
        .imei-tech-value {
            font-size: 0.96rem;
            font-weight: 600;
            color: #F1F5F9;
            word-break: break-word;
        }
        .imei-source-card {
            background: #111827;
            border: 1px solid #1E293B;
            border-radius: 10px;
            padding: 1rem 1.15rem;
            margin-bottom: 0.85rem;
        }
        div[data-testid="stButton"] > button[kind="primary"] {
            background-color: #2563EB;
            border-color: #2563EB;
            color: #FFFFFF;
            font-weight: 600;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover {
            background-color: #1D4ED8;
            border-color: #1D4ED8;
        }
        div[data-testid="stFormSubmitButton"] > button {
            background-color: #2563EB;
            border-color: #2563EB;
            color: #FFFFFF;
            font-weight: 600;
        }
        div[data-testid="stFormSubmitButton"] > button:hover {
            background-color: #1D4ED8;
            border-color: #1D4ED8;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, subtitle: str) -> None:
    """Renderiza cabeçalho padronizado de página."""
    st.markdown(
        f"""
        <div class="imei-page-header">
            <div class="imei-page-title">{html.escape(title)}</div>
            <div class="imei-page-subtitle">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(
    label: str,
    value: str,
    hint: str = "",
    accent_color: str = "#3B82F6",
) -> None:
    """Renderiza um cartão de métrica com borda superior discreta."""
    hint_html = f'<div class="imei-metric-hint">{html.escape(hint)}</div>' if hint else ""
    st.markdown(
        f"""
        <div class="imei-metric-card" style="border-top: 3px solid {accent_color};">
            <div class="imei-metric-label">{html.escape(label)}</div>
            <div class="imei-metric-value">{html.escape(value)}</div>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def style_status_dataframe_cell(val: object) -> str:
    """Estilização de célula Pandas Styler para a coluna Status."""
    text = str(val)
    if text == STATUS_IDENTIFICADO:
        return "background-color: rgba(16, 185, 129, 0.20); color: #34D399; font-weight: 700;"
    if text == STATUS_IMEI_INVALIDO:
        return "background-color: rgba(239, 68, 68, 0.20); color: #F87171; font-weight: 700;"
    if text == STATUS_TAC_NAO_ENCONTRADO:
        return "background-color: rgba(100, 116, 139, 0.22); color: #CBD5E1; font-weight: 600;"
    if text == STATUS_ERRO_CONSULTA:
        return "background-color: rgba(245, 158, 11, 0.20); color: #FBBF24; font-weight: 700;"
    return ""
