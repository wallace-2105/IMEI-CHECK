"""Testes de banco local SQLite: histórico, privacidade, dashboard e busca offline."""

from __future__ import annotations

from pathlib import Path

from services.database_service import (
    clear_history,
    get_dashboard_stats,
    get_history,
    initialize_database,
    is_history_enabled,
    search_tac_catalog,
    set_history_enabled,
)
from services.imei_validator import calculate_luhn_check_digit
from services.tac_service import query_imei
from tests.test_tac_service import _seed_synthetic_osmocom


def _valid_imei_for_tac(tac8: str) -> str:
    prefix14 = tac8 + "654321"
    return prefix14 + calculate_luhn_check_digit(prefix14)


def test_history_toggle_and_clear(tmp_path: Path):
    db_path = tmp_path / "history.db"
    initialize_database(db_path)
    _seed_synthetic_osmocom(db_path)

    assert is_history_enabled(db_path) is True

    imei_ok = _valid_imei_for_tac("99000001")
    query_imei(imei_ok, db_path=db_path)
    assert len(get_history(db_path=db_path)) == 1

    # Desativar histórico impede novas gravações sem apagar as existentes
    set_history_enabled(False, db_path=db_path)
    assert is_history_enabled(db_path) is False
    query_imei(_valid_imei_for_tac("99999999"), db_path=db_path)
    assert len(get_history(db_path=db_path)) == 1

    # Reativar e apagar histórico
    set_history_enabled(True, db_path=db_path)
    query_imei("123", db_path=db_path)
    assert len(get_history(db_path=db_path)) == 2

    removed = clear_history(db_path=db_path)
    assert removed == 2
    assert get_history(db_path=db_path) == []


def test_dashboard_stats_and_catalog_search(tmp_path: Path):
    db_path = tmp_path / "stats.db"
    _seed_synthetic_osmocom(db_path)

    query_imei(_valid_imei_for_tac("99000001"), db_path=db_path)
    query_imei(_valid_imei_for_tac("99999999"), db_path=db_path)
    query_imei("12345", db_path=db_path)

    stats = get_dashboard_stats(db_path=db_path)
    assert stats["total_consultas"] == 3
    assert stats["identificados"] == 1
    assert stats["nao_encontrados"] == 1
    assert stats["invalidos"] == 1
    assert stats["total_tacs_base"] == 2

    catalog = search_tac_catalog("Rastreador Teste", db_path=db_path)
    assert len(catalog) == 1
    assert catalog[0]["tac"] == "99000001"
