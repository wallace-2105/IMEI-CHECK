"""Testes integrados da interface Streamlit (AppTest) para todas as páginas."""

from __future__ import annotations

from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

import services.database_service as database_service
from services.imei_validator import calculate_luhn_check_digit
from tests.test_tac_service import _seed_synthetic_osmocom


def _valid_imei(tac8: str) -> str:
    prefix14 = tac8 + "112233"
    return prefix14 + calculate_luhn_check_digit(prefix14)


def test_streamlit_navigation_and_single_and_batch_queries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    tmp_db = tmp_path / "ui_test.db"
    monkeypatch.setattr(database_service, "DEFAULT_DB_PATH", tmp_db)
    _seed_synthetic_osmocom(tmp_db)

    app_file = Path(__file__).resolve().parent.parent / "app.py"
    at = AppTest.from_file(app_file, default_timeout=15)
    at.run()
    assert not at.exception

    # Navega para todas as páginas do menu lateral sem erros
    for page in [
        "Consultar IMEI",
        "Consulta em lote",
        "Histórico",
        "Banco de dados",
        "Sobre o sistema",
        "Início",
    ]:
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, f"Erro ao renderizar página '{page}': {at.exception}"

    # Executa consulta individual real na interface (inputs dentro de st.form são enviados no clique do submit)
    at.sidebar.radio[0].set_value("Consultar IMEI").run()
    at.text_input[0].input(_valid_imei("99000001"))
    at.button[0].click().run()
    assert not at.exception
    rendered_html = " ".join(m.value for m in at.markdown)
    assert "Fabricante Teste Sintético A" in rendered_html
    assert "Modelo Rastreador Teste X1" in rendered_html

    # Executa consulta em lote na interface
    at.sidebar.radio[0].set_value("Consulta em lote").run()
    batch_input = f"{_valid_imei('99000001')}\n{_valid_imei('99999999')}\n12345"
    at.text_area[0].input(batch_input).run()
    at.button[0].click().run()
    assert not at.exception
    assert len(at.dataframe) >= 1

    # Verifica que o histórico registrou as consultas e exibe na tela Histórico
    at.sidebar.radio[0].set_value("Histórico").run()
    assert not at.exception
    assert len(at.dataframe) >= 1

    # Verifica busca no catálogo offline em Banco de dados
    at.sidebar.radio[0].set_value("Banco de dados").run()
    at.text_input[0].input("Rastreador Teste").run()
    assert not at.exception
    assert len(at.dataframe) >= 1
