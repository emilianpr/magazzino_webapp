-- =====================================================
-- Magazzino WebApp - Database Schema
-- Version: 1.4.2
-- 
-- This script creates all required tables for a fresh
-- installation. Run this on a new MySQL database.
-- =====================================================

-- Character set configuration
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- =====================================================
-- CORE TABLES
-- =====================================================

-- Users table (authentication)
CREATE TABLE IF NOT EXISTS `utenti` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `username` VARCHAR(100) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `is_admin` TINYINT(1) DEFAULT 0,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Products catalog
CREATE TABLE IF NOT EXISTS `prodotti` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `codice_prodotto` VARCHAR(50) NOT NULL UNIQUE,
    `nome_prodotto` VARCHAR(255) NOT NULL,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX `idx_codice` (`codice_prodotto`),
    INDEX `idx_nome` (`nome_prodotto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Warehouses
CREATE TABLE IF NOT EXISTS `magazzini` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `nome` VARCHAR(100) NOT NULL UNIQUE,
    `descrizione` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Inventory/Stock levels
CREATE TABLE IF NOT EXISTS `giacenze` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `prodotto_id` INT NOT NULL,
    `magazzino_id` INT,
    `ubicazione` VARCHAR(100),
    `stato` VARCHAR(50) DEFAULT 'IN_MAGAZZINO',
    `quantita` INT NOT NULL DEFAULT 0,
    `note` TEXT,
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`prodotto_id`) REFERENCES `prodotti`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`magazzino_id`) REFERENCES `magazzini`(`id`) ON DELETE SET NULL,
    INDEX `idx_prodotto` (`prodotto_id`),
    INDEX `idx_magazzino` (`magazzino_id`),
    INDEX `idx_ubicazione` (`ubicazione`),
    INDEX `idx_stato` (`stato`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Movement history log
CREATE TABLE IF NOT EXISTS `movimenti` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `prodotto_id` INT NOT NULL,
    `da_magazzino_id` INT,
    `a_magazzino_id` INT,
    `da_ubicazione` VARCHAR(100),
    `a_ubicazione` VARCHAR(100),
    `quantita` INT NOT NULL,
    `note` TEXT,
    `data_ora` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `user_id` INT,
    `stato` VARCHAR(50),
    `tipo_movimento` VARCHAR(50) DEFAULT 'TRASFERIMENTO',
    FOREIGN KEY (`prodotto_id`) REFERENCES `prodotti`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`da_magazzino_id`) REFERENCES `magazzini`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`a_magazzino_id`) REFERENCES `magazzini`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`user_id`) REFERENCES `utenti`(`id`) ON DELETE SET NULL,
    INDEX `idx_prodotto` (`prodotto_id`),
    INDEX `idx_data` (`data_ora`),
    INDEX `idx_user` (`user_id`),
    INDEX `idx_tipo` (`tipo_movimento`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Unload/Dispatch logs
CREATE TABLE IF NOT EXISTS `log_scarichi` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `data_ora` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `user_id` INT,
    `prodotto_id` INT NOT NULL,
    `quantita` INT NOT NULL,
    `note` TEXT,
    `tipo_scarico` VARCHAR(50),
    FOREIGN KEY (`user_id`) REFERENCES `utenti`(`id`) ON DELETE SET NULL,
    FOREIGN KEY (`prodotto_id`) REFERENCES `prodotti`(`id`) ON DELETE CASCADE,
    INDEX `idx_data` (`data_ora`),
    INDEX `idx_prodotto` (`prodotto_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- CHANGELOG & VERSIONING
-- =====================================================

CREATE TABLE IF NOT EXISTS `changelogs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `versione` VARCHAR(50) NOT NULL,
    `data_rilascio` DATE NOT NULL,
    `descrizione` TEXT NOT NULL,
    `user_id` INT,
    `data_creazione` DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `utenti`(`id`) ON DELETE SET NULL,
    INDEX `idx_versione` (`versione`),
    INDEX `idx_data` (`data_rilascio`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- NOTIFICATIONS SYSTEM
-- =====================================================

-- Product threshold alerts
CREATE TABLE IF NOT EXISTS `product_thresholds` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `codice_prodotto` VARCHAR(50) NOT NULL,
    `nome_prodotto` VARCHAR(255) NOT NULL,
    `soglia_minima` INT NOT NULL DEFAULT 0,
    `notifica_attiva` BOOLEAN DEFAULT TRUE,
    `user_id` INT,
    `data_creazione` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `data_modifica` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY `unique_product` (`codice_prodotto`),
    INDEX `idx_codice` (`codice_prodotto`),
    INDEX `idx_attiva` (`notifica_attiva`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Generated notifications
CREATE TABLE IF NOT EXISTS `notifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `codice_prodotto` VARCHAR(50) NOT NULL,
    `nome_prodotto` VARCHAR(255) NOT NULL,
    `quantita_attuale` INT NOT NULL,
    `soglia_minima` INT NOT NULL,
    `magazzino` VARCHAR(100),
    `data_notifica` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `visualizzata` BOOLEAN DEFAULT FALSE,
    `data_visualizzazione` DATETIME NULL,
    INDEX `idx_codice` (`codice_prodotto`),
    INDEX `idx_visualizzata` (`visualizzata`),
    INDEX `idx_data` (`data_notifica`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- BATCH OPERATIONS
-- =====================================================

-- Draft storage for batch movements
CREATE TABLE IF NOT EXISTS `movimenti_batch_draft` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `nome_bozza` VARCHAR(100) NOT NULL,
    `json_items` JSON NOT NULL,
    `nota_globale` TEXT,
    `stato_origine` VARCHAR(50),
    `stato_destinazione` VARCHAR(50),
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (`user_id`) REFERENCES `utenti`(`id`) ON DELETE CASCADE,
    INDEX `idx_user_created` (`user_id`, `created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- =====================================================
-- SCHEMA COMPLETE
-- =====================================================
