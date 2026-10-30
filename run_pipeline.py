"""
IT-Salary-Predictor: Główny skrypt uruchomieniowy potoku danych (CLI).

Użycie:
    python run_pipeline.py                 # Pełny potok: pobranie z API -> baza -> ETL
    python run_pipeline.py --skip-scrape   # Pomija pobieranie z sieci, wykonuje bazę i ETL na istniejącym pliku
"""

import argparse
import sys
from pathlib import Path

# Dodanie katalogu głównego do ścieżki Pythona
sys.path.append(str(Path(__file__).parent))

from src.pipeline.orchestrator import PipelineOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IT-Salary-Predictor: End-to-End Pipeline Orchestrator."
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Pomiń ponowne odpytywanie API i użyj istniejącego pliku data/raw/offers_latest.json"
    )
    args = parser.parse_args()

    orchestrator = PipelineOrchestrator()
    orchestrator.run_pipeline(skip_scrape=args.skip_scrape)


if __name__ == "__main__":
    main()
