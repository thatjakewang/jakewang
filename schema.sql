-- Reference DDL for the main-api database (PostgreSQL).
-- Rebuild an empty database with:  psql "$DATABASE_URL" -f schema.sql
--
-- Generated from pg_dump --schema-only on 2026-07-10 (odometer_readings DDL
-- taken from the applied add_odometer_readings migration, see git history).
-- Keep this file in sync whenever a migration changes the schema.
--
-- Notes:
-- - Required fields are NOT NULL and numeric measurements must be non-negative,
--   matching the validation performed by the API.
-- - created_at is not read by the API (kept for auditing); the dashboard's
--   recent-record queries order by the record's date column + id instead.

CREATE TABLE IF NOT EXISTS charging_records (
    id SERIAL PRIMARY KEY,
    charge_date date NOT NULL,
    provider text NOT NULL CHECK (char_length(provider) BETWEEN 1 AND 100),
    amount bigint NOT NULL CHECK (amount >= 0),
    kwh double precision NOT NULL CHECK (kwh >= 0),
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS car_expenses (
    id SERIAL PRIMARY KEY,
    date date NOT NULL,
    item text NOT NULL CHECK (char_length(item) BETWEEN 1 AND 100),
    amount bigint NOT NULL CHECK (amount >= 0),
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS odometer_readings (
    id SERIAL PRIMARY KEY,
    reading_km integer NOT NULL CHECK (reading_km >= 0),
    reading_date date NOT NULL,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP
);
