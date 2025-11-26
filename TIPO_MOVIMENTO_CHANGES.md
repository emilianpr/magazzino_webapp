# Tipo Movimento - Log delle Modifiche

## Obiettivo
Aggiungere un campo `tipo_movimento` alla tabella `movimenti` per categorizzare i movimenti e visualizzarli con tag colorati distinti nei log.

## Modifiche al Database

### File: `add_tipo_movimento.sql`
Script SQL per aggiungere il nuovo campo al database:
```sql
-- Aggiunge colonna tipo_movimento alla tabella movimenti
ALTER TABLE movimenti ADD COLUMN tipo_movimento VARCHAR(50) DEFAULT 'TRASFERIMENTO';

-- Classifica i movimenti esistenti in base alla logica da/a magazzino
UPDATE movimenti 
SET tipo_movimento = CASE
    WHEN da_magazzino_id IS NULL AND a_magazzino_id IS NOT NULL THEN 'CARICO'
    WHEN da_magazzino_id IS NOT NULL AND a_magazzino_id IS NULL THEN 'SCARICO'
    WHEN da_magazzino_id IS NOT NULL AND a_magazzino_id IS NOT NULL THEN 'TRASFERIMENTO'
    ELSE 'TRASFERIMENTO'
END
WHERE tipo_movimento = 'TRASFERIMENTO' OR tipo_movimento IS NULL;
```

**AZIONE RICHIESTA**: Eseguire questo script sul database prima di avviare l'applicazione.

## Modifiche Backend (app.py)

### 1. Route `/movimento` (linea ~366)
Aggiunta logica per determinare il tipo di movimento basandosi sugli stati:
```python
if not da_stato and a_stato == 'IN_MAGAZZINO':
    tipo_mov = 'CARICO'
elif da_stato == 'IN_MAGAZZINO' and a_stato != 'IN_MAGAZZINO':
    tipo_mov = 'SCARICO'
elif da_stato == 'IN_MAGAZZINO' and a_stato == 'IN_MAGAZZINO':
    tipo_mov = 'TRASFERIMENTO'
else:
    tipo_mov = 'TRASFERIMENTO'  # default
```

**Logica Corretta:**
- `da_stato` e `a_stato` indicano lo stato della merce (IN_MAGAZZINO, VENDUTO, FUORI_MAGAZZINO, ecc.)
- `da_ubicazione` e `a_ubicazione` indicano la posizione fisica (A1, B2, ecc.)
- `da_magazzino_id` e `a_magazzino_id` indicano quale magazzino fisico (magazzino 1, 2, ecc.)

### 2. Route `/carico_merci` (linea ~1514)
INSERT con `tipo_movimento='CARICO'`

### 3. Route `/modifica_giacenza` (linea ~1654)
INSERT con `tipo_movimento='MODIFICA'`

### 4. Route `/conferma_modifica_giacenza` (linee ~1755, ~1781)
Due INSERT con `tipo_movimento='MODIFICA'`:
- Restituzione modifica giacenza
- Compensazione modifica giacenza

### 5. Route `/rientro_merce` (linea ~1977)
INSERT con `tipo_movimento='TRASFERIMENTO'`

### 6. Route `/aggiorna_giacenza_rapida` (linea ~2179)
INSERT corretto con schema giusto e `tipo_movimento='MODIFICA'`

### 7. Route `/logmovimenti` (linea ~1182)
Aggiunto `mv.tipo_movimento` alla SELECT per recuperare il campo dal database

## Modifiche Frontend (templates/logmovimenti.html)

### 1. Badge Desktop (tabella principale)
Sostituito il badge condizionale con 5 tipologie:
- **CARICO**: Verde (bg-green-100, text-green-800) con icona arrow-up
- **SCARICO**: Rosso (bg-red-100, text-red-800) con icona arrow-down
- **TRASFERIMENTO**: Blu (bg-blue-100, text-blue-800) con icona exchange-alt
- **MODIFICA**: Giallo (bg-yellow-100, text-yellow-800) con icona edit
- **Non specificato**: Grigio (bg-gray-100, text-gray-800) con icona question

