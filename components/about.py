"""Página institucional e técnica sobre o sistema IMEI CHECK."""

from __future__ import annotations

import streamlit as st

from components.styles import render_page_header


def render_about_page() -> None:
    """Exibe informações técnicas, fontes gratuitas, privacidade e limitações."""
    render_page_header(
        "Sobre o Sistema — IMEI CHECK",
        "Ferramenta interna 100% gratuita, offline e sem anúncios para identificação de dispositivos por TAC.",
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
            ### Objetivo
            O **IMEI CHECK** foi desenvolvido para substituir pesquisas em sites repletos de anúncios e
            conteúdos inseguros, oferecendo uma alternativa rápida, local e gratuita para consulta de
            fabricantes e modelos de rastreadores, módulos IoT/M2M e aparelhos móveis.

            ### Garantias de Segurança e Gratuidade
            - **100% gratuito:** não utiliza APIs pagas, créditos por consulta, assinaturas ou períodos de teste.
            - **Zero anúncios e zero scraping:** não acessa sites como IMEI.info.
            - **Funcionamento offline:** após o download da base, todas as consultas rodam localmente em SQLite.
            - **Privacidade:** nenhum IMEI consultado ou histórico é enviado a servidores externos.
            - **Proteção contra falhas:** falhas no download nunca apagam a última base local válida.
            """
        )

    with col2:
        st.markdown(
            """
            ### Como funciona a identificação
            1. **Validação estrutural:** verifica se o código possui exatamente 15 dígitos numéricos.
            2. **Algoritmo de Luhn (3GPP TS 23.003):** valida o 15º dígito verificador contra erros de digitação.
            3. **Extração do TAC:** obtém os 8 primeiros dígitos (*Type Allocation Code*).
            4. **Consulta SQLite local:** busca o TAC na base armazenada em `database/imei_database.db`.

            ### Origem e Licenças das Bases Públicas
            - **Osmocom TAC Database (Principal):** [http://tacdb.osmocom.org/](http://tacdb.osmocom.org/)
              — Licença **CC-BY-SA v3.0 Unported** (22.527 TACs catalogados pela comunidade Osmocom).
            - **Base Comunitária Expandida (Complementar opcional):** [MoazEb/tac-database](https://github.com/MoazEb/tac-database)
              — Licença **MIT**, reunindo lista pública Optus V36, Osmocom e registros comunitários (incluindo módulos e rastreadores IoT).
            """
        )

    st.divider()
    st.subheader("Limitações conhecidas")
    st.markdown(
        """
        - **Cobertura da base gratuita:** nenhuma base gratuita pública contém 100% de todas as alocações comerciais da GSMA (cuja base oficial completa é paga e restrita). Para rastreadores muito novos ou lotes proprietários, é possível importar um arquivo CSV interno da empresa na aba **Banco de dados**.
        - **Escopo da consulta TAC:** um **IMEI válido** (Luhn aprovado) pode não estar cadastrado na base (**TAC não encontrado**). Validade matemática não significa identificação garantida.
        - **Status de rede:** a consulta de TAC **não** informa se o aparelho está ligado, conectado à torre, com chip M2M ativo, bloqueado ou roubado.
        - **Classificação de equipamento:** o sistema exibe exclusivamente os campos registrados na base de origem, sem inferir ou inventar categorias não documentadas.
        """
    )
