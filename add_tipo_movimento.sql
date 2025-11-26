-- Script per aggiungere il campo tipo_movimento alla tabella movimenti
-- Questo campo permetterà di distinguere i vari tipi di movimento

-- PASSO 1: Aggiunge la colonna tipo_movimento
-- ESEGUI PRIMA QUESTA QUERY DA SOLA:
ALTER TABLE `movimenti` ADD `tipo_movimento` VARCHAR(50) DEFAULT 'TRASFERIMENTO';

-- =====================================================
-- PASSO 2: ESEGUI LE QUERY SOTTO SOLO DOPO IL PASSO 1
-- =====================================================

-- CARICO: merce entra in magazzino (nessuna partenza → IN_MAGAZZINO)
UPDATE movimenti 
SET tipo_movimento = 'CARICO'
WHERE (da_ubicazione IS NULL OR da_ubicazione = '')
  AND (a_ubicazione IS NOT NULL AND a_ubicazione != '')
  AND stato = 'IN_MAGAZZINO';

-- SCARICO: merce esce dal magazzino (da IN_MAGAZZINO → altro stato)
UPDATE movimenti 
SET tipo_movimento = 'SCARICO'
WHERE (da_ubicazione IS NOT NULL AND da_ubicazione != '')
  AND (stato IS NULL OR stato != 'IN_MAGAZZINO');

-- TRASFERIMENTO: spostamento interno tra ubicazioni (IN_MAGAZZINO → IN_MAGAZZINO)
UPDATE movimenti 
SET tipo_movimento = 'TRASFERIMENTO'
WHERE (da_ubicazione IS NOT NULL AND da_ubicazione != '')
  AND (a_ubicazione IS NOT NULL AND a_ubicazione != '')
  AND stato = 'IN_MAGAZZINO';

-- MODIFICA: questo tipo viene gestito direttamente dal codice quando si fanno modifiche manuali di giacenza
-- Non può essere identificato nei dati esistenti tramite pattern, viene inserito esplicitamente dal codice
