"""Serviço de consulta de IMEI/TAC e importação segura de bases públicas gratuitas."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import io
from pathlib import Path
import sqlite3
import tempfile
import uuid
import requests

from services.database_service import (
    SOURCE_COMMUNITY_NAME,
    SOURCE_KEY_COMMUNITY,
    SOURCE_KEY_OSMOCOM,
    SOURCE_OSMOCOM_NAME,
    TACRecordInput,
    add_history_entry,
    get_database_summary,
    lookup_tac,
    replace_source_records,
    upsert_local_records,
)
from services.imei_validator import (
    MAX_BATCH_IMEIS,
    STATUS_ERRO_CONSULTA,
    STATUS_IDENTIFICADO,
    STATUS_IMEI_INVALIDO,
    STATUS_TAC_NAO_ENCONTRADO,
    IMEIValidationResult,
    validate_imei,
)

# Endpoints oficiais verificados diretamente em http://tacdb.osmocom.org/
OSMOCOM_HOMEPAGE_URL = "http://tacdb.osmocom.org/"
OSMOCOM_SQLITE_URL = "http://tacdb.osmocom.org/export/tacdb.sqlite3"
OSMOCOM_CSV_URL = "http://tacdb.osmocom.org/export/tacdb.csv"
OSMOCOM_LICENSE = "CC-BY-SA v3.0 Unported (Osmocom TAC Database)"

# Fonte complementar gratuita open-source (MIT) com cobertura expandida de rastreadores/IoT
COMMUNITY_REPO_URL = "https://github.com/MoazEb/tac-database"
COMMUNITY_CSV_URL = "https://raw.githubusercontent.com/MoazEb/tac-database/main/tac_full.csv"
COMMUNITY_LICENSE = "MIT License (Optus V36 + Osmocom + contribuições comunitárias)"

MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # Limite de segurança de 100 MB por arquivo
SQLITE_MAGIC = b"SQLite format 3\x00"


@dataclass(frozen=True)
class IMEILookupResult:
    """Resultado consolidado de consulta de um IMEI."""

    queried_at: str
    imei_informado: str
    imei_normalizado: str
    tac: str | None
    snr: str | None
    digito_verificador: str | None
    fabricante: str | None
    modelo: str | None
    nomes_alternativos: str | None
    detalhes: str | None
    status: str
    fonte: str | None
    referencia_url: str | None
    contribuidor: str | None
    data_registro_base: str | None
    ultima_atualizacao_base: str | None
    mensagem: str
    todas_fontes: tuple[str, ...] = ()


@dataclass(frozen=True)
class UpdateResult:
    """Resultado de atualização ou importação de base TAC."""

    success: bool
    source_name: str
    records_imported: int
    message: str
    last_upstream_date: str | None = None


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_tac_code(raw_tac: str, allow_zero_pad: bool = False) -> str | None:
    """Normaliza código TAC para exatamente 8 dígitos numéricos ou retorna None."""
    cleaned = (raw_tac or "").strip()
    if not cleaned or not cleaned.isascii() or not cleaned.isdigit():
        return None
    if len(cleaned) == 8:
        return cleaned
    if allow_zero_pad and len(cleaned) in (6, 7):
        if cleaned == "0" * len(cleaned):
            return None
        return cleaned.zfill(8)
    return None


def _extract_model_from_specs(brand: str | None, specs: str | None) -> str | None:
    """Extrai nome de modelo legível de uma string composta sem inventar valores."""
    clean_specs = _clean_text(specs)
    if not clean_specs:
        return None

    clean_brand = (_clean_text(brand) or "").strip()
    brand_lower = clean_brand.lower()

    parts = [p.strip() for p in clean_specs.split(",") if p.strip()]
    useful_parts: list[str] = []
    for part in parts:
        part_lower = part.lower()
        if part_lower in {"n/a", "na", "none", "null", "-", "unknown"}:
            continue
        if brand_lower and part_lower == brand_lower:
            continue
        useful_parts.append(part)

    if not useful_parts:
        return None

    candidate = useful_parts[0]
    if brand_lower and candidate.lower().startswith(brand_lower + " "):
        stripped = candidate[len(clean_brand) :].strip(" -_,")
        if stripped:
            candidate = stripped

    if len(useful_parts) > 1 and candidate.lower() in {"", "n/a"}:
        candidate = useful_parts[1]

    if brand_lower and candidate.lower() == brand_lower:
        return None
    return candidate or None


def query_imei(
    raw_imei: str,
    save_history: bool = True,
    batch_id: str | None = None,
    db_path: Path | str | None = None,
) -> IMEILookupResult:
    """Executa o fluxo completo: validação, Luhn, extração do TAC e consulta SQLite."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    validation: IMEIValidationResult = validate_imei(raw_imei)

    try:
        summary = get_database_summary(db_path=db_path)
        last_update = summary.get("last_updated_at")
        total_tacs = summary.get("total_distinct_tacs", 0)
    except Exception as exc:
        return IMEILookupResult(
            queried_at=now_str,
            imei_informado=validation.original_input,
            imei_normalizado=validation.normalized_imei,
            tac=validation.tac,
            snr=validation.snr,
            digito_verificador=validation.check_digit,
            fabricante=None,
            modelo=None,
            nomes_alternativos=None,
            detalhes=None,
            status=STATUS_ERRO_CONSULTA,
            fonte=None,
            referencia_url=None,
            contribuidor=None,
            data_registro_base=None,
            ultima_atualizacao_base=None,
            mensagem=f"Erro ao acessar o banco de dados local: {exc}",
        )

    if not validation.is_valid:
        result = IMEILookupResult(
            queried_at=now_str,
            imei_informado=validation.original_input,
            imei_normalizado=validation.normalized_imei,
            tac=validation.tac,
            snr=validation.snr,
            digito_verificador=validation.check_digit,
            fabricante=None,
            modelo=None,
            nomes_alternativos=None,
            detalhes=validation.error_message,
            status=STATUS_IMEI_INVALIDO,
            fonte=None,
            referencia_url=None,
            contribuidor=None,
            data_registro_base=None,
            ultima_atualizacao_base=last_update,
            mensagem=validation.error_message or "IMEI inválido.",
        )
        if save_history:
            add_history_entry(
                imei=result.imei_normalizado or result.imei_informado,
                tac=result.tac,
                fabricante=None,
                modelo=None,
                status=result.status,
                fonte=None,
                detalhes=result.mensagem,
                batch_id=batch_id,
                queried_at=now_str,
                db_path=db_path,
            )
        return result

    assert validation.tac is not None
    try:
        record = lookup_tac(validation.tac, db_path=db_path)
    except Exception as exc:
        result = IMEILookupResult(
            queried_at=now_str,
            imei_informado=validation.original_input,
            imei_normalizado=validation.normalized_imei,
            tac=validation.tac,
            snr=validation.snr,
            digito_verificador=validation.check_digit,
            fabricante=None,
            modelo=None,
            nomes_alternativos=None,
            detalhes=str(exc),
            status=STATUS_ERRO_CONSULTA,
            fonte=None,
            referencia_url=None,
            contribuidor=None,
            data_registro_base=None,
            ultima_atualizacao_base=last_update,
            mensagem=f"Erro na consulta ao SQLite: {exc}",
        )
        if save_history:
            add_history_entry(
                imei=result.imei_normalizado,
                tac=result.tac,
                fabricante=None,
                modelo=None,
                status=result.status,
                fonte=None,
                detalhes=result.mensagem,
                batch_id=batch_id,
                queried_at=now_str,
                db_path=db_path,
            )
        return result

    if record is None:
        msg = (
            "IMEI estruturalmente válido (15 dígitos e dígito de Luhn corretos), "
            f"porém o TAC {validation.tac} não está cadastrado na base local."
            if total_tacs > 0
            else "A base TAC local está vazia. Baixe a base na aba 'Banco de dados' para identificar dispositivos."
        )
        result = IMEILookupResult(
            queried_at=now_str,
            imei_informado=validation.original_input,
            imei_normalizado=validation.normalized_imei,
            tac=validation.tac,
            snr=validation.snr,
            digito_verificador=validation.check_digit,
            fabricante=None,
            modelo=None,
            nomes_alternativos=None,
            detalhes=msg,
            status=STATUS_TAC_NAO_ENCONTRADO,
            fonte=None,
            referencia_url=None,
            contribuidor=None,
            data_registro_base=None,
            ultima_atualizacao_base=last_update,
            mensagem=msg,
        )
    else:
        fabricante = _clean_text(record.get("fabricante"))
        modelo = _clean_text(record.get("modelo"))
        fonte = _clean_text(record.get("origem"))
        msg = (
            f"Dispositivo identificado via {fonte}."
            if modelo
            else f"Fabricante identificado via {fonte}; modelo específico não informado na base."
        )
        result = IMEILookupResult(
            queried_at=now_str,
            imei_informado=validation.original_input,
            imei_normalizado=validation.normalized_imei,
            tac=validation.tac,
            snr=validation.snr,
            digito_verificador=validation.check_digit,
            fabricante=fabricante,
            modelo=modelo,
            nomes_alternativos=_clean_text(record.get("nomes_alternativos")),
            detalhes=_clean_text(record.get("detalhes")),
            status=STATUS_IDENTIFICADO,
            fonte=fonte,
            referencia_url=_clean_text(record.get("referencia_url")),
            contribuidor=_clean_text(record.get("contribuidor")),
            data_registro_base=_clean_text(record.get("data_registro")),
            ultima_atualizacao_base=last_update,
            mensagem=msg,
            todas_fontes=tuple(record.get("todas_fontes", ())),
        )

    if save_history:
        add_history_entry(
            imei=result.imei_normalizado,
            tac=result.tac,
            fabricante=result.fabricante,
            modelo=result.modelo,
            status=result.status,
            fonte=result.fonte,
            detalhes=result.detalhes,
            batch_id=batch_id,
            queried_at=now_str,
            db_path=db_path,
        )

    return result


