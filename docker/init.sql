-- Inicjalizacja schematu bazy danych IT-Salary-Predictor (PostgreSQL)

-- 1. Warstwa Surowa (Bronze / Raw)
CREATE TABLE IF NOT EXISTS raw_offers (
    id SERIAL PRIMARY KEY,
    portal VARCHAR(50) NOT NULL DEFAULT 'justjoin.it',
    external_id VARCHAR(255) NOT NULL,
    scraped_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL,
    CONSTRAINT uq_portal_external_id UNIQUE (portal, external_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_offers_scraped_at ON raw_offers (scraped_at);
CREATE INDEX IF NOT EXISTS idx_raw_offers_payload_gin ON raw_offers USING gin (payload);

COMMENT ON TABLE raw_offers IS 'Surowa warstwa (Bronze/Raw) zrzutów z API JustJoin.it w formacie JSONB';

-- 2. Warstwa Analityczna (Silver / Cleaned) - zasilana przez Analityka Danych (ETL)
CREATE TABLE IF NOT EXISTS cleaned_offers (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    company_name VARCHAR(255),
    category VARCHAR(50) NOT NULL,
    seniority VARCHAR(50) NOT NULL,
    workplace_type VARCHAR(50) NOT NULL,
    city VARCHAR(100),
    is_remote BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMP WITH TIME ZONE,
    
    -- Widełki płacowe (przeliczone do kwot miesięcznych w PLN)
    salary_b2b_from NUMERIC(10, 2),
    salary_b2b_to NUMERIC(10, 2),
    salary_b2b_avg NUMERIC(10, 2),
    
    salary_uop_from NUMERIC(10, 2),
    salary_uop_to NUMERIC(10, 2),
    salary_uop_avg NUMERIC(10, 2),
    
    -- Główna stawka do modelowania ML
    target_salary_avg NUMERIC(10, 2),
    primary_contract_type VARCHAR(20),
    
    -- Znormalizowany stos technologiczny
    skills TEXT[],
    skills_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cleaned_category ON cleaned_offers (category);
CREATE INDEX IF NOT EXISTS idx_cleaned_seniority ON cleaned_offers (seniority);
CREATE INDEX IF NOT EXISTS idx_cleaned_target_salary ON cleaned_offers (target_salary_avg);

COMMENT ON TABLE cleaned_offers IS 'Wyczyszczona tabela analityczna przygotowana przez Analityka (ETL) do zasilenia modelu ML i dashboardu';
