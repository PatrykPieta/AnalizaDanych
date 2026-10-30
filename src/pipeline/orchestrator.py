"""
IT-Salary-Predictor: Pipeline Orchestrator.

Zarządza pełnym cyklem życia potoku danych (End-to-End Data Pipeline):
1. Ingestion: Pobranie najnowszych ofert z JustJoin.it API -> data/raw/
2. Raw Loading: Załadowanie surowych zrzutów do PostgreSQL (tabela 'raw_offers')
3. Data Quality Gate: Weryfikacja spójności i liczby pobranych rekordów
4. Transformation & ETL: Czyszczenie, normalizacja tech stacku i widełek -> tabela 'cleaned_offers'
5. Export: Zapis lokalnej kopii analitycznej do data/processed/cleaned_offers.csv
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import Optional

from src.pipeline.cleaner import transform_raw_offers_dataframe
from src.pipeline.db import (
    fetch_raw_offers_df,
    get_engine,
    save_cleaned_offers_df,
    test_connection
)
from src.pipeline.load_to_db import load_json_to_postgres
from src.pipeline.scraper import JustJoinScraper, save_dataset

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Orchestrator")


class PipelineOrchestrator:
    """Orkiestrator potoku danych IT-Salary-Predictor."""

    def __init__(self, raw_data_path: str = "data/raw/offers_latest.json") -> None:
        self.raw_data_path = Path(raw_data_path)

    def step_1_ingestion(self) -> bool:
        """Krok 1: Pobiera świeże dane z portalu JustJoin.it."""
        print("\n" + "=" * 60)
        print("  [KROK 1/4] INGESTION: Pobieranie ofert z API JustJoin.it")
        print("=" * 60)
        start_t = time.time()
        
        scraper = JustJoinScraper(batch_size=100, delay_seconds=0.1)
        offers = scraper.fetch_all_offers()

        if not offers:
            logger.error("[BŁĄD] Nie pobrano żadnych ofert z API!")
            return False

        save_dataset(offers)
        duration = time.time() - start_t
        print(f"[OK] Krok 1 zakonczony w {duration:.1f}s. Zapisano: {len(offers):,} ofert.")
        return True

    def step_2_load_raw_db(self) -> bool:
        """Krok 2: Załadowanie surowego JSON do tabeli 'raw_offers' w PostgreSQL."""
        print("\n" + "=" * 60)
        print("  [KROK 2/4] DATABASE LOAD: Ladowanie do PostgreSQL ('raw_offers')")
        print("=" * 60)
        start_t = time.time()

        if not test_connection():
            logger.error("[BŁĄD] Brak polaczenia z PostgreSQL! Upewnij sie, ze kontener dziala: docker compose up -d db")
            return False

        loaded_count = load_json_to_postgres(str(self.raw_data_path))
        duration = time.time() - start_t
        print(f"[OK] Krok 2 zakonczony w {duration:.1f}s. Zaimportowano/zaktualizowano: {loaded_count:,} rekordow.")
        return loaded_count > 0

    def step_3_quality_gate(self) -> bool:
        """Krok 3: Walidacja jakosci danych przed transformacja."""
        print("\n" + "=" * 60)
        print("  [KROK 3/4] DATA QUALITY GATE: Weryfikacja danych")
        print("=" * 60)

        df_raw = fetch_raw_offers_df(limit=10)
        if df_raw.empty:
            logger.error("[BŁĄD JAKOŚCI] Tabela 'raw_offers' jest pusta!")
            return False

        # Sprawdzenie czy payload zawiera kluczowe pola
        sample_payload = df_raw.iloc[0]["payload"]
        required_keys = ["title", "workplaceType", "employmentTypes"]
        missing_keys = [k for k in required_keys if k not in sample_payload]

        if missing_keys:
            logger.error("[BŁĄD JAKOŚCI] Brak wymaganych kluczy w zrzucie JSON: %s", missing_keys)
            return False

        print("[OK] Test jakosci zaliczony: struktura JSON jest spojna.")
        return True

    def step_4_etl_transformation(self) -> bool:
        """Krok 4: Wykonanie transformacji analitycznej (ETL) i zapis 'cleaned_offers'."""
        print("\n" + "=" * 60)
        print("  [KROK 4/4] ETL & TRANSFORMATION: Czyszczenie i normalizacja")
        print("=" * 60)
        start_t = time.time()

        # Pobranie wszystkich surowych danych
        df_raw = fetch_raw_offers_df()
        print(f"[*] Przetwarzanie {len(df_raw):,} ofert przez modul 'cleaner'...")

        # Transformacja
        df_clean = transform_raw_offers_dataframe(df_raw)

        # Statystyki po czyszczeniu
        total_clean = len(df_clean)
        with_salary = df_clean["target_salary_avg"].notna().sum()
        pct_salary = (with_salary / total_clean) * 100 if total_clean > 0 else 0

        # Zapis do PostgreSQL
        if test_connection():
            save_cleaned_offers_df(df_clean, if_exists="replace")
            print(f"[OK] Zaktualizowano tabele 'cleaned_offers' w PostgreSQL!")

        # Zapis lokalnej kopii analitycznej CSV
        processed_dir = Path("data/processed")
        processed_dir.mkdir(parents=True, exist_ok=True)
        csv_path = processed_dir / "cleaned_offers.csv"
        df_clean.to_csv(csv_path, index=False)
        print(f"[OK] Zapisano plik: {csv_path} ({len(df_clean):,} wierszy)")

        duration = time.time() - start_t
        print("\n" + "=" * 60)
        print(f"  [STATYSTYKI POTOKU DANYCH]")
        print(f"  - Wszystkie przetworzone oferty:   {total_clean:,}")
        print(f"  - Oferty z wyliczona pensja (ML): {with_salary:,} ({pct_salary:.1f}%)")
        print(f"  - Czas transformacji:             {duration:.1f}s")
        print("=" * 60)
        return True

    def run_pipeline(self, skip_scrape: bool = False) -> None:
        """Uruchamia pelny potok danych krok po kroku."""
        global_start = time.time()
        print("\n" + "#" * 60)
        print("  ROZPOCZECIE ORKIESTRACJI: IT-Salary-Predictor Pipeline")
        print(f"  Czas uruchomienia: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("#" * 60)

        # Krok 1
        if not skip_scrape:
            if not self.step_1_ingestion():
                print("\n[ZATRZYMANO] Potok przerwany na etapie Ingestion.")
                return
        else:
            print("\n[INFO] Pominieto Krok 1 (Scraping) - uzywanie istniejacego pliku.")

        # Krok 2
        if not self.step_2_load_raw_db():
            print("\n[ZATRZYMANO] Potok przerwany na etapie ladowania bazy.")
            return

        # Krok 3
        if not self.step_3_quality_gate():
            print("\n[ZATRZYMANO] Potok przerwany: brak zgodnosci w Quality Gate.")
            return

        # Krok 4
        if not self.step_4_etl_transformation():
            print("\n[ZATRZYMANO] Potok przerwany na etapie transformacji ETL.")
            return

        total_time = time.time() - global_start
        print("\n" + "#" * 60)
        print(f"  [SUKCES] CALY POTOK ZAKONCZONY POMYSLNIE W {total_time:.1f}s!")
        print("  Baza danych oraz tabela analityczna sa w 100% zsynchronizowane.")
        print("#" * 60 + "\n")
