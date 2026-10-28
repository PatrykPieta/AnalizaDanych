"""
IT-Salary-Predictor: Database Loader Module.

Wczytuje surowy plik JSON (data/raw/offers_latest.json) i ładuje rekordy
do tabeli 'raw_offers' w bazie PostgreSQL za pomocą operacji UPSERT (ON CONFLICT).
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("DatabaseLoader")

# Parametry połączenia (domyślnie z docker-compose.yml)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "salary_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgrespassword")


def load_json_to_postgres(json_file_path: str = "data/raw/offers_latest.json") -> int:
    """Ładuje dane z pliku JSON do bazy PostgreSQL."""
    file_path = Path(json_file_path)
    if not file_path.exists():
        logger.error("Plik %s nie istnieje! Najpierw uruchom scrapera.", file_path)
        return 0

    logger.info("Odczytywanie pliku: %s...", file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        offers: List[Dict[str, Any]] = json.load(f)

    logger.info("Załadowano z pliku %d ofert. Łączenie z PostgreSQL (%s:%d)...", len(offers), DB_HOST, DB_PORT)

    conn_str = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"
    
    try:
        with psycopg2.connect(conn_str) as conn:
            with conn.cursor() as cur:
                # Przygotowanie danych do wsadowego wstawienia
                now_utc = datetime.now(timezone.utc)
                records = []
                for offer in offers:
                    ext_id = offer.get("slug") or offer.get("guid") or str(offer.get("id"))
                    if ext_id:
                        records.append((
                            "justjoin.it",
                            ext_id,
                            now_utc,
                            json.dumps(offer, ensure_ascii=False)
                        ))

                query = """
                INSERT INTO raw_offers (portal, external_id, scraped_at, payload)
                VALUES %s
                ON CONFLICT (portal, external_id) DO UPDATE SET
                    scraped_at = EXCLUDED.scraped_at,
                    payload = EXCLUDED.payload;
                """

                execute_values(cur, query, records, page_size=1000)
                logger.info("✅ Pomyślnie załadowano %d ofert do tabeli 'raw_offers'!", len(records))
                return len(records)

    except psycopg2.OperationalError as op_err:
        logger.error(
            "Nie można połączyć się z PostgreSQL. Upewnij się, że Docker Desktop działa i wpisałeś 'docker compose up -d db'. Błąd: %s",
            op_err
        )
    except Exception as e:
        logger.error("Wystąpił nieoczekiwany błąd: %s", e)

    return 0


if __name__ == "__main__":
    load_json_to_postgres()