def query_batch_imeis(
    imeis: list[str],
    save_history: bool = True,
    db_path: Path | str | None = None,
) -> list[IMEILookupResult]:
    """Consulta uma lista de até 10 IMEIs em lote."""
    if len(imeis) > MAX_BATCH_IMEIS:
        raise ValueError(f"A consulta em lote suporta no máximo {MAX_BATCH_IMEIS} IMEIs por vez.")
    batch_id = uuid.uuid4().hex[:12]
    return [
        query_imei(item, save_history=save_history, batch_id=batch_id, db_path=db_path)
        for item in imeis
    ]


def _download_to_temp_file(url: str, suffix: str, timeout: int = 45) -> Path:
    """Baixa arquivo público com limite de tamanho e verificação HTTP."""
    headers = {"User-Agent": "IMEI-CHECK/1.0 (Local Telemetry TAC Lookup)"}
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        total = 0
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Arquivo baixado excedeu o limite de segurança de 100 MB.")
                tmp.write(chunk)
        except Exception:
            tmp.close()
            tmp_path.unlink(missing_ok=True)
            raise
        tmp.close()

    if total == 0:
        tmp_path.unlink(missing_ok=True)
        raise ValueError("O servidor retornou um arquivo vazio.")
    return tmp_path


def parse_osmocom_sqlite(sqlite_file: Path) -> tuple[list[TACRecordInput], str | None]:
    """Lê e valida o arquivo tacdb.sqlite3 oficial do Osmocom em modo somente leitura."""
    with open(sqlite_file, "rb") as fh:
        magic = fh.read(len(SQLITE_MAGIC))
    if magic != SQLITE_MAGIC:
        raise ValueError("O arquivo baixado não é um banco SQLite3 válido.")

    conn = sqlite3.connect(f"file:{sqlite_file.as_posix()}?mode=ro", uri=True)
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        required_tables = {"brand", "model", "tac"}
        if not required_tables.issubset(tables):
            missing = ", ".join(sorted(required_tables - tables))
            raise ValueError(f"Estrutura SQLite inesperada do Osmocom. Tabelas ausentes: {missing}.")

        has_aka = "aka" in tables
        if has_aka:
            query = """
                SELECT
                    t.tac AS raw_tac,
                    b.name AS brand_name,
                    m.name AS model_name,
                    GROUP_CONCAT(a.name, ', ') AS aka_names,
                    t.comment AS comment_text,
                    COALESCE(m.gsmarena, m.phonearena, m.phonedb, b.gsmarena, b.phonearena, b.phonedb) AS ref_url,
                    t.contributor AS contributor_text,
                    t.date AS tac_date
                FROM tac t
                JOIN model m ON t.model = m.id
                JOIN brand b ON m.brand = b.id
                LEFT JOIN aka a ON a.model = m.id
                GROUP BY t.tac, m.id
            """
        else:
            query = """
                SELECT
                    t.tac AS raw_tac,
                    b.name AS brand_name,
                    m.name AS model_name,
                    NULL AS aka_names,
                    t.comment AS comment_text,
                    COALESCE(m.gsmarena, m.phonearena, m.phonedb, b.gsmarena, b.phonearena, b.phonedb) AS ref_url,
                    t.contributor AS contributor_text,
                    t.date AS tac_date
                FROM tac t
                JOIN model m ON t.model = m.id
                JOIN brand b ON m.brand = b.id
            """

        records: list[TACRecordInput] = []
        max_date: str | None = None
        for row in conn.execute(query):
            tac_code = _normalize_tac_code(str(row[0] or ""), allow_zero_pad=False)
            if not tac_code:
                continue
            tac_date = _clean_text(row[7])
            if tac_date and (max_date is None or tac_date > max_date):
                max_date = tac_date
            records.append(
                TACRecordInput(
                    tac=tac_code,
                    fabricante=_clean_text(row[1]),
                    modelo=_clean_text(row[2]),
                    nomes_alternativos=_clean_text(row[3]),
                    detalhes=_clean_text(row[4]),
                    referencia_url=_clean_text(row[5]),
                    contribuidor=_clean_text(row[6]),
                    data_registro=tac_date,
                )
            )
    finally:
        conn.close()

    if not records:
        raise ValueError("Nenhum TAC válido encontrado no arquivo SQLite do Osmocom.")
    return records, max_date


