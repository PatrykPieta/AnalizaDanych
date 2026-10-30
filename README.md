# IT-Salary-Predictor: End-to-End Data & ML Pipeline

Projekt zrealizowany w ramach przedmiotu **Analiza Danych (AGH)**.  
System realizuje pełny cykl życia danych (End-to-End Data Product): od zautomatyzowanego pobierania ofert pracy z polskiego rynku IT, przez relacyjną bazę danych, czyszczenie i eksplorację (EDA), aż po trenowanie modeli uczenia maszynowego i interaktywny kalkulator stawek rynkowych.

---

## 👥 Podział Ról w Zespole

| Rola | Odpowiedzialność | Kluczowe artefakty |
| :--- | :--- | :--- |
| **Osoba 1: Inżynier Danych** | Reverse engineering API JustJoin.it, automatyzacja pobierania, wdrożenie bazy PostgreSQL w Dockerze, ładowanie danych surowych (JSONB). | `src/pipeline/scraper.py`<br>`src/pipeline/load_to_db.py`<br>`docker-compose.yml`<br>`docker/init.sql` |
| **Osoba 2: Analityk Danych** | Czyszczenie i normalizacja tech stacku oraz widełek B2B/UoP, eksploracyjna analiza danych (EDA), zasilenie tabeli analitycznej `cleaned_offers`. | `src/pipeline/cleaner.py`<br>`notebooks/01_eda_and_cleaning.ipynb` |
| **Osoba 3: Inżynier ML** | Inżynieria cech, trening modeli regresji (XGBoost, Random Forest), ewaluacja ($R^2$, RMSE, MAE), serwowanie wag modelu przez REST API (FastAPI). | `src/ml/train.py`<br>`src/backend/main.py`<br>`models/salary_model.joblib` |
| **Osoba 4: Frontend Developer** | Nowoczesny interfejs w Vue 3 + Tailwind CSS: interaktywny kalkulator wynagrodzeń kandydata oraz dashboard analityczny trendów rynkowych. | `frontend/` (Vue 3, Vite, Tailwind CSS) |

---

## 🏗️ Architektura Przepływu Danych

```text
[API JustJoin.it] ──(Scraper HTTP GET)──► [data/raw/offers_latest.json]
                                                   │
                                                   ▼ (load_to_db.py)
                                    [(DB) PostgreSQL: raw_offers] (JSONB)
                                                   │
                                                   ▼ (cleaner.py / Notebook 01)
                                    [(DB) PostgreSQL: cleaned_offers]
                                                   │
                   ┌───────────────────────────────┴───────────────────────────────┐
                   ▼                                                               ▼
       [Modelowanie ML (XGBoost)]                                       [Dashboard Analityczny]
                   │                                                               │
                   ▼                                                               ▼
        [FastAPI: /predict] ◄────────────────────────────────────────────► [Vue 3 + Tailwind UI]
```

---

## 🗄️ Schemat Relacyjnej Bazy Danych (PostgreSQL)

1. **`raw_offers`** (Warstwa Bronze / Surowa):
   - `id`: Identyfikator rekordu (SERIAL PRIMARY KEY)
   - `portal`: Nazwa portalu ogłoszeniowego (`justjoin.it`)
   - `external_id`: Unikalny identyfikator / slug ogłoszenia
   - `scraped_at`: Dokładny znacznik czasu pobrania zrzutu
   - `payload`: Kompletny obiekt ogłoszenia w formacie **JSONB** (z indeksem GIN)

2. **`cleaned_offers`** (Warstwa Silver / Analityczna):
   - `external_id`, `title`, `company_name`, `category`, `seniority`, `workplace_type`, `city`, `is_remote`, `published_at`
   - `salary_b2b_from`, `salary_b2b_to`, `salary_b2b_avg`: Stawki B2B netto w PLN/mies.
   - `salary_uop_from`, `salary_uop_to`, `salary_uop_avg`: Stawki UoP brutto w PLN/mies.
   - `target_salary_avg`: Wiodąca stawka rynkowa (zmienna celu regresji ML)
   - `skills`: Tablica znormalizowanych technologii (`TEXT[]`)

---

## 🚀 Instrukcja Uruchomienia

### 1. Klonowanie i instalacja bibliotek
```bash
git clone https://github.com/PatrykPieta/AnalizaDanych.git
cd AnalizaDanych
pip install -r requirements.txt
```

### 2. Uruchomienie bazy danych PostgreSQL (Docker)
Włącz aplikację **Docker Desktop**, a następnie w terminalu wykonaj:
```bash
docker compose up -d db
```
Baza zostanie uruchomiona na porcie `5432` z automatycznie zainicjalizowanymi tabelami z pliku `docker/init.sql`.

### 3. Pobranie najświeższych danych z rynku (Data Ingestion)
```bash
python src/pipeline/scraper.py
```
*Scraper pobiera 100% bazy JustJoin.it (~10 200 ofert) z deduplikacją i zapisuje plik `data/raw/offers_latest.json`.*

### 4. Załadowanie danych do bazy PostgreSQL
```bash
python src/pipeline/load_to_db.py
```

### 5. Czyszczenie danych i Analiza Eksploracyjna (EDA)
Otwórz notebook analityczny w Jupyter Lab / VS Code:
```bash
jupyter notebook notebooks/01_eda_and_cleaning.ipynb
```
Notebook przeprowadzi Cię przez analizę stawek, rozkładów zarobków, ranking technologii oraz zapisze wyniki do tabeli `cleaned_offers`.