### 2. Badge Mobile
Stessi stili applicati alla vista mobile con layout compatto

### 3. Filtro Movimento
Aggiornato dropdown filtro con tutte le opzioni:
```html
<option value="carico">Carico</option>
<option value="scarico">Scarico</option>
<option value="trasferimento">Trasferimento</option>
<option value="modifica">Modifica</option>
```

### 4. JavaScript
Funzione `determineMovementType()` semplificata per usare `movimento.tipo_movimento` dal database

### 5. Dark Mode
Aggiunti stili dark mode per tutti i colori dei badge:
```css
.dark .bg-green-100 { background-color: rgba(34, 197, 94, 0.2) !important; }
.dark .text-green-800 { color: #86efac !important; }
/* ... altri colori ... */
```

## Tipi di Movimento

| Tipo | Descrizione | Icona | Colore | Quando viene usato |
|------|-------------|-------|--------|-------------------|
| CARICO | Carico merci | ↑ arrow-up | Verde | Quando merce entra in magazzino (da_stato=NULL → a_stato=IN_MAGAZZINO) |
| SCARICO | Scarico merci | ↓ arrow-down | Rosso | Quando merce esce dal magazzino (da_stato=IN_MAGAZZINO → a_stato≠IN_MAGAZZINO) |
| TRASFERIMENTO | Trasferimento | ⇄ exchange-alt | Blu | Spostamento interno (da_stato=IN_MAGAZZINO → a_stato=IN_MAGAZZINO) |
| MODIFICA | Modifica giacenza | ✎ edit | Giallo | Modifica manuale di una giacenza esistente |

### Note sulla Logica
- **Stati**: `IN_MAGAZZINO`, `VENDUTO`, `FUORI_MAGAZZINO`, `RESO`, ecc.
- **Ubicazioni**: Posizioni fisiche come "A1", "B2", "Scaffale 3", ecc.
- **Magazzini**: Identificatori numerici dei magazzini fisici (1, 2, 3...)

## Testing

### 1. Database
- [ ] Eseguire `add_tipo_movimento.sql`
- [ ] Verificare che la colonna `tipo_movimento` esista
- [ ] Verificare che i movimenti esistenti siano stati classificati

### 2. Backend
- [ ] Test carico merci → tipo_movimento = 'CARICO'
- [ ] Test scarico merci → tipo_movimento = 'SCARICO'
- [ ] Test movimento tra ubicazioni → tipo_movimento = 'TRASFERIMENTO'
- [ ] Test modifica giacenza → tipo_movimento = 'MODIFICA'
- [ ] Test rientro merce → tipo_movimento = 'TRASFERIMENTO'

### 3. Frontend
- [ ] Verificare badge colorati corretti in vista desktop
- [ ] Verificare badge colorati corretti in vista mobile
- [ ] Verificare filtro per tipo movimento
- [ ] Verificare dark mode per tutti i colori
- [ ] Verificare export CSV include tipo_movimento

### 4. Edge Cases
- [ ] Movimenti senza tipo_movimento (NULL) → badge "Non specificato" grigio
- [ ] Filtro con tipo movimento applicato
- [ ] Combinazione filtri multipli incluso tipo movimento

## Note Tecniche

### Compatibilità
- Tutti i nuovi INSERT hanno `tipo_movimento` specificato
- Il campo ha DEFAULT 'TRASFERIMENTO' per backward compatibility
- Lo script SQL classifica automaticamente i movimenti esistenti

### Prestazioni
- Il campo `tipo_movimento` non richiede indici aggiuntivi (volume basso di query con filtro)
- La SELECT in `/logmovimenti` aggiunge un solo campo, impatto minimo

### Manutenzione Futura
Se si aggiungono nuove route che creano movimenti:
1. Assicurarsi di includere `tipo_movimento` nell'INSERT
2. Scegliere il tipo appropriato tra: CARICO, SCARICO, TRASFERIMENTO, MODIFICA
3. Aggiornare questa documentazione

## Rollback
In caso di problemi, per rimuovere le modifiche:
```sql
ALTER TABLE movimenti DROP COLUMN tipo_movimento;
```
Poi ripristinare i file modificati dal git.
