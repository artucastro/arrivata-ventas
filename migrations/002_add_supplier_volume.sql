-- Arrivata · migración incremental
-- Agrega los dos campos de evaluación comercial que se cargan a mano después de
-- visitar el local, y pasa score_auto a decimal (la vara de prioridad da 0–10
-- con 1 decimal, no un entero).
-- Idempotente: ADD COLUMN IF NOT EXISTS + guards; se puede re-correr.

ALTER TABLE prospects
    ADD COLUMN IF NOT EXISTS current_supplier TEXT NOT NULL DEFAULT 'desconocido';

ALTER TABLE prospects
    ADD COLUMN IF NOT EXISTS potential_volume TEXT NOT NULL DEFAULT 'desconocido';

-- Valores permitidos (se agregan una sola vez).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'prospects_current_supplier_chk'
          AND conrelid = 'prospects'::regclass
    ) THEN
        ALTER TABLE prospects ADD CONSTRAINT prospects_current_supplier_chk
            CHECK (current_supplier IN ('ninguno', 'la_meson', 'competencia', 'desconocido'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'prospects_potential_volume_chk'
          AND conrelid = 'prospects'::regclass
    ) THEN
        ALTER TABLE prospects ADD CONSTRAINT prospects_potential_volume_chk
            CHECK (potential_volume IN ('alto', 'medio', 'bajo', 'desconocido'));
    END IF;
END $$;

-- score_auto: INTEGER -> DOUBLE PRECISION (solo si todavía es integer).
DO $$
BEGIN
    IF (
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'prospects'
          AND column_name = 'score_auto'
    ) = 'integer' THEN
        ALTER TABLE prospects ALTER COLUMN score_auto TYPE DOUBLE PRECISION;
    END IF;
END $$;

ALTER TABLE prospects ALTER COLUMN score_auto SET DEFAULT 5;