def parse_osmocom_csv(csv_text: str) -> list[TACRecordInput]:
    """Lê e valida o formato CSV oficial (tacdb.csv) do Osmocom TAC Database."""
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        raise ValueError("Arquivo CSV do Osmocom está vazio.")

    idx = 0
    if len(rows[0]) == 1 and "osmocom" in rows[0][0].lower():
        idx = 1

    if idx >= len(rows):
        raise ValueError("Cabeçalho do CSV do Osmocom não encontrado.")

    header = [col.strip().lower() for col in rows[idx]]
    if not header or header[0] != "tac":
        raise ValueError(f"Cabeçalho inválido para CSV do Osmocom: {rows[idx]}")

    records: list[TACRecordInput] = []
    for row in rows[idx + 1 :]:
        if not row:
            continue
        tac_code = _normalize_tac_code(row[0], allow_zero_pad=False)
        if not tac_code:
            continue
        fabricante = _clean_text(row[1]) if len(row) > 1 else None
        modelo = _clean_text(row[2]) if len(row) > 2 else None
        contribuidor = _clean_text(row[3]) if len(row) > 3 else None
        detalhes = _clean_text(row[4]) if len(row) > 4 else None
        model_url = _clean_text(row[5]) if len(row) > 5 else None
        brand_url = _clean_text(row[6]) if len(row) > 6 else None
        aka = _clean_text(row[7]) if len(row) > 7 else None

        records.append(
            TACRecordInput(
                tac=tac_code,
                fabricante=fabricante,
                modelo=modelo,
                nomes_alternativos=aka,
                detalhes=detalhes,
                referencia_url=model_url or brand_url,
                contribuidor=contribuidor,
                data_registro=None,
            )
        )

    if not records:
        raise ValueError("Nenhum registro TAC válido encontrado no CSV do Osmocom.")
    return records


