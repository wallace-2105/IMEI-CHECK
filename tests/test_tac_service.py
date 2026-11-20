"""Testes de consulta individual, lote, importação, modo offline e preservação em falhas."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import requests

import pytest

from services.database_service import (
    SOURCE_KEY_OSMOCOM,
    SOURCE_OSMOCOM_NAME,
    TACRecordInput,
    initialize_database,
    replace_source_records,
)
from services.imei_validator import (
    STATUS_IDENTIFICADO,
    STATUS_IMEI_INVALIDO,
    STATUS_TAC_NAO_ENCONTRADO,
    calculate_luhn_check_digit,
)
from services.tac_service import (
    import_local_csv_bytes,
    parse_community_csv,
    parse_osmocom_csv,
    parse_osmocom_sqlite,
    query_batch_imeis,
    query_imei,
    update_osmocom_database,
)


def _valid_imei_for_tac(tac8: str, snr6: str = "123456") -> str:
    prefix14 = tac8 + snr6
    return prefix14 + calculate_luhn_check_digit(prefix14)


def _seed_synthetic_osmocom(db_path: Path) -> None:
    records = [
        TACRecordInput(
            tac="99000001",
            fabricante="Fabricante Teste Sintético A",
            modelo="Modelo Rastreador Teste X1",
            nomes_alternativos="X1-LTE",
            detalhes="Registro sintético exclusivo para testes automatizados",
            contribuidor="Pytest Fixture",
            data_registro="2026-01-01 00:00:00",
        ),
        TACRecordInput(
            tac="99000002",
            fabricante="Fabricante Teste Sintético B",
            modelo=None,
            detalhes="Marca sem modelo cadastrado",
        ),
    ]
    replace_source_records(
        source_key=SOURCE_KEY_OSMOCOM,
        source_name=SOURCE_OSMOCOM_NAME,
        source_url="http://tacdb.osmocom.org/",
        license_info="CC-BY-SA v3.0",
        records=records,
        last_upstream_date="2026-01-01 00:00:00",
        db_path=db_path,
    )


def test_query_existing_and_nonexistent_tac_offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_imei.db"
    _seed_synthetic_osmocom(db_path)

    # Garante funcionamento 100% offline bloqueando qualquer tentativa de requisição HTTP
    def _fail_if_network_called(*args, **kwargs):
        raise AssertionError("Consulta de IMEI não pode realizar chamadas de rede!")

    monkeypatch.setattr(requests, "get", _fail_if_network_called)

    # 1. TAC existente
    imei_found = _valid_imei_for_tac("99000001")
    res_found = query_imei(imei_found, db_path=db_path)
    assert res_found.status == STATUS_IDENTIFICADO
    assert res_found.tac == "99000001"
    assert res_found.fabricante == "Fabricante Teste Sintético A"
    assert res_found.modelo == "Modelo Rastreador Teste X1"
    assert res_found.fonte == SOURCE_OSMOCOM_NAME

    # 2. TAC inexistente (IMEI válido por Luhn, porém TAC ausente)
    imei_unknown = _valid_imei_for_tac("99999999")
    res_unknown = query_imei(imei_unknown, db_path=db_path)
    assert res_unknown.status == STATUS_TAC_NAO_ENCONTRADO
    assert res_unknown.tac == "99999999"
    assert res_unknown.fabricante is None
    assert res_unknown.modelo is None

    # 3. IMEI inválido (erro de Luhn)
    wrong_digit = str((int(imei_found[-1]) + 1) % 10)
    res_invalid = query_imei(imei_found[:-1] + wrong_digit, db_path=db_path)
    assert res_invalid.status == STATUS_IMEI_INVALIDO
    assert res_invalid.fabricante is None


def test_batch_query_up_to_10_imeis(tmp_path: Path):
    db_path = tmp_path / "batch.db"
    _seed_synthetic_osmocom(db_path)

    valid_found = _valid_imei_for_tac("99000001", "000001")
    valid_missing = _valid_imei_for_tac("99887766", "000002")
    invalid_len = "12345"

    results = query_batch_imeis([valid_found, valid_missing, invalid_len], db_path=db_path)
    assert len(results) == 3
    assert results[0].status == STATUS_IDENTIFICADO
    assert results[1].status == STATUS_TAC_NAO_ENCONTRADO
    assert results[2].status == STATUS_IMEI_INVALIDO

    with pytest.raises(ValueError):
        query_batch_imeis([valid_found] * 11, db_path=db_path)


def test_parse_osmocom_sqlite_normalizes_leading_space_tacs(tmp_path: Path):
    # Cria um SQLite simulando o schema exato do Osmocom tacdb.sqlite3
    src_sqlite = tmp_path / "mock_osmocom.sqlite3"
    conn = sqlite3.connect(src_sqlite)
    conn.executescript(
        """
        CREATE TABLE brand (id INTEGER PRIMARY KEY, name TEXT, gsmarena TEXT, phonearena TEXT, phonedb TEXT);
        CREATE TABLE model (id INTEGER PRIMARY KEY, brand INTEGER, name TEXT, gsmarena TEXT, phonearena TEXT, phonedb TEXT);
        CREATE TABLE aka (model INTEGER, name TEXT);
        CREATE TABLE tac (tac TEXT, model INTEGER, date DATETIME, contributor TEXT, comment TEXT);
        INSERT INTO brand VALUES (1, 'Fabricante Teste Osmocom', NULL, NULL, NULL);
        INSERT INTO model VALUES (10, 1, 'Modelo Teste Osmocom', NULL, NULL, NULL);
        INSERT INTO aka VALUES (10, 'Alias Teste');
        INSERT INTO tac VALUES (' 99000003', 10, '2026-01-10 12:00:00', 'Teste', 'Com espaço à esquerda');
        """
    )
    conn.commit()
    conn.close()

    records, max_date = parse_osmocom_sqlite(src_sqlite)
    assert len(records) == 1
    assert records[0].tac == "99000003"
    assert records[0].fabricante == "Fabricante Teste Osmocom"
    assert records[0].modelo == "Modelo Teste Osmocom"
    assert records[0].nomes_alternativos == "Alias Teste"
    assert max_date == "2026-01-10 12:00:00"


def test_parse_osmocom_csv_and_community_csv():
    osmocom_csv = (
        "Osmocom TAC database under CC-BY-SA v3.0 (c) Harald Welte 2016\n"
        "tac,name,name,contributor,comment,gsmarena,gsmarena,aka\n"
        " 99000004,Marca Teste CSV,Modelo CSV,Contribuidor Teste,,,,\"Alias 1,Alias 2\"\n"
    )
    parsed_osmocom = parse_osmocom_csv(osmocom_csv)
    assert len(parsed_osmocom) == 1
    assert parsed_osmocom[0].tac == "99000004"
    assert parsed_osmocom[0].fabricante == "Marca Teste CSV"
    assert parsed_osmocom[0].modelo == "Modelo CSV"

    community_csv = (
        "Brand,TAC,SPECS\n"
        "OLD_PHONES,,\n"
        "MOTOROLA,0,\"N/A, N/A\"\n"
        "MARCA TESTE,1419200,\"MARCA TESTE, MARCA TESTE M100\"\n"
        "MARCA SEM MODELO,99000005,\"MARCA SEM MODELO, MARCA SEM MODELO\"\n"
    )
    parsed_comm = parse_community_csv(community_csv)
    assert len(parsed_comm) == 2
    assert parsed_comm[0].tac == "01419200"
    assert parsed_comm[0].modelo == "M100"
    assert parsed_comm[1].tac == "99000005"
    assert parsed_comm[1].modelo is None


def test_update_failure_preserves_existing_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "preserve.db"
    _seed_synthetic_osmocom(db_path)

    # Simula falha de conexão nos endpoints de atualização
    def _failing_get(*args, **kwargs):
        raise requests.ConnectionError("Sem conexão com a internet (simulado)")

    monkeypatch.setattr(requests, "get", _failing_get)

    update_res = update_osmocom_database(db_path=db_path)
    assert update_res.success is False
    assert "preservada" in update_res.message.lower()

    # Garante que a base anterior permanece íntegra e consultável
    imei_found = _valid_imei_for_tac("99000001")
    lookup_res = query_imei(imei_found, db_path=db_path)
    assert lookup_res.status == STATUS_IDENTIFICADO
    assert lookup_res.fabricante == "Fabricante Teste Sintético A"


def test_local_csv_import_overrides_priority_safely(tmp_path: Path):
    db_path = tmp_path / "local_override.db"
    _seed_synthetic_osmocom(db_path)

    csv_bytes = (
        "tac,fabricante,modelo,detalhes\n"
        "99000001,Fabricante Interno Teste,Rastreador Homologado H1,Lista interna\n"
    ).encode("utf-8")

    res = import_local_csv_bytes(csv_bytes, "interno.csv", db_path=db_path)
    assert res.success is True
    assert res.records_imported == 1

    lookup_res = query_imei(_valid_imei_for_tac("99000001"), db_path=db_path)
    assert lookup_res.status == STATUS_IDENTIFICADO
    assert lookup_res.fabricante == "Fabricante Interno Teste"
    assert lookup_res.modelo == "Rastreador Homologado H1"
    assert lookup_res.fonte == "Importação Local"


def test_no_paid_apis_or_forbidden_scraping_in_codebase():
    project_root = Path(__file__).resolve().parent.parent
    req_text = (project_root / "requirements.txt").read_text(encoding="utf-8").lower()
    forbidden_tokens = ["rapidapi", "stripe", "api_key", "apikey", "bearer "]
    forbidden_urls = ["http://imei.info", "https://imei.info", "http://www.imei.info", "https://www.imei.info"]

    for pkg_forbidden in ["selenium", "playwright", "beautifulsoup4", "scrapy", "openai"]:
        assert pkg_forbidden not in req_text

    for py_file in project_root.rglob("*.py"):
        if ".venv" in py_file.parts or "tests" in py_file.parts:
            continue
        content = py_file.read_text(encoding="utf-8").lower()
        for url in forbidden_urls:
            assert url not in content, f"URL proibida '{url}' encontrada em {py_file}"
        for token in forbidden_tokens:
            assert token not in content, f"Token proibido '{token}' encontrado em {py_file}"
        if "services" in py_file.parts:
            assert "imei.info" not in content, f"Referência a imei.info encontrada em serviço {py_file}"
