-- ========================================
-- MIGRAZIONE PRODUZIONE: Privacy Soglie Notifiche
-- ========================================
-- Questo script rende le soglie personali per ogni utente
-- ESEGUIRE SU SERVER PRODUZIONE
-- 
-- IMPORTANTE: Fai backup prima di eseguire!
-- mysqldump -u username -p database_name > backup_pre_migration.sql
-- ========================================

-- STEP 1: Aggiungi colonna user_id a product_thresholds (se non esiste)
ALTER TABLE product_thresholds 
ADD COLUMN user_id INT NOT NULL DEFAULT 1 AFTER id;

-- STEP 2: Aggiungi indice per performance su product_thresholds
ALTER TABLE product_thresholds 
ADD INDEX idx_user_id (user_id);

-- STEP 3: Rimuovi vecchio vincolo UNIQUE su codice_prodotto
ALTER TABLE product_thresholds 
DROP INDEX unique_product;

-- STEP 4: Aggiungi nuovo vincolo UNIQUE combinato (user_id, codice_prodotto)
ALTER TABLE product_thresholds 
ADD UNIQUE KEY unique_user_product (user_id, codice_prodotto);

-- STEP 5: Aggiungi foreign key verso utenti
ALTER TABLE product_thresholds 
ADD CONSTRAINT fk_threshold_user 
FOREIGN KEY (user_id) REFERENCES utenti(id) ON DELETE CASCADE;

-- STEP 6: Aggiungi colonna user_id a notifications
ALTER TABLE notifications 
ADD COLUMN user_id INT NOT NULL DEFAULT 1 AFTER id;

-- STEP 7: Aggiungi indice per performance su notifications
ALTER TABLE notifications 
ADD INDEX idx_notification_user_id (user_id);

-- STEP 8: Aggiungi foreign key verso utenti per notifications
ALTER TABLE notifications 
ADD CONSTRAINT fk_notification_user 
FOREIGN KEY (user_id) REFERENCES utenti(id) ON DELETE CASCADE;

-- ========================================
-- VERIFICA FINALE
-- ========================================
-- Esegui questi comandi per verificare che tutto sia corretto:
-- SHOW CREATE TABLE product_thresholds;
-- SHOW CREATE TABLE notifications;
-- 
-- Dovresti vedere:
-- - Colonna user_id in entrambe le tabelle
-- - Indici idx_user_id e idx_notification_user_id
-- - Foreign keys fk_threshold_user e fk_notification_user
-- - Vincolo UNIQUE unique_user_product (user_id, codice_prodotto)
