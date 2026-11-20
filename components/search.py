"""Tela de consulta individual de IMEI."""

from __future__ import annotations

import html
import streamlit as st

from components.styles import STATUS_COLORS, render_page_header
from services.imei_validator import STATUS_IDENTIFICADO
from services.tac_service import IMEILookupResult, query_imei


def _render_result_card(result: IMEILookupResult) -> None:
    theme = STATUS_COLORS[result.status]
    fabricante = result.fabricante or "Não identificado"
    modelo = result.modelo or ("Não informado na base" if result.status == STATUS_IDENTIFICADO else "-")

    if result.status == STATUS_IDENTIFICADO:
        headline = f"{fabricante} — {modelo}" if result.modelo else fabricante
    elif result.status == "TAC não encontrado":
        headline = f"TAC {result.tac or '-'} não cadastrado na base local"
    else:
        headline = result.mensagem

    st.markdown(
        f"""
        <div class="imei-result-card" style="background:{theme['bg']}; border:1px solid {theme['border']};">
            <span class="imei-status-pill" style="background:{theme['pill_bg']}; color:{theme['pill_text']};">
                {html.escape(theme['icon'])} {html.escape(result.status)}
            </span>
            <div class="imei-device-title">{html.escape(headline)}</div>
            <div style="color:#CBD5E1; font-size:0.94rem;">{html.escape(result.mensagem)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    luhn_label = (
        f"Válido ({result.digito_verificador})"
        if result.status != "IMEI inválido" and result.digito_verificador is not None
        else "Reprovado / Não verificado"
    )
    fonte_label = result.fonte or "N/A"
    atualizacao_label = result.ultima_atualizacao_base or "Base ainda não baixada"

    tech_items = [
        ("IMEI consultado", result.imei_normalizado or result.imei_informado or "-"),
        ("TAC (8 dígitos)", result.tac or "-"),
        ("Fabricante", result.fabricante or "-"),
        ("Modelo", result.modelo or ("Não informado na base" if result.status == STATUS_IDENTIFICADO else "-")),
        ("Situação da consulta", result.status),
        ("Fonte dos dados", fonte_label),
        ("Série (SNR — 6 dígitos)", result.snr or "-"),
        ("Dígito verificador (Luhn)", luhn_label),
        ("Última atualização da base", atualizacao_label),
    ]

    if result.nomes_alternativos:
        tech_items.append(("Nomes alternativos (AKA)", result.nomes_alternativos))
    if result.detalhes and result.status == STATUS_IDENTIFICADO:
        tech_items.append(("Especificações / Comentários", result.detalhes))
    if result.data_registro_base:
        tech_items.append(("Data do registro TAC", result.data_registro_base))
    if result.contribuidor:
        tech_items.append(("Contribuidor na base", result.contribuidor))

    grid_cards = "".join(
        f"""
        <div class="imei-tech-item">
            <div class="imei-tech-label">{html.escape(label)}</div>
            <div class="imei-tech-value">{html.escape(str(val))}</div>
        </div>
        """
        for label, val in tech_items
    )

    st.markdown(
        f"""
        <div class="imei-info-panel">
            <div style="font-weight:700; font-size:1.02rem; color:#F8FAFC; margin-bottom:0.35rem;">
                Informações técnicas do dispositivo
            </div>
            <div class="imei-tech-grid">
                {grid_cards}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if result.referencia_url and result.referencia_url.startswith(("http://", "https://")):
        st.caption(f"Referência catalogada na base: {result.referencia_url}")

    st.info(
        "Nota técnica: a consulta TAC identifica apenas o lote de fabricação associado aos 8 primeiros "
        "dígitos do IMEI. Ela não informa se o equipamento está ligado, ativo na operadora, bloqueado ou com sinal.",
        icon="ℹ️",
    )


def render_search_page() -> None:
    """Renderiza a tela de consulta individual de IMEI."""
    render_page_header(
        "Consultar IMEI",
        "Validação de 15 dígitos, verificação pelo algoritmo de Luhn e busca local pelo código TAC.",
    )

    with st.form("single_imei_form", clear_on_submit=False):
        col_input, col_btn = st.columns([4, 1.2], vertical_alignment="bottom")
        with col_input:
            raw_imei = st.text_input(
                "Número IMEI (15 dígitos)",
                placeholder="Ex.: 356759040000001",
                help="Digite ou cole o IMEI com 15 dígitos numéricos. Espaços e hífens são removidos automaticamente.",
            )
        with col_btn:
            submitted = st.form_submit_button("Consultar", use_container_width=True)

    if submitted:
        result = query_imei(raw_imei, save_history=True)
        st.session_state["last_single_result"] = result

    last_result: IMEILookupResult | None = st.session_state.get("last_single_result")
    if last_result is not None:
        _render_result_card(last_result)
    else:
        st.caption(
            "Informe um IMEI acima e clique em **Consultar** para validar o dígito verificador "
            "e identificar fabricante e modelo na base SQLite local."
        )
