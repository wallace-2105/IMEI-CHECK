"""Camada de persistência local em SQLite para base TAC, histórico e configurações."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Iterable, Iterator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "database" / "imei_database.db"

SOURCE_KEY_LOCAL = "local_csv"
SOURCE_KEY_OSMOCOM = "osmocom"
SOURCE_KEY_COMMUNITY = "community_optus"

SOURCE_LOCAL_NAME = "Importação Local"
SOURCE_OSMOCOM_NAME = "Osmocom TAC Database"
SOURCE_COMMUNITY_NAME = "Base Comunitária (Optus V36 / MoazEb)"

SOURCE_PRIORITY = {
    SOURCE_LOCAL_NAME: 1,
    SOURCE_OSMOCOM_NAME: 2,
    SOURCE_COMMUNITY_NAME: 3,
}

SETTING_HISTORY_ENABLED = "history_enabled"


@dataclass(frozen=True)
class TACRecordInput:
    """Registro normalizado pronto para gravação na base local."""

    tac: str
    fabricante: str | None
    modelo: str | None
    nomes_alternativos: str | None = None
    detalhes: str | None = None
    referencia_url: str | None = None
    contribuidor: str | None = None
    data_registro: str | None = None


def resolve_db_path(db_path: Path | str | None = None) -> Path:
    """Resolve o caminho do banco SQLite garantindo que a pasta exista."""
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def get_connection(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Abre uma conexão SQLite configurada com timeout e Row factory."""
    resolved = resolve_db_path(db_path)
    conn = sqlite3.connect(str(resolved), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        yield conn
    finally:
        conn.close()


def initialize_database(db_path: Path | str | None = None) -> Path:
    """Cria as tabelas e índices necessários se ainda não existirem."""
    resolved = resolve_db_path(db_path)
    with get_connection(resolved) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tac_records (
                tac TEXT NOT NULL,
                origem TEXT NOT NULL,
                prioridade INTEGER NOT NULL DEFAULT 10,
                fabricante TEXT,
                modelo TEXT,
                nomes_alternativos TEXT,
                detalhes TEXT,
                referencia_url TEXT,
                contribuidor TEXT,
                data_registro TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tac, origem)
            );

            CREATE INDEX IF NOT EXISTS idx_tac_lookup
                ON tac_records (tac, prioridade);

            CREATE INDEX IF NOT EXISTS idx_tac_fabricante
                ON tac_records (fabricante);

            CREATE TABLE IF NOT EXISTS database_metadata (
                source_key TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                license_info TEXT NOT NULL,
                record_count INTEGER NOT NULL DEFAULT 0,
                last_updated_at TEXT,
                last_upstream_date TEXT,
                status TEXT NOT NULL DEFAULT 'Não baixada',
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS consult_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                queried_at TEXT NOT NULL,
                imei TEXT NOT NULL,
                tac TEXT,
                fabricante TEXT,
                modelo TEXT,
                status TEXT NOT NULL,
                fonte TEXT,
                detalhes TEXT,
                batch_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_history_queried_at
                ON consult_history (id DESC);

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        # Configura valores iniciais sem sobrescrever preferências existentes.
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)",
            (SETTING_HISTORY_ENABLED, "true"),
        )
        default_sources = [
            (
                SOURCE_KEY_OSMOCOM,
                SOURCE_OSMOCOM_NAME,
                "http://tacdb.osmocom.org/",
                "CC-BY-SA v3.0 Unported",
                0,
                None,
                None,
                "Não baixada",
                "Fonte oficial primária do projeto (Osmocom TAC Database).",
            ),
            (
                SOURCE_KEY_COMMUNITY,
                SOURCE_COMMUNITY_NAME,
                "https://github.com/MoazEb/tac-database",
                "MIT License (inclui Optus V36 + Osmocom + contribuições)",
                0,
                None,
                None,
                "Não baixada",
                "Fonte complementar gratuita recomendada para rastreadores e módulos IoT/M2M.",
            ),
            (
                SOURCE_KEY_LOCAL,
                SOURCE_LOCAL_NAME,
                "Arquivo CSV local",
                "Uso interno da empresa",
                0,
                None,
                None,
                "Sem registros locais",
                "Permite importar listas internas de TACs de fornecedores/rastreadores.",
            ),
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO database_metadata (
                source_key, source_name, source_url, license_info,
                record_count, last_updated_at, last_upstream_date, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            default_sources,
        )
        conn.commit()
    return resolved


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def replace_source_records(
    source_key: str,
    source_name: str,
    source_url: str,
    license_info: str,
    records: Iterable[TACRecordInput],
    last_upstream_date: str | None = None,
    notes: str | None = None,
    db_path: Path | str | None = None,
) -> int:
    """Substitui atomicamente os registros de uma fonte específica em transação SQLite.

    Se a lista estiver vazia ou houver erro durante a gravação, a transação é revertida
    e a base anterior permanece intacta.
    """
    initialize_database(db_path)
    now_str = _now_iso()
    prioridade = SOURCE_PRIORITY.get(source_name, 10)

    dedup: dict[str, TACRecordInput] = {}
    for rec in records:
        if rec.tac and len(rec.tac) == 8 and rec.tac.isdigit():
            dedup[rec.tac] = rec

    if not dedup:
        raise ValueError(f"Nenhum registro TAC válido encontrado para importar em '{source_name}'.")

    rows = [
        (
            rec.tac,
            source_name,
            prioridade,
            rec.fabricante,
            rec.modelo,
            rec.nomes_alternativos,
            rec.detalhes,
            rec.referencia_url,
            rec.contribuidor,
            rec.data_registro,
            now_str,
        )
        for rec in dedup.values()
    ]

    with get_connection(db_path) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM tac_records WHERE origem = ?", (source_name,))
            conn.executemany(
                """
                INSERT INTO tac_records (
                    tac, origem, prioridade, fabricante, modelo,
                    nomes_alternativos, detalhes, referencia_url,
                    contribuidor, data_registro, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.execute(
                """
                INSERT INTO database_metadata (
                    source_key, source_name, source_url, license_info,
                    record_count, last_updated_at, last_upstream_date, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key) DO UPDATE SET
                    source_name = excluded.source_name,
                    source_url = excluded.source_url,
                    license_info = excluded.license_info,
                    record_count = excluded.record_count,
                    last_updated_at = excluded.last_updated_at,
                    last_upstream_date = excluded.last_upstream_date,
                    status = excluded.status,
                    notes = COALESCE(excluded.notes, database_metadata.notes)
                """,
                (
                    source_key,
                    source_name,
                    source_url,
                    license_info,
                    len(rows),
                    now_str,
                    last_upstream_date,
                    "Atualizada",
                    notes,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return len(rows)


def upsert_local_records(
    records: Iterable[TACRecordInput],
    notes: str | None = None,
    db_path: Path | str | None = None,
) -> int:
    """Adiciona ou atualiza registros locais importados pela empresa."""
    initialize_database(db_path)
    now_str = _now_iso()
    dedup: dict[str, TACRecordInput] = {}
    for rec in records:
        if rec.tac and len(rec.tac) == 8 and rec.tac.isdigit():
            dedup[rec.tac] = rec

    if not dedup:
        raise ValueError("Nenhum registro TAC válido encontrado no arquivo local.")

    rows = [
        (
            rec.tac,
            SOURCE_LOCAL_NAME,
            SOURCE_PRIORITY[SOURCE_LOCAL_NAME],
            rec.fabricante,
            rec.modelo,
            rec.nomes_alternativos,
            rec.detalhes,
            rec.referencia_url,
            rec.contribuidor,
            rec.data_registro,
            now_str,
        )
        for rec in dedup.values()
    ]

    with get_connection(db_path) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                """
                INSERT INTO tac_records (
                    tac, origem, prioridade, fabricante, modelo,
                    nomes_alternativos, detalhes, referencia_url,
                    contribuidor, data_registro, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tac, origem) DO UPDATE SET
                    fabricante = excluded.fabricante,
                    modelo = excluded.modelo,
                    nomes_alternativos = excluded.nomes_alternativos,
                    detalhes = excluded.detalhes,
                    referencia_url = excluded.referencia_url,
                    contribuidor = excluded.contribuidor,
                    data_registro = excluded.data_registro,
                    updated_at = excluded.updated_at
                """,
                rows,
            )
            total_local = conn.execute(
                "SELECT COUNT(*) FROM tac_records WHERE origem = ?",
                (SOURCE_LOCAL_NAME,),
            ).fetchone()[0]
            conn.execute(
                """
                UPDATE database_metadata
                SET record_count = ?,
                    last_updated_at = ?,
                    status = 'Atualizada',
                    notes = COALESCE(?, notes)
                WHERE source_key = ?
                """,
                (total_local, now_str, notes, SOURCE_KEY_LOCAL),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return len(rows)


def clear_local_records(db_path: Path | str | None = None) -> int:
    """Remove apenas os registros adicionados por importação local da empresa."""
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM tac_records WHERE origem = ?", (SOURCE_LOCAL_NAME,))
        removed = cur.rowcount
        conn.execute(
            """
            UPDATE database_metadata
            SET record_count = 0,
                last_updated_at = NULL,
                status = 'Sem registros locais'
            WHERE source_key = ?
            """,
            (SOURCE_KEY_LOCAL,),
        )
        conn.commit()
    return removed


def lookup_tac(tac: str, db_path: Path | str | None = None) -> dict | None:
    """Busca um TAC de 8 dígitos na base local, respeitando prioridade das fontes."""
    initialize_database(db_path)
    clean_tac = tac.strip()
    if len(clean_tac) != 8 or not clean_tac.isdigit():
        return None

    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT tac, origem, prioridade, fabricante, modelo,
                   nomes_alternativos, detalhes, referencia_url,
                   contribuidor, data_registro, updated_at
            FROM tac_records
            WHERE tac = ?
            ORDER BY prioridade ASC
            """,
            (clean_tac,),
        ).fetchall()

    if not rows:
        return None

    primary = dict(rows[0])
    primary["todas_fontes"] = [row["origem"] for row in rows]
    return primary


def search_tac_catalog(
    query: str,
    limit: int = 100,
    db_path: Path | str | None = None,
) -> list[dict]:
    """Pesquisa TAC, fabricante, modelo ou apelido na base offline."""
    initialize_database(db_path)
    term = (query or "").strip()
    if not term:
        return []

    like = f"%{term}%"
    prefix = f"{term}%"
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT tac, fabricante, modelo, nomes_alternativos, detalhes, origem, data_registro
            FROM tac_records
            WHERE tac LIKE ?
               OR fabricante LIKE ?
               OR modelo LIKE ?
               OR nomes_alternativos LIKE ?
               OR detalhes LIKE ?
            ORDER BY prioridade ASC, tac ASC
            LIMIT ?
            """,
            (prefix, like, like, like, like, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_database_summary(db_path: Path | str | None = None) -> dict:
    """Retorna contagens consolidadas e metadados das fontes locais."""
    resolved = initialize_database(db_path)
    with get_connection(resolved) as conn:
        total_distinct = conn.execute(
            "SELECT COUNT(DISTINCT tac) FROM tac_records"
        ).fetchone()[0]
        total_rows = conn.execute("SELECT COUNT(*) FROM tac_records").fetchone()[0]
        sources = [
            dict(r)
            for r in conn.execute(
                """
                SELECT source_key, source_name, source_url, license_info,
                       record_count, last_updated_at, last_upstream_date, status, notes
                FROM database_metadata
                ORDER BY CASE source_key
                    WHEN 'osmocom' THEN 1
                    WHEN 'community_optus' THEN 2
                    WHEN 'local_csv' THEN 3
                    ELSE 4
                END
                """
            ).fetchall()
        ]

        latest_row = conn.execute(
            """
            SELECT MAX(last_updated_at) AS latest
            FROM database_metadata
            WHERE record_count > 0 AND last_updated_at IS NOT NULL
            """
        ).fetchone()
        latest_update = latest_row["latest"] if latest_row else None

    db_size_bytes = resolved.stat().st_size if resolved.exists() else 0
    return {
        "db_path": str(resolved),
        "db_size_mb": round(db_size_bytes / (1024 * 1024), 2),
        "total_distinct_tacs": total_distinct,
        "total_rows": total_rows,
        "last_updated_at": latest_update,
        "sources": sources,
    }


def is_history_enabled(db_path: Path | str | None = None) -> bool:
    """Indica se o armazenamento local de histórico está ativado."""
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (SETTING_HISTORY_ENABLED,),
        ).fetchone()
    return True if row is None else row["value"].lower() == "true"


def set_history_enabled(enabled: bool, db_path: Path | str | None = None) -> None:
    """Ativa ou desativa o armazenamento local do histórico de consultas."""
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (SETTING_HISTORY_ENABLED, "true" if enabled else "false"),
        )
        conn.commit()


def add_history_entry(
    imei: str,
    tac: str | None,
    fabricante: str | None,
    modelo: str | None,
    status: str,
    fonte: str | None,
    detalhes: str | None = None,
    batch_id: str | None = None,
    queried_at: str | None = None,
    db_path: Path | str | None = None,
) -> bool:
    """Grava uma consulta no histórico local caso o armazenamento esteja ativado."""
    if not is_history_enabled(db_path):
        return False

    timestamp = queried_at or _now_iso()
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO consult_history (
                queried_at, imei, tac, fabricante, modelo, status, fonte, detalhes, batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, imei, tac, fabricante, modelo, status, fonte, detalhes, batch_id),
        )
        conn.commit()
    return True


def get_history(
    limit: int = 500,
    status_filter: str | None = None,
    search_text: str | None = None,
    db_path: Path | str | None = None,
) -> list[dict]:
    """Lista consultas registradas localmente em ordem mais recente primeiro."""
    initialize_database(db_path)
    clauses: list[str] = []
    params: list[object] = []

    if status_filter and status_filter != "Todos":
        clauses.append("status = ?")
        params.append(status_filter)

    if search_text and search_text.strip():
        like = f"%{search_text.strip()}%"
        clauses.append("(imei LIKE ? OR tac LIKE ? OR fabricante LIKE ? OR modelo LIKE ?)")
        params.extend([like, like, like, like])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT id, queried_at, imei, tac, fabricante, modelo, status, fonte, detalhes, batch_id
            FROM consult_history
            {where_sql}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def clear_history(db_path: Path | str | None = None) -> int:
    """Apaga todo o histórico local de consultas."""
    initialize_database(db_path)
    with get_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM consult_history")
        conn.commit()
        return cur.rowcount


def get_dashboard_stats(db_path: Path | str | None = None) -> dict:
    """Calcula métricas resumidas do histórico local e estado da base TAC."""
    summary = get_database_summary(db_path)
    history_enabled = is_history_enabled(db_path)

    with get_connection(db_path) as conn:
        counts = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Identificado' THEN 1 ELSE 0 END) AS identificados,
                SUM(CASE WHEN status = 'TAC não encontrado' THEN 1 ELSE 0 END) AS nao_encontrados,
                SUM(CASE WHEN status = 'IMEI inválido' THEN 1 ELSE 0 END) AS invalidos,
                SUM(CASE WHEN status = 'Erro na consulta' THEN 1 ELSE 0 END) AS erros
            FROM consult_history
            """
        ).fetchone()
        recent = [
            dict(r)
            for r in conn.execute(
                """
                SELECT queried_at, imei, tac, fabricante, modelo, status, fonte
                FROM consult_history
                ORDER BY id DESC
                LIMIT 8
                """
            ).fetchall()
        ]

    return {
        "total_consultas": counts["total"] or 0,
        "identificados": counts["identificados"] or 0,
        "nao_encontrados": counts["nao_encontrados"] or 0,
        "invalidos": counts["invalidos"] or 0,
        "erros": counts["erros"] or 0,
        "ultima_atualizacao_base": summary["last_updated_at"],
        "total_tacs_base": summary["total_distinct_tacs"],
        "history_enabled": history_enabled,
        "recent_history": recent,
        "sources": summary["sources"],
    }
