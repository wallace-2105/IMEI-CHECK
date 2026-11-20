"""Gerenciamento da base TAC local, atualizações gratuitas e pesquisa no catálogo."""

from __future__ import annotations

import html
import pandas as pd
import streamlit as st

from components.styles import render_metric_card, render_page_header
from services.database_service import (
    SOURCE_KEY_COMMUNITY,
    SOURCE_KEY_LOCAL,
    SOURCE_KEY_OSMOCOM,
    clear_local_records,
    get_database_summary,
    search_tac_catalog,
)
from services.tac_service import (
    import_local_csv_bytes,
    update_community_database,
    update_osmocom_database,
)

TEMPLATE_CSV = (
    "tac,fabricante,modelo,detalhes\n"
    "35699357,Teltonika,RUT956,Roteador industrial LTE/M2M (exemplo)\n"
)


def _render_source_card(source: dict) -> None:
    count = source.get("record_count", 0)
    count_str = f"{count:,}".replace(",", ".")
    last_update = source.get("last_updated_at") or "Nunca"
    upstream_date = source.get("last_upstream_date") or "-"
    status = source.get("status") or "-"
    badge_color = "#10B981" if count > 0 else "#64748B"

    st.markdown(
        f"""
        <div class="imei-source-card" style="border-left: 4px solid {badge_color};">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
                <div style="font-weight:700; font-size:1.05rem; color:#F8FAFC;">
                    {html.escape(source['source_name'])}
                </div>
                <span style="font-size:0.82rem; color:#CBD5E1; background:#1E293B; padding:0.2rem 0.6rem; border-radius:999px;">
                    {count_str} TACs • {html.escape(status)}
                </span>
            </div>
            <div style="font-size:0.86rem; color:#94A3B8; margin-top:0.35rem;">
                <strong>Origem:</strong> {html.escape(source['source_url'])} &nbsp;|&nbsp;
                <strong>Licença:</strong> {html.escape(source['license_info'])}
            </div>
            <div style="font-size:0.84rem; color:#94A3B8; margin-top:0.2rem;">
                <strong>Último download/importação local:</strong> {html.escape(last_update)} &nbsp;|&nbsp;
                <strong>Registro mais recente na origem:</strong> {html.escape(upstream_date)}
            </div>
            <div style="font-size:0.83rem; color:#CBD5E1; margin-top:0.3rem;">
                {html.escape(source.get('notes') or '')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_database_page() -> None:
    """Renderiza painel de atualização da base SQLite, importação local e pesquisa offline."""
    render_page_header(
        "Banco de Dados TAC (Offline)",
        "Baixe e atualize bases públicas 100% gratuitas. Em qualquer falha de rede, a base anterior é preservada.",
    )

    summary = get_database_summary()
    last_update = summary.get("last_updated_at") or "Não baixada"

    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric_card(
            "TACs únicos offline",
            f"{summary['total_distinct_tacs']:,}".replace(",", "."),
            "Prontos para consulta sem internet",
            accent_color="#10B981" if summary["total_distinct_tacs"] > 0 else "#64748B",
        )
    with c2:
        render_metric_card(
            "Última atualização",
            last_update,
            "Horário local da última importação",
            accent_color="#3B82F6",
        )
    with c3:
        render_metric_card(
            "Tamanho do SQLite local",
            f"{summary['db_size_mb']} MB",
            "database/imei_database.db",
            accent_color="#2563EB",
        )

    st.markdown("<div style='height: 0.9rem;'></div>", unsafe_allow_html=True)
    st.subheader("Fontes de dados configuradas")

    sources_by_key = {s["source_key"]: s for s in summary["sources"]}

    if SOURCE_KEY_OSMOCOM in sources_by_key:
        _render_source_card(sources_by_key[SOURCE_KEY_OSMOCOM])
        if st.button("Atualizar Base Osmocom (Oficial — Principal)", type="primary"):
            with st.spinner("Baixando e validando Osmocom TAC Database (http://tacdb.osmocom.org/)..."):
                res = update_osmocom_database()
            if res.success:
                st.success(res.message)
                st.rerun()
            else:
                st.error(res.message)

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    if SOURCE_KEY_COMMUNITY in sources_by_key:
        _render_source_card(sources_by_key[SOURCE_KEY_COMMUNITY])
        if st.button("Baixar / Atualizar Base Complementar Gratuita (Optus V36 + IoT / Rastreadores)"):
            with st.spinner("Baixando base comunitária MIT (275 mil+ TACs, inclui rastreadores e módulos IoT)..."):
                res = update_community_database()
            if res.success:
                st.success(res.message)
                st.rerun()
            else:
                st.error(res.message)

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    if SOURCE_KEY_LOCAL in sources_by_key:
        _render_source_card(sources_by_key[SOURCE_KEY_LOCAL])
        with st.expander("Importar lista CSV interna da empresa (opcional)"):
            st.caption(
                "Ideal para cadastrar TACs de fornecedores específicos de rastreadores, módulos M2M ou "
                "equipamentos homologados internamente. Os registros locais têm prioridade na consulta."
            )
            st.download_button(
                "Baixar modelo de CSV",
                data=TEMPLATE_CSV.encode("utf-8-sig"),
                file_name="modelo_tac_interno.csv",
                mime="text/csv",
            )
            uploaded = st.file_uploader(
                "Selecione um arquivo CSV com colunas 'tac', 'fabricante' e 'modelo'",
                type=["csv"],
            )
            if uploaded is not None:
                if st.button("Importar CSV selecionado"):
                    res = import_local_csv_bytes(uploaded.getvalue(), uploaded.name)
                    if res.success:
                        st.success(res.message)
                        st.rerun()
                    else:
                        st.error(res.message)

            if sources_by_key[SOURCE_KEY_LOCAL]["record_count"] > 0:
                if st.button("Limpar registros de importação local"):
                    removed = clear_local_records()
                    st.info(f"{removed} registro(s) local(is) removido(s).")
                    st.rerun()

    st.divider()
    st.subheader("Explorar catálogo offline")
    catalog_query = st.text_input(
        "Pesquisar na base local por TAC, fabricante ou modelo",
        placeholder="Ex.: Teltonika, Quectel, Suntech, Nokia ou 35675904",
    )
    if catalog_query.strip():
        matches = search_tac_catalog(catalog_query, limit=100)
        if not matches:
            st.info("Nenhum registro encontrado na base local para o termo informado.")
        else:
            df = pd.DataFrame(matches).rename(
                columns={
                    "tac": "TAC",
                    "fabricante": "Fabricante",
                    "modelo": "Modelo",
                    "nomes_alternativos": "Nomes alternativos",
                    "detalhes": "Detalhes",
                    "origem": "Fonte",
                    "data_registro": "Data registro",
                }
            ).fillna("-")
            st.caption(f"Exibindo até 100 resultados ({len(df)} encontrado(s)).")
            st.dataframe(df, use_container_width=True, hide_index=True)
