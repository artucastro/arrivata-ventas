-- Arrivata · migración incremental
-- display_score: qué número muestra la columna "Score" del dashboard para
-- ese prospecto — 'auto' (default, score_auto) o 'manual' (el ajuste a mano).
-- Puramente de presentación: NO afecta el Tier ni el orden del dashboard,
-- que siguen siempre por score_auto.
-- Idempotente: ADD COLUMN IF NOT EXISTS + guard; se puede re-correr.

ALTER TABLE prospects
    ADD COLUMN IF NOT EXISTS display_score TEXT NOT NULL DEFAULT 'auto';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'prospects_display_score_chk'
          AND conrelid = 'prospects'::regclass
    ) THEN
        ALTER TABLE prospects ADD CONSTRAINT prospects_display_score_chk
            CHECK (display_score IN ('auto', 'manual'));
    END IF;
END $$;
