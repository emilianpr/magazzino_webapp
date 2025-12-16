-- =====================================================
-- Magazzino WebApp - Sample Data for Testing
-- 
-- This script inserts sample data for testing purposes.
-- Run this AFTER schema.sql on a fresh database.
-- 
-- Default admin credentials:
--   Username: admin
--   Password: admin123
-- 
-- CHANGE THE PASSWORD IN PRODUCTION!
-- =====================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- =====================================================
-- USERS
-- =====================================================
-- NOTE: The password hashes below are PLACEHOLDERS.
-- You MUST generate real hashes before using this data.
-- 
-- To generate a password hash, run:
--   python generate-passwordhash.py
-- 
-- Or use this Python command:
--   python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_password'))"
--
-- Default test credentials (generate hashes first!):
--   admin / admin123 (is_admin = 1)
--   operatore / operatore123 (is_admin = 0)

-- IMPORTANT: Replace 'GENERATE_HASH_HERE' with actual hashes!
INSERT INTO `utenti` (`username`, `password_hash`, `is_admin`) VALUES
('admin', 'GENERATE_HASH_FOR_admin123', 1),
('operatore', 'GENERATE_HASH_FOR_operatore123', 0);

-- =====================================================
-- WAREHOUSES
-- =====================================================
INSERT INTO `magazzini` (`nome`, `descrizione`) VALUES
('Magazzino Principale', 'Main warehouse - Central location'),
('Magazzino Secondario', 'Secondary warehouse - North wing'),
('Cold Storage', 'Temperature-controlled storage area');

-- =====================================================
-- PRODUCTS
-- =====================================================
INSERT INTO `prodotti` (`codice_prodotto`, `nome_prodotto`) VALUES
('PROD-001', 'Widget Standard Type A'),
('PROD-002', 'Widget Premium Type B'),
('PROD-003', 'Connector Cable 2m'),
('PROD-004', 'Power Supply Unit 500W'),
('PROD-005', 'Mounting Bracket Kit'),
('PROD-006', 'LED Display Panel 24"'),
('PROD-007', 'Control Board v2.0'),
('PROD-008', 'Sensor Module Temperature'),
('PROD-009', 'Protective Case Large'),
('PROD-010', 'Maintenance Kit Complete');

-- =====================================================
-- INVENTORY (GIACENZE)
-- =====================================================
INSERT INTO `giacenze` (`prodotto_id`, `magazzino_id`, `ubicazione`, `stato`, `quantita`, `note`) VALUES
-- Warehouse 1 - Main
(1, 1, 'A-01-01', 'IN_MAGAZZINO', 150, 'Standard stock'),
(1, 1, 'A-01-02', 'IN_MAGAZZINO', 75, 'Overflow stock'),
(2, 1, 'A-02-01', 'IN_MAGAZZINO', 50, 'Premium items'),
(3, 1, 'B-01-01', 'IN_MAGAZZINO', 200, 'Cable storage'),
(4, 1, 'C-01-01', 'IN_MAGAZZINO', 30, 'Electronics section'),
(5, 1, 'D-01-01', 'IN_MAGAZZINO', 100, 'Hardware accessories'),
-- Warehouse 1 - Special states
(6, 1, 'E-01-01', 'BAIA_USCITA', 10, 'Ready for shipment'),
(7, 1, 'F-01-01', 'LABORATORIO', 5, 'Under testing'),
(8, 1, 'G-01-01', 'DANNEGGIATO', 3, 'Awaiting inspection'),
-- Warehouse 2 - Secondary
(1, 2, 'S-01-01', 'IN_MAGAZZINO', 25, 'Backup stock'),
(3, 2, 'S-02-01', 'IN_MAGAZZINO', 50, 'Secondary cable storage'),
(9, 2, 'S-03-01', 'IN_MAGAZZINO', 40, 'Protective cases'),
(10, 2, 'S-04-01', 'IN_MAGAZZINO', 15, 'Maintenance supplies'),
-- Cold Storage
(8, 3, 'CS-01-01', 'IN_MAGAZZINO', 20, 'Temperature-sensitive sensors');