def parse_community_csv(csv_text: str) -> list[TACRecordInput]:
    """Lê e valida o CSV da base comunitária gratuita (Brand, TAC, SPECS)."""
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader, None)
    if not header:
        raise ValueError("Arquivo CSV da base complementar está vazio.")

    normalized_cols = [col.strip().lower() for col in header]
    if "tac" not in normalized_cols or "brand" not in normalized_cols:
        raise ValueError(f"Cabeçalho inesperado no CSV complementar: {header}")

    brand_idx = normalized_cols.index("brand")
    tac_idx = normalized_cols.index("tac")
    specs_idx = normalized_cols.index("specs") if "specs" in normalized_cols else None

    records: list[TACRecordInput] = []
    for row in reader:
        if len(row) <= max(brand_idx, tac_idx):
            continue
        tac_code = _normalize_tac_code(row[tac_idx], allow_zero_pad=True)
        if not tac_code:
            continue
        fabricante = _clean_text(row[brand_idx])
        specs = _clean_text(row[specs_idx]) if specs_idx is not None and len(row) > specs_idx else None
        modelo = _extract_model_from_specs(fabricante, specs)
        records.append(
            TACRecordInput(
                tac=tac_code,
                fabricante=fabricante,
                modelo=modelo,
                detalhes=specs,
            )
        )

    if not records:
        raise ValueError("Nenhum registro TAC válido encontrado no CSV complementar.")
    return records


