-- Script per aggiungere campo created_by alla tabella notifications
-- Esegui questo script sul database

-- Aggiungi colonna created_by (chi ha creato la notifica)
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS created_by INT DEFAULT NULL;

-- Aggiungi foreign key verso utenti
ALTER TABLE notifications ADD CONSTRAINT fk_notification_creator 
FOREIGN KEY (created_by) REFERENCES utenti(id) ON DELETE SET NULL;

-- Aggiungi indice per migliorare performance
CREATE INDEX IF NOT EXISTS idx_notification_creator ON notifications(created_by);

-- Aggiungi colonna tipo se non esiste (per categorizzare le notifiche)
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS tipo VARCHAR(20) DEFAULT 'info';

-- Verifica struttura
SHOW CREATE TABLE notifications;
