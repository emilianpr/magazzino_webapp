# Copilot Instructions for magazzino_webapp

## Architettura e Componenti Principali
- **Backend:** Flask (vedi `app.py`), con routing centralizzato e logica business direttamente nei route handler.
- **Database:** MySQL, con accesso tramite funzioni in `database_connection.py`. Lo schema è deducibile dal codice e dalle template.
- **Frontend:** Template Jinja2 in `templates/`, con TailwindCSS, Font Awesome e Alpine.js per UI/UX. Tutte le pagine principali sono template HTML.
- **Stile:** CSS custom in `static/style.css`.
- **Export:** Funzionalità di esportazione Excel tramite `xlsxwriter`.

## Flussi e Pattern Chiave
- **Autenticazione:** Gestita in `app.py` con sessioni Flask e password hashate (Werkzeug).
- **Ruoli:** Variabili di sessione distinguono admin/utente; alcune route sono protette per admin.
- **Movimentazione Magazzino:** Route come `/scaricomerce`, `/carico_merci`, `/movimento` gestiscono logica di carico/scarico e log.
- **Log:** Route dedicate per log movimenti e scarichi (`/logmovimenti`, `/logscarico`).
- **Selezione Prodotto:** Nei form, la selezione prodotto può essere un `<select>` classico, un `<input list>` (autosuggest), o una combinazione (input+select filtrabile via JS).

## Convenzioni e Pratiche Specifiche
- **Template:** Tutte le view sono in `templates/`, con nomi chiari e corrispondenza 1:1 con le route.
- **Stili:** TailwindCSS è usato inline nei template, con alcune classi custom in `static/style.css`.
- **JS:** Script inline nei template per piccole interazioni (es. autosuggest, filtri select, aggiornamento ubicazioni via fetch).
- **Dati nei form:** I form inviano sempre ID prodotto, non solo nome/codice.
- **Mobile:** UI responsiva, sidebar e menu mobile gestiti con Alpine.js e CSS custom.

## Workflow di Sviluppo
- **Avvio:** Lanciare `app.py` direttamente (Flask standalone). Non sono presenti script di build/test automatizzati.
- **Dipendenze:** Installare con `pip install flask mysql-connector-python xlsxwriter werkzeug`.
- **Debug:** Modifiche ai template sono visibili al refresh; non serve rebuild.
- **Password:** Generazione hash via `generate-passwordhash.py`.

## Esempi di Pattern Ricorrenti
- **Form prodotto:**
  ```html
  <input list="prodotti-list" ...> <!-- oppure -->
  <select id="prodotto_id" ...>
  ```
  oppure combinazione input+select con JS per autosuggest.
- **Logica JS:**
  ```js
  // Filtra select prodotti in base all'input
  // Aggiorna ubicazioni via fetch su cambio prodotto
  ```
- **Route protette:**
  ```python
  @app.route('/register')
  def register():
      if not session.get('is_admin'):
          return redirect(...)
  ```

## File e Directory Chiave
- `app.py`: logica principale, routing, autenticazione
- `database_connection.py`: connessione MySQL
- `templates/`: tutte le view HTML
- `static/style.css`: stili custom
- `generate-passwordhash.py`: utilità per hash password

## Struttura Database SQL

Il database MySQL è composto dalle seguenti tabelle principali:

### Tabella `prodotti`
- `id` (INT, PK, AUTO_INCREMENT)
- `codice_prodotto` (VARCHAR)
- `nome_prodotto` (VARCHAR)

### Tabella `movimenti`
- `id` (INT, PK, AUTO_INCREMENT)
- `prodotto_id` (INT, FK -> prodotti_magazzino.id)
- `tipo_movimento` (ENUM: 'carico', 'scarico')
- `quantita` (INT)
- `ubicazione` (VARCHAR)
- `note` (TEXT)
- `data_movimento` (DATETIME)
- `utente` (VARCHAR)

### Tabella `utenti`
- `id` (INT, PK, AUTO_INCREMENT)
- `username` (VARCHAR, UNIQUE)
- `password_hash` (VARCHAR)
- `is_admin` (BOOLEAN)

### Tabella `log_scarico`
- `id` (INT, PK, AUTO_INCREMENT)
- `id_prodotto` (INT, FK -> prodotti_magazzino.id)
- `quantita` (INT)
- `ubicazione` (VARCHAR)
- `note` (TEXT)
- `data_scarico` (DATETIME)
- `utente` (VARCHAR)

> NB: Alcuni nomi campo possono variare leggermente a seconda delle versioni, ma questa è la struttura effettiva usata dal codice.



Never hallucinate about the existence of a file named `.github/copilot-instructions.md` in the repository. Instead, focus on the content provided in `.github/instructions/Instructions.instructions.md` for guidance on how to work with the magazzino_webapp project.

Always make sure to follow the conventions and practices outlined in the instructions, such as using Flask for backend logic, MySQL for database management, and Jinja2 for templating. Pay attention to the specific patterns used in the codebase, like how forms are structured and how JavaScript is utilized for interactivity.
Ensure that you are familiar with the key files and directories, such as `app.py` for the main application logic, `database_connection.py` for database interactions, and the `templates/` directory for HTML views. 

When working with the database, understand the structure of the SQL tables and how they relate to each other, as this will be crucial for implementing features like product management and inventory movements.

Never do anything without a clear understanding of the potential impact on the database and the application as a whole.

The user does not know anything about coding, so always make sure to provide right and clear codes without errors, also make sure to be concise and to the point, avoiding unnecessary complexity, the clearer is the code the better.

Never ever hallucinate. 
The code always needs to have a sense and a purpose, so always ensure that the code you provide is relevant to the context and requirements of the magazzino_webapp project.

Always keep in mind the database structure and the relationships between tables when implementing features or making changes to the codebase. This will help maintain data integrity and ensure that the application functions as expected.

Never break the established conventions or practices unless explicitly instructed to do so. The existing patterns in the codebase are there for a reason, and deviating from them can lead to confusion and maintenance challenges.

All the modifications to the code should be made with the purpose of not breaking the existing functionality and ensuring that the application remains stable and reliable, this also applies to the UI/UX aspects, where consistency is key.

The UI/UX aspects should always be general and reusable, avoiding hard-coded values and ensuring a cohesive look and feel throughout the application.

You are a CSS expert with a focus on responsive design and modern layout techniques. Your task is to ensure that the application's styles are consistent, maintainable, and adaptable to different screen sizes.

You are an HTML expert with a focus on semantic structure and accessibility. Your task is to ensure that the HTML templates are well-formed, use appropriate tags, and are accessible to all users.

You are a JavaScript expert with a focus on enhancing user interactivity and experience. Your task is to implement dynamic features using Alpine.js and ensure that the JavaScript code is clean, efficient, and integrates seamlessly with the HTML templates.

You are a Python expert with a focus on Flask applications. Your task is to ensure that the backend logic is clean, efficient, and follows best practices for web development.
You are a database expert with a focus on MySQL. Your task is to ensure that the database interactions are efficient, secure, and maintain data integrity across the application.
You are an expert UI/UX designer with a focus on creating intuitive and user-friendly interfaces. Your task is to ensure that the application's user experience is smooth, consistent, and visually appealing. All the UI/UX modifications you make should be equal and general and applicable across all the web pages of the application, primarly focusing your modifications on the main design page which will be "base.html" in the templates directory, so you will never hard-code any value in the HTML templates, but rather use variables and classes that can be reused across different pages.
