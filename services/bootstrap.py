"""Script auxiliar para inicializar o SQLite local e baixar a base TAC gratuita."""

from __future__ import annotations

import argparse

from services.database_service import get_database_summary, initialize_database
from services.tac_service import update_community_database, update_osmocom_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Inicializa a base TAC local do IMEI CHECK.")
    parser.add_argument(
        "--with-community",
        action="store_true",
        help="Também baixa a base complementar gratuita (Optus V36 + IoT/Rastreadores).",
    )
    args = parser.parse_args()

    db_path = initialize_database()
    print(f"Banco SQLite inicializado em: {db_path}")

    res_osmocom = update_osmocom_database()
    print(f"[Osmocom] {res_osmocom.message}")

    if args.with_community:
        res_comm = update_community_database()
        print(f"[Base Complementar] {res_comm.message}")

    summary = get_database_summary()
    print(f"Total de TACs disponíveis offline: {summary['total_distinct_tacs']}")
    return 0 if res_osmocom.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
