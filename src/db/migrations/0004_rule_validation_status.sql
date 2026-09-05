ALTER TABLE quality_rules ADD COLUMN IF NOT EXISTS validation_status VARCHAR;
ALTER TABLE quality_rules ADD COLUMN IF NOT EXISTS validation_reasons VARCHAR;
