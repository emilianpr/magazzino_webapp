# Fix Privacy Soglie Notifiche - Riepilogo Modifiche

## Problema
Le soglie di notifica erano globali e visibili a tutti gli utenti. Ogni utente poteva vedere e modificare le soglie di tutti.

## Soluzione Implementata
Reso le soglie personali per ogni utente. Ogni utente può ora:
- Impostare solo le proprie soglie
- Vedere solo le proprie soglie
- Modificare/eliminare solo le proprie soglie
- Ricevere notifiche solo per le proprie soglie

## Modifiche al Database

### File: `add_user_to_thresholds.sql` (NUOVO)
Script di migrazione che aggiunge:
1. Campo `user_id` alla tabella `product_thresholds`
2. Foreign key verso la tabella `users` con `ON DELETE CASCADE`
3. Indici per migliorare le performance
4. Vincolo UNIQUE su `(user_id, codice_prodotto)` - ogni utente può avere una sola soglia per prodotto
5. Campo `user_id` alla tabella `notifications` con foreign key e indici

**IMPORTANTE**: Prima di eseguire lo script, modifica il valore `1` nelle UPDATE con l'ID del tuo utente amministratore se diverso da 1.

## Modifiche al Codice (app.py)

### 1. `/api/soglie_data` (linee ~698-735)
- Aggiunto filtro `WHERE pt.user_id = %s` per recuperare solo le soglie dell'utente corrente

### 2. `/gestione_soglie` (linee ~740-781)
- Aggiunto filtro `WHERE pt.user_id = %s` per mostrare solo le soglie dell'utente corrente

### 3. `/add_threshold` (linee ~783-832)
- Aggiunto campo `user_id` nell'INSERT con valore `session['user_id']`
- Ora ogni nuova soglia è associata all'utente che la crea

### 4. `/update_threshold` (linee ~835-870)
- Aggiunto `AND user_id = %s` nella WHERE dell'UPDATE
- Previene la modifica di soglie di altri utenti

### 5. `/toggle_threshold` (linee ~873-900)
- Aggiunto `AND user_id = %s` nella WHERE dell'UPDATE
- Previene l'attivazione/disattivazione di soglie di altri utenti

### 6. `/delete_threshold` (linee ~903-924)
- Aggiunto `AND user_id = %s` nella WHERE del DELETE
- Previene l'eliminazione di soglie di altri utenti

### 7. `check_and_create_notifications()` (linee ~928-980)
- Aggiunto `pt.user_id` nel SELECT per identificare l'utente
- Aggiunto `GROUP BY pt.user_id` per separare le soglie per utente
- Controllo esistenza notifica ora include `AND user_id = %s`
- INSERT notifica ora include `user_id` per associarla all'utente
- Ogni utente riceve notifiche solo per le proprie soglie

### 8. `/notifications` (linee ~989-1028)
- Aggiunto filtro `AND user_id = %s` per mostrare solo notifiche dell'utente corrente

### 9. `/mark_notification_read/<notification_id>` (linee ~1032-1052)
- Aggiunto `AND user_id = %s` nella WHERE dell'UPDATE
- Previene la marcatura come lette di notifiche di altri utenti

### 10. `/mark_all_notifications_read` (linee ~1055-1075)
- Aggiunto `AND user_id = %s` nella WHERE dell'UPDATE
- Marca come lette solo le notifiche dell'utente corrente

## Istruzioni per il Deploy

### 1. Backup del Database
```bash
mysqldump -u username -p database_name > backup_pre_migration.sql
```

### 2. Esegui la Migrazione
```bash
mysql -u username -p database_name < add_user_to_thresholds.sql
```

### 3. Verifica la Migrazione
```sql
-- Verifica che la colonna user_id sia stata aggiunta
DESCRIBE product_thresholds;
DESCRIBE notifications;

-- Verifica che i vincoli siano stati creati
SHOW CREATE TABLE product_thresholds;
SHOW CREATE TABLE notifications;

-- Verifica che i dati esistenti abbiano user_id = 1 (o il valore che hai impostato)
SELECT * FROM product_thresholds LIMIT 5;
SELECT * FROM notifications LIMIT 5;
```

### 4. Riavvia l'Applicazione
```bash
sudo systemctl restart magazzino-port80.service
```

### 5. Test Funzionale
1. Accedi con un utente
2. Crea una soglia
3. Verifica che sia visibile solo a quell'utente
4. Accedi con un altro utente
5. Verifica che non veda le soglie del primo utente
6. Crea una soglia con il secondo utente
7. Verifica che ogni utente veda solo le proprie soglie

## Note Tecniche

### Vincolo UNIQUE
Il vincolo `unique_user_product (user_id, codice_prodotto)` permette a più utenti di impostare soglie diverse per lo stesso prodotto.

### CASCADE DELETE
Le foreign key hanno `ON DELETE CASCADE`, quindi:
- Se un utente viene eliminato, vengono eliminate automaticamente tutte le sue soglie
- Se un utente viene eliminato, vengono eliminate automaticamente tutte le sue notifiche

### Performance
Gli indici creati su `user_id` nelle tabelle `product_thresholds` e `notifications` garantiscono performance ottimali anche con molti utenti e soglie.

### Sicurezza
Tutti gli endpoint ora verificano:
1. Che l'utente sia loggato (`if 'user_id' not in session`)
2. Che l'utente possa operare solo sui propri dati (filtro `WHERE user_id = session['user_id']`)

## Rollback (in caso di problemi)

Se la migrazione causa problemi, è possibile fare rollback:

```sql
-- Rimuovi le foreign key
ALTER TABLE product_thresholds DROP FOREIGN KEY fk_threshold_user;
ALTER TABLE notifications DROP FOREIGN KEY fk_notification_user;

-- Rimuovi gli indici
ALTER TABLE product_thresholds DROP INDEX idx_user_id;
ALTER TABLE product_thresholds DROP INDEX unique_user_product;
ALTER TABLE notifications DROP INDEX idx_notification_user_id;

-- Rimuovi le colonne
ALTER TABLE product_thresholds DROP COLUMN user_id;
ALTER TABLE notifications DROP COLUMN user_id;

-- Ricrea il vincolo unique originale
ALTER TABLE product_thresholds ADD UNIQUE KEY unique_product (codice_prodotto);

-- Ripristina il backup
mysql -u username -p database_name < backup_pre_migration.sql
```