def parse_local_csv(file_bytes: bytes) -> list[TACRecordInput]:
    """Lê CSV enviado localmente pela empresa (UTF-8 ou Latin-1)."""
    text: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Não foi possível decodificar o arquivo CSV (use UTF-8 ou Latin-1).")

    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, None)
    if not header:
        raise ValueError("O arquivo CSV está vazio.")

    cols = [c.strip().lower() for c in header]

    def _find_col(candidates: tuple[str, ...]) -> int | None:
        for cand in candidates:
            if cand in cols:
                return cols.index(cand)
        return None

    tac_idx = _find_col(("tac", "codigo_tac", "código tac"))
    brand_idx = _find_col(("fabricante", "brand", "marca", "manufacturer"))
    model_idx = _find_col(("modelo", "model", "specs", "dispositivo"))
    aka_idx = _find_col(("nomes_alternativos", "aka", "alias", "apelido"))
    details_idx = _find_col(("detalhes", "observacoes", "observações", "comment", "notes"))

    if tac_idx is None:
        raise ValueError("O CSV precisa conter uma coluna chamada 'tac'.")
    if brand_idx is None and model_idx is None:
        raise ValueError("O CSV precisa conter ao menos a coluna 'fabricante' (ou 'brand') ou 'modelo'.")

    records: list[TACRecordInput] = []
    for row in reader:
        if not row or len(row) <= tac_idx:
            continue
        tac_code = _normalize_tac_code(row[tac_idx], allow_zero_pad=True)
        if not tac_code:
            continue
        fabricante = _clean_text(row[brand_idx]) if brand_idx is not None and len(row) > brand_idx else None
        raw_model = _clean_text(row[model_idx]) if model_idx is not None and len(row) > model_idx else None
        aka = _clean_text(row[aka_idx]) if aka_idx is not None and len(row) > aka_idx else None
        details = _clean_text(row[details_idx]) if details_idx is not None and len(row) > details_idx else None

        if cols[model_idx] == "specs" if model_idx is not None else False:
            modelo = _extract_model_from_specs(fabricante, raw_model)
            details = details or raw_model
        else:
            modelo = raw_model

        records.append(
            TACRecordInput(
                tac=tac_code,
                fabricante=fabricante,
                modelo=modelo,
                nomes_alternativos=aka,
                detalhes=details,
                contribuidor="Importação interna",
            )
        )

    if not records:
        raise ValueError("Nenhum TAC válido de 6 a 8 dígitos encontrado no arquivo CSV.")
    return records


