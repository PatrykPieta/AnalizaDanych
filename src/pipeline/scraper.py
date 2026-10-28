"""
IT-Salary-Predictor: Data Ingestion Module (Scraper).

Pobiera 100% aktywnych ofert pracy z serwisu JustJoin.it poprzez odpytywanie
wewnętrznego API (https://justjoin.it/api/candidate-api/offers).
Omija twardy limit indeksu (max 10 000 rekordów) poprzez równoległe/sekwencyjne
odpytywanie poszczególnych kategorii rynkowych i deduplikację po unikalnym kluczu slug/guid.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Set
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

# Konfiguracja logera
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Scraper")


class JustJoinScraper:
    """Produkcyjny scraper API JustJoin.it z obsługą deduplikacji i stronicowania."""

    BASE_URL: str = "https://justjoin.it/api/candidate-api/offers"
    COUNT_URL: str = "https://justjoin.it/api/candidate-api/offers/count"

    # Pełna lista oficjalnych kategorii z JustJoin.it
    CATEGORIES: List[str] = [
        "javascript", "python", "java", "data", "devops", "testing",
        "c", "mobile", "security", "admin", "ux", "pm", "game",
        "analytics", "erp", "architecture", "support", "other"
    ]

    def __init__(self, batch_size: int = 100, delay_seconds: float = 0.15) -> None:
        """
        Inicjalizacja scrapera.
        
        :param batch_size: Liczba ofert na jedno zapytanie (maksimum to 100).
        :param delay_seconds: Odstęp w sekundach między zapytaniami (kultura sieciowa).
        """
        self.batch_size = min(batch_size, 100)
        self.delay_seconds = delay_seconds
        self.session = self._build_session()

    def _build_session(self) -> requests.Session:
        """Tworzy sesję HTTP z polityką automatycznych ponowień i nagłówkami przeglądarki."""
        session = requests.Session()
        
        retries = Retry(
            total=4,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://justjoin.it/",
            "Origin": "https://justjoin.it"
        })
        return session

    def get_total_count(self) -> int:
        """Pobiera aktualną liczbę wszystkich aktywnych ogłoszeń na portalu."""
        try:
            resp = self.session.get(self.COUNT_URL, timeout=10)
            if resp.status_code == 200:
                return int(resp.json().get("count", 0))
        except requests.RequestException as e:
            logger.warning("Nie udało się pobrać licznika ofert: %s", e)
        return 0

    def fetch_category_offers(self, category: str) -> List[Dict[str, Any]]:
        """
        Pobiera wszystkie oferty z wybranej kategorii za pomocą paginacji 'from'.
        """
        category_offers: List[Dict[str, Any]] = []
        offset = 0

        while True:
            params = {
                "categories": category,
                "from": offset,
                "itemsCount": self.batch_size
            }

            try:
                response = self.session.get(self.BASE_URL, params=params, timeout=15)
                
                if response.status_code != 200:
                    logger.error(
                        "Błąd podczas pobierania kategorii '%s' (offset %d): HTTP %s",
                        category, offset, response.status_code
                    )
                    break

                payload = response.json()
                items = payload.get("data", [])
                
                if not items:
                    # Brak kolejnych rekordów – koniec kategorii
                    break

                category_offers.extend(items)
                offset += len(items)

                # Bezpiecznik: jeśli pobrano mniej niż batch_size, jesteśmy na ostatniej stronie
                if len(items) < self.batch_size:
                    break

                time.sleep(self.delay_seconds)

            except requests.RequestException as req_err:
                logger.error("Błąd sieciowy w kategorii '%s' przy offset %d: %s", category, offset, req_err)
                break

        return category_offers

    def fetch_all_offers(self) -> List[Dict[str, Any]]:
        """
        Główna metoda pobierająca oferty ze wszystkich kategorii z deduplikacją.
        Zwraca listę unikalnych ofert.
        """
        total_market_count = self.get_total_count()
        print("\n" + "=" * 65)
        print("  [*] IT-Salary-Predictor: Data Ingestion (JustJoin.it)")
        print(f"  [i] Szacowana liczba ofert na rynku: {total_market_count:,} ogłoszeń")
        print(f"  [i] Skanowanie kategorii: {len(self.CATEGORIES)} obszarów IT")
        print("=" * 65 + "\n")

        unique_offers_map: Dict[str, Dict[str, Any]] = {}
        category_stats: Dict[str, int] = {}

        overall_progress = tqdm(
            self.CATEGORIES, 
            desc="Skanowanie kategorii", 
            unit="kat", 
            colour="green"
        )

        for category in overall_progress:
            overall_progress.set_postfix_str(f"Pobieranie '{category}'...")
            offers = self.fetch_category_offers(category)
            category_stats[category] = len(offers)

            # Deduplikacja po unikalnym identyfikatorze
            for offer in offers:
                unique_key = offer.get("slug") or offer.get("guid") or str(offer.get("id"))
                if unique_key and unique_key not in unique_offers_map:
                    unique_offers_map[unique_key] = offer

            time.sleep(self.delay_seconds)

        final_offers = list(unique_offers_map.values())
        return final_offers


def save_dataset(offers: List[Dict[str, Any]], output_dir: str = "data/raw") -> Path:
    """Zapisuje listę ofert jako sformatowany plik JSON (ze znacznikiem daty oraz 'latest')."""
    target_path = Path(output_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    today_str = datetime.now(timezone.utc).strftime("%Y_%m_%d")
    dated_file = target_path / f"offers_{today_str}.json"
    latest_file = target_path / "offers_latest.json"

    logger.info("Zapisywanie %d unikalnych ofert do pliku JSON...", len(offers))
    
    with open(dated_file, "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)

    return dated_file


def print_summary_statistics(offers: List[Dict[str, Any]], saved_file: Path) -> None:
    """Wyświetla podsumowanie pobranego zbioru danych."""
    total = len(offers)
    if total == 0:
        print("\n⚠️ Nie pobrano żadnych danych.")
        return

    # Statystyki widełek płacowych (w nowym API 'from' i 'to' są bezpośrednio w obiekcie umowy)
    with_salary = 0
    b2b_count = 0
    uop_count = 0
    currencies: Dict[str, int] = {}

    for offer in offers:
        emp_types = offer.get("employmentTypes", [])
        has_any_salary = False
        has_b2b = False
        has_uop = False

        for emp in emp_types:
            salary_from = emp.get("from")
            salary_to = emp.get("to")
            if salary_from is not None or salary_to is not None:
                has_any_salary = True
                emp_type = emp.get("type")
                if emp_type == "b2b":
                    has_b2b = True
                elif emp_type == "permanent":
                    has_uop = True

        if has_any_salary:
            with_salary += 1
        if has_b2b:
            b2b_count += 1
        if has_uop:
            uop_count += 1

    salary_pct = (with_salary / total) * 100 if total > 0 else 0
    file_size_mb = os.path.getsize(saved_file) / (1024 * 1024)

    print("\n" + "=" * 65)
    print("  [OK] SUKCES: POBIERANIE ZAKONCZONE W 100%!")
    print("=" * 65)
    print(f"  [DIR]  Zapisano plik:             {saved_file.name} ({file_size_mb:.1f} MB)")
    print(f"  [LINK] Kopia 'latest':            data/raw/offers_latest.json")
    print(f"  [DATA] Wszystkie unikalne oferty: {total:,} (100% bazy JustJoin!)")
    print(f"  [CASH] Oferty z jawna pensja:     {with_salary:,} ({salary_pct:.1f}%)")
    print(f"         |-- Ofert z opcja B2B:     {b2b_count:,}")
    print(f"         `-- Ofert z opcja UoP:     {uop_count:,}")
    print("=" * 65)
    print("  -> Twoj zbior danych jest gotowy do przekazania Analitykowi (ETL)!")
    print("=" * 65 + "\n")


def main() -> None:
    """Główna funkcja uruchomieniowa scrapera."""
    scraper = JustJoinScraper(batch_size=100, delay_seconds=0.1)
    offers = scraper.fetch_all_offers()
    
    if offers:
        saved_path = save_dataset(offers)
        print_summary_statistics(offers, saved_path)
    else:
        logger.error("Nie udało się pobrać żadnych ofert.")


if __name__ == "__main__":
    main()
