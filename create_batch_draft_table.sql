-- ============================================
-- Script per creare la tabella movimenti_batch_draft
-- Eseguire sul database di produzione
-- ============================================

CREATE TABLE IF NOT EXISTS movimenti_batch_draft (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    nome_bozza VARCHAR(100) NOT NULL,
    json_items JSON NOT NULL,
    nota_globale TEXT,
    stato_origine VARCHAR(50),
    stato_destinazione VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES utenti(id) ON DELETE CASCADE,
    INDEX idx_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Verifica creazione
SELECT 'Tabella movimenti_batch_draft creata con successo!' AS risultato;