def update_osmocom_database(
    db_path: Path | str | None = None,
    timeout: int = 45,
    min_expected_records: int = 1000,
) -> UpdateResult:
    """Baixa e importa a base oficial do Osmocom preservando a base atual em falhas."""
    sqlite_error: Exception | None = None
    tmp_sqlite: Path | None = None

    try:
        tmp_sqlite = _download_to_temp_file(OSMOCOM_SQLITE_URL, suffix=".sqlite3", timeout=timeout)
        records, max_date = parse_osmocom_sqlite(tmp_sqlite)
        if len(records) < min_expected_records:
            raise ValueError(
                f"Quantidade de registros abaixo do esperado ({len(records)} < {min_expected_records})."
            )
        imported = replace_source_records(
            source_key=SOURCE_KEY_OSMOCOM,
            source_name=SOURCE_OSMOCOM_NAME,
            source_url=OSMOCOM_HOMEPAGE_URL,
            license_info=OSMOCOM_LICENSE,
            records=records,
            last_upstream_date=max_date,
            notes="Importado do endpoint oficial /export/tacdb.sqlite3.",
            db_path=db_path,
        )
        return UpdateResult(
            success=True,
            source_name=SOURCE_OSMOCOM_NAME,
            records_imported=imported,
            message=f"Base Osmocom atualizada com sucesso ({imported:,} TACs importados).".replace(",", "."),
            last_upstream_date=max_date,
        )
    except Exception as exc:
        sqlite_error = exc
    finally:
        if tmp_sqlite is not None:
            tmp_sqlite.unlink(missing_ok=True)

    # Fallback oficial para /export/tacdb.csv caso o SQLite esteja temporariamente indisponível
    tmp_csv: Path | None = None
    try:
        tmp_csv = _download_to_temp_file(OSMOCOM_CSV_URL, suffix=".csv", timeout=timeout)
        csv_text = tmp_csv.read_text(encoding="utf-8", errors="replace")
        records = parse_osmocom_csv(csv_text)
        if len(records) < min_expected_records:
            raise ValueError(
                f"Quantidade de registros no CSV abaixo do esperado ({len(records)} < {min_expected_records})."
            )
        imported = replace_source_records(
            source_key=SOURCE_KEY_OSMOCOM,
            source_name=SOURCE_OSMOCOM_NAME,
            source_url=OSMOCOM_HOMEPAGE_URL,
            license_info=OSMOCOM_LICENSE,
            records=records,
            notes="Importado via fallback oficial /export/tacdb.csv.",
            db_path=db_path,
        )
        return UpdateResult(
            success=True,
            source_name=SOURCE_OSMOCOM_NAME,
            records_imported=imported,
            message=f"Base Osmocom atualizada via CSV oficial ({imported:,} TACs importados).".replace(",", "."),
        )
    except Exception as csv_exc:
        return UpdateResult(
            success=False,
            source_name=SOURCE_OSMOCOM_NAME,
            records_imported=0,
            message=(
                "Falha ao atualizar a base Osmocom. A última base local válida foi preservada. "
                f"Detalhes: SQLite ({sqlite_error}); CSV ({csv_exc})."
            ),
        )
    finally:
        if tmp_csv is not None:
            tmp_csv.unlink(missing_ok=True)


def update_community_database(
    db_path: Path | str | None = None,
    timeout: int = 60,
    min_expected_records: int = 10000,
) -> UpdateResult:
    """Baixa e importa a base comunitária gratuita (MIT / Optus V36 + IoT)."""
    tmp_csv: Path | None = None
    try:
        tmp_csv = _download_to_temp_file(COMMUNITY_CSV_URL, suffix=".csv", timeout=timeout)
        csv_text = tmp_csv.read_text(encoding="utf-8", errors="replace")
        records = parse_community_csv(csv_text)
        if len(records) < min_expected_records:
            raise ValueError(
                f"Arquivo incompleto: apenas {len(records)} registros encontrados."
            )
        imported = replace_source_records(
            source_key=SOURCE_KEY_COMMUNITY,
            source_name=SOURCE_COMMUNITY_NAME,
            source_url=COMMUNITY_REPO_URL,
            license_info=COMMUNITY_LICENSE,
            records=records,
            notes="Base comunitária gratuita importada com sucesso (Optus V36 + IoT/Rastreadores).",
            db_path=db_path,
        )
        return UpdateResult(
            success=True,
            source_name=SOURCE_COMMUNITY_NAME,
            records_imported=imported,
            message=(
                f"Base complementar atualizada com sucesso ({imported:,} TACs importados)."
            ).replace(",", "."),
        )
    except Exception as exc:
        return UpdateResult(
            success=False,
            source_name=SOURCE_COMMUNITY_NAME,
            records_imported=0,
            message=(
                "Falha ao baixar a base complementar gratuita. A base local anterior foi preservada. "
                f"Detalhes: {exc}"
            ),
        )
    finally:
        if tmp_csv is not None:
            tmp_csv.unlink(missing_ok=True)


def import_local_csv_bytes(
    file_bytes: bytes,
    filename: str,
    db_path: Path | str | None = None,
) -> UpdateResult:
    """Importa um CSV local da empresa para enriquecer a base com TACs próprios."""
    try:
        records = parse_local_csv(file_bytes)
        imported = upsert_local_records(
            records=records,
            notes=f"Última importação local: {filename}",
            db_path=db_path,
        )
        return UpdateResult(
            success=True,
            source_name="Importação Local",
            records_imported=imported,
            message=f"{imported} registro(s) TAC importado(s) do arquivo '{filename}'.",
        )
    except Exception as exc:
        return UpdateResult(
            success=False,
            source_name="Importação Local",
            records_imported=0,
            message=f"Erro ao importar arquivo CSV local: {exc}",
        )
