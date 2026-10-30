"""
IT-Salary-Predictor: Database Interface Module.

Centralny moduł do zarządzania połączeniem z relacyjną bazą danych PostgreSQL.
Używany przez:
- Inżyniera Danych (ładowanie surowych ofert JSONB),
- Analityka Danych (odczyt surowych rekordów, zapis wyczyszczonej tabeli 'cleaned_offers'),
- Inżyniera ML (odczyt tabeli 'cleaned_offers' do treningu regresji),
- Backend FastAPI (odpytywanie statystyk rynkowych do dashboardu).
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Database")

# Parametry połączenia z PostgreSQL (zmienne środowiskowe lub wartości domyślne z Dockera)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "salary_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgrespassword")


def get_connection_url() -> str:
    """Zwraca sformatowany URL połączeniowy dla SQLAlchemy."""
    return f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine() -> Engine:
    """Tworzy i zwraca obiekt SQLAlchemy Engine."""
    return create_engine(get_connection_url(), pool_pre_ping=True)


def test_connection() -> bool:
    """Sprawdza, czy baza danych PostgreSQL jest osiągalna."""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1;")).scalar()
            return result == 1
    except Exception as err:
        logger.warning("Brak połączenia z PostgreSQL (%s:%d): %s", DB_HOST, DB_PORT, err)
        return False


def fetch_raw_offers_df(limit: Optional[int] = None) -> pd.DataFrame:
    """
    Pobiera surowe oferty z tabeli 'raw_offers' jako Pandas DataFrame.
    Jeśli PostgreSQL nie jest uruchomiony, automatycznie wczytuje dane z pliku
    backupu 'data/raw/offers_latest.json'.
    """
    if test_connection():
        logger.info("Odczyt surowych ofert z bazy danych PostgreSQL...")
        query = "SELECT id, portal, external_id, scraped_at, payload FROM raw_offers"
        if limit:
            query += f" LIMIT {limit}"
        
        engine = get_engine()
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            logger.info("Pobrano %d rekordów z tabeli 'raw_offers'.", len(df))
            return df
    else:
        fallback_path = os.path.join("data", "raw", "offers_latest.json")
        logger.info("PostgreSQL niedostępny. Wczytywanie z pliku lokalnego: %s...", fallback_path)
        if os.path.exists(fallback_path):
            with open(fallback_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            if limit:
                raw_data = raw_data[:limit]
            df = pd.DataFrame({
                "id": range(1, len(raw_data) + 1),
                "portal": "justjoin.it",
                "external_id": [o.get("slug") or o.get("guid") for o in raw_data],
                "scraped_at": pd.Timestamp.now(),
                "payload": raw_data
            })
            logger.info("Załadowano %d rekordów z pliku lokalnego.", len(df))
            return df
        else:
            raise FileNotFoundError(f"Nie znaleziono pliku {fallback_path} ani bazy danych!")


def save_cleaned_offers_df(df: pd.DataFrame, if_exists: str = "replace") -> int:
    """
    Zapisuje wyczyszczone i znormalizowane dane do tabeli 'cleaned_offers' w PostgreSQL.
    
    :param df: DataFrame przygotowany przez Analityka Danych.
    :param if_exists: Sposób zapisu ('replace' lub 'append').
    :return: Liczba zapisanych rekordów.
    """
    if not test_connection():
        raise ConnectionError("Nie można połączyć się z PostgreSQL. Uruchom kontener: docker compose up -d db")

    logger.info("Zapisywanie %d rekordów do tabeli 'cleaned_offers'...", len(df))
    engine = get_engine()
    
    # Zapis do PostgreSQL
    df.to_sql("cleaned_offers", con=engine, if_exists=if_exists, index=False, chunksize=1000)
    logger.info("Sukces! Tabela 'cleaned_offers' została pomyślnie zaktualizowana.")
    return len(df)


def fetch_cleaned_offers_df() -> pd.DataFrame:
    """Pobiera wyczyszczone dane z tabeli 'cleaned_offers' dla Inżyniera ML lub API."""
    if not test_connection():
        raise ConnectionError("Nie można połączyć się z PostgreSQL.")

    engine = get_engine()
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM cleaned_offers", conn)
        return df


if __name__ == "__main__":
    print("[*] Test modułu bazy danych:")
    connected = test_connection()
    print(f"    Status połączenia z PostgreSQL: {'POŁĄCZONO' if connected else 'BRAK POŁĄCZENIA'}")