-- =====================================================
-- SAMPLE MOVEMENTS
-- =====================================================
INSERT INTO `movimenti` (`prodotto_id`, `da_magazzino_id`, `a_magazzino_id`, `da_ubicazione`, `a_ubicazione`, `quantita`, `note`, `data_ora`, `user_id`, `stato`, `tipo_movimento`) VALUES
(1, NULL, 1, NULL, 'A-01-01', 200, 'Initial stock receipt', DATE_SUB(NOW(), INTERVAL 30 DAY), 1, 'IN_MAGAZZINO', 'CARICO'),
(2, NULL, 1, NULL, 'A-02-01', 75, 'Premium items received', DATE_SUB(NOW(), INTERVAL 25 DAY), 1, 'IN_MAGAZZINO', 'CARICO'),
(1, 1, 1, 'A-01-01', 'A-01-02', 75, 'Overflow relocation', DATE_SUB(NOW(), INTERVAL 20 DAY), 1, 'IN_MAGAZZINO', 'TRASFERIMENTO'),
(3, NULL, 1, NULL, 'B-01-01', 250, 'Cable shipment arrived', DATE_SUB(NOW(), INTERVAL 15 DAY), 1, 'IN_MAGAZZINO', 'CARICO'),
(1, 1, 2, 'A-01-01', 'S-01-01', 25, 'Transfer to secondary', DATE_SUB(NOW(), INTERVAL 10 DAY), 1, 'IN_MAGAZZINO', 'TRASFERIMENTO'),
(6, 1, 1, 'E-01-01', 'E-01-01', 10, 'Moved to dispatch bay', DATE_SUB(NOW(), INTERVAL 5 DAY), 1, 'BAIA_USCITA', 'TRASFERIMENTO');

-- =====================================================
-- SAMPLE UNLOAD LOGS
-- =====================================================
INSERT INTO `log_scarichi` (`data_ora`, `user_id`, `prodotto_id`, `quantita`, `note`, `tipo_scarico`) VALUES
(DATE_SUB(NOW(), INTERVAL 7 DAY), 1, 1, 25, 'Customer order #1234', 'VENDITA'),
(DATE_SUB(NOW(), INTERVAL 5 DAY), 1, 3, 50, 'Internal project use', 'USO_INTERNO'),
(DATE_SUB(NOW(), INTERVAL 3 DAY), 2, 2, 25, 'Customer order #1235', 'VENDITA');

-- =====================================================
-- SAMPLE THRESHOLDS
-- =====================================================
INSERT INTO `product_thresholds` (`codice_prodotto`, `nome_prodotto`, `soglia_minima`, `notifica_attiva`) VALUES
('PROD-001', 'Widget Standard Type A', 50, TRUE),
('PROD-002', 'Widget Premium Type B', 20, TRUE),
('PROD-004', 'Power Supply Unit 500W', 10, TRUE);

-- =====================================================
-- SAMPLE CHANGELOG
-- =====================================================
INSERT INTO `changelogs` (`versione`, `data_rilascio`, `descrizione`, `user_id`) VALUES
('v1.0.0', DATE_SUB(CURDATE(), INTERVAL 90 DAY), 'Initial release with basic inventory management', 1),
('v1.1.0', DATE_SUB(CURDATE(), INTERVAL 60 DAY), 'Added multi-warehouse support and location tracking', 1),
('v1.2.0', DATE_SUB(CURDATE(), INTERVAL 30 DAY), 'Introduced status management and movement logs', 1),
('v1.3.0', DATE_SUB(CURDATE(), INTERVAL 14 DAY), 'Added AS400 reconciliation feature', 1),
('v1.4.0', CURDATE(), 'Notification system and threshold alerts', 1);

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================
-- SAMPLE DATA COMPLETE
-- =====================================================
