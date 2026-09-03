-- Arrivata · migración incremental
-- Datos nuevos que captura la búsqueda con IA (además de los que ya traía):
-- rango de precio, rating/reseñas de Google, estado de redes sociales, tamaño
-- de cadena, notas de menú (quesos) y un resumen corto de la IA.
-- Idempotente: ADD COLUMN IF NOT EXISTS + guards; se puede re-correr.

ALTER TABLE prospects ADD COLUMN IF NOT EXISTS price_range TEXT NOT NULL DEFAULT 'desconocido';
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS google_rating DOUBLE PRECISION;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS google_review_count INTEGER;
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS social_media_status TEXT NOT NULL DEFAULT 'sin_datos';
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS chain_size TEXT NOT NULL DEFAULT 'desconocido';
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS cheese_menu_notes TEXT NOT NULL DEFAULT '';
ALTER TABLE prospects ADD COLUMN IF NOT EXISTS ai_summary TEXT NOT NULL DEFAULT '';

-- Tag propio ($BODY$, no $$): el cuerpo tiene strings literales con '$$',
-- '$$$', '$$$$' (price_range) que si no, cerrarían el dollar-quote antes de tiempo.
DO $BODY$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'prospects_price_range_chk' AND conrelid = 'prospects'::regclass
    ) THEN
        ALTER TABLE prospects ADD CONSTRAINT prospects_price_range_chk
            CHECK (price_range IN ('$', '$$', '$$$', '$$$$', 'desconocido'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'prospects_social_media_status_chk' AND conrelid = 'prospects'::regclass
    ) THEN
        ALTER TABLE prospects ADD CONSTRAINT prospects_social_media_status_chk
            CHECK (social_media_status IN ('activa', 'inactiva', 'sin_datos'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'prospects_chain_size_chk' AND conrelid = 'prospects'::regclass
    ) THEN
        ALTER TABLE prospects ADD CONSTRAINT prospects_chain_size_chk
            CHECK (chain_size IN ('único_local', 'cadena_chica', 'cadena_grande', 'desconocido'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'prospects_google_rating_chk' AND conrelid = 'prospects'::regclass
    ) THEN
        ALTER TABLE prospects ADD CONSTRAINT prospects_google_rating_chk
            CHECK (google_rating IS NULL OR (google_rating >= 0 AND google_rating <= 5));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'prospects_google_review_count_chk' AND conrelid = 'prospects'::regclass
    ) THEN
        ALTER TABLE prospects ADD CONSTRAINT prospects_google_review_count_chk
            CHECK (google_review_count IS NULL OR google_review_count >= 0);
    END IF;
END $BODY$;
