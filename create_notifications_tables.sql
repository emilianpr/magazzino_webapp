-- Tabella per le soglie di notifica dei prodotti
CREATE TABLE IF NOT EXISTS product_thresholds (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codice_prodotto VARCHAR(50) NOT NULL,
    nome_prodotto VARCHAR(255) NOT NULL,
    soglia_minima INT NOT NULL DEFAULT 0,
    notifica_attiva BOOLEAN DEFAULT TRUE,
    data_creazione DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_modifica DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_product (codice_prodotto),
    INDEX idx_codice (codice_prodotto),
    INDEX idx_attiva (notifica_attiva)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabella per le notifiche generate
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codice_prodotto VARCHAR(50) NOT NULL,
    nome_prodotto VARCHAR(255) NOT NULL,
    quantita_attuale INT NOT NULL,
    soglia_minima INT NOT NULL,
    magazzino VARCHAR(100),
    data_notifica DATETIME DEFAULT CURRENT_TIMESTAMP,
    visualizzata BOOLEAN DEFAULT FALSE,
    data_visualizzazione DATETIME NULL,
    INDEX idx_codice (codice_prodotto),
    INDEX idx_visualizzata (visualizzata),
    INDEX idx_data (data_notifica)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
