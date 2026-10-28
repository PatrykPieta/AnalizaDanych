-- Inicjalizacja schematu bazy danych IT-Salary-Predictor

CREATE TABLE IF NOT EXISTS raw_offers (
    id SERIAL PRIMARY KEY,
    portal VARCHAR(50) NOT NULL DEFAULT 'justjoin.it',
    external_id VARCHAR(255) NOT NULL,
    scraped_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL,
    CONSTRAINT uq_portal_external_id UNIQUE (portal, external_id)
);

-- Indeksy dla szybkiego wyszukiwania
CREATE INDEX IF NOT EXISTS idx_raw_offers_scraped_at ON raw_offers (scraped_at);
CREATE INDEX IF NOT EXISTS idx_raw_offers_payload_gin ON raw_offers USING gin (payload);

COMMENT ON TABLE raw_offers IS 'Surowa warstwa (Bronze/Raw) zrzutów z API JustJoin.it w formacie JSONB';
