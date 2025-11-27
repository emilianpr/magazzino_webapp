ALTER TABLE product_thresholds DROP INDEX unique_product;
ALTER TABLE product_thresholds ADD UNIQUE KEY unique_user_product (user_id, codice_prodotto);
ALTER TABLE product_thresholds ADD CONSTRAINT fk_threshold_user FOREIGN KEY (user_id) REFERENCES utenti(id) ON DELETE CASCADE;
ALTER TABLE notifications ADD COLUMN user_id INT NOT NULL DEFAULT 1 AFTER id;
ALTER TABLE notifications ADD INDEX idx_notification_user_id (user_id);
ALTER TABLE notifications ADD CONSTRAINT fk_notification_user FOREIGN KEY (user_id) REFERENCES utenti(id) ON DELETE CASCADE;

