# Magazzino WebApp

A complete warehouse management web application built with Flask. Track inventory across multiple warehouses, manage stock movements, handle special product states, and reconcile data with legacy systems like AS400.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Database Setup](#database-setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Application Overview](#application-overview)
- [REST API](#rest-api)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## Features

### Core Functionality
- **Multi-warehouse inventory tracking** - Manage products across multiple warehouses with specific locations (shelves, bays, cold storage)
- **Stock movements** - Load, unload, and transfer products with complete audit trail
- **Status management** - Track products in special states (in transit, damaged, in repair, dispatch bay, etc.)
- **Real-time dashboard** - Filter and search products by code, name, location, or status
- **Movement history** - Complete logs of all operations with user, timestamp, and notes

### Advanced Features
- **AS400 reconciliation** - Compare warehouse data with legacy AS400 system exports
- **Excel/TXT exports** - Generate reports for administrative needs
- **Threshold alerts** - Set minimum stock levels and get notifications
- **Batch operations** - Process multiple movements efficiently
- **AMOLED dark mode** - Eye-friendly interface for night work
- **Responsive design** - Works on desktop, tablet, and mobile

### Security
- **Role-based access** - Admin and regular user roles
- **Session-based authentication** - Secure login with hashed passwords
- **Maintenance mode** - Graceful handling during system updates

---

## Requirements

- **Python** 3.10+ (3.11+ recommended)
- **MySQL** 8.0+ or **MariaDB** 10.5+
- **pip** for Python package management

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/emilianpr/magazzino_webapp.git
cd magazzino_webapp
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Database Connection

```bash
# Copy the configuration template
cp config_local.py.template config_local.py

# Edit with your favorite editor
nano config_local.py  # or vim, code, etc.
```

Update the database credentials:

```python
DATABASE_CONFIG = {
    'host': 'localhost',
    'user': 'your_mysql_user',
    'password': 'your_mysql_password',
    'database': 'magazzino_db'
}

FLASK_CONFIG = {
    'secret_key': 'generate_a_random_key',  # See step 5
    'debug': True  # False in production
}
```

### 5. Generate Flask Secret Key

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and paste it as your `secret_key` in `config_local.py`.

### 6. Set Up the Database

See [Database Setup](#database-setup) below.

### 7. Run the Application

```bash
python3 app.py
```

Open your browser at `http://localhost` (or `http://localhost:80`).

---

## Database Setup

### Option A: Fresh Installation (Recommended for Testing)

1. **Create the database in MySQL:**

```bash
mysql -u root -p
```

```sql
CREATE DATABASE magazzino_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'magazzino_webapp'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON magazzino_db.* TO 'magazzino_webapp'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

2. **Import the schema:**

```bash
mysql -u magazzino_webapp -p magazzino_db < database/schema.sql
```

3. **Create your first admin user:**

Generate a password hash:

```bash
python3 generate-passwordhash.py
# Or manually:
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_admin_password'))"
```

Insert the admin user:

```bash
mysql -u magazzino_webapp -p magazzino_db
```

```sql
INSERT INTO utenti (username, password_hash, is_admin) 
VALUES ('admin', 'YOUR_GENERATED_HASH_HERE', 1);
EXIT;
```

### Option B: With Sample Data (For Development/Demo)

1. Complete steps 1-2 from Option A above.

2. **Edit sample data file** (optional):

Before importing, you may want to generate real password hashes. Edit `database/sample_data.sql` and replace the placeholder hashes:

```bash
# Generate hashes for the sample users
python3 -c "from werkzeug.security import generate_password_hash; print('admin123:', generate_password_hash('admin123')); print('operatore123:', generate_password_hash('operatore123'))"
```

3. **Import sample data:**

```bash
mysql -u magazzino_webapp -p magazzino_db < database/sample_data.sql
```

This creates:
- 2 users: `admin` (administrator) and `operatore` (regular user)
- 3 warehouses
- 10 sample products
- Inventory entries with various states
- Sample movements and logs

### Database Files Reference

| File | Description |
|------|-------------|
| `database/schema.sql` | Complete database schema (tables, indexes, foreign keys) |
| `database/sample_data.sql` | Test data with sample products, warehouses, and movements |
| `add_tipo_movimento.sql` | Migration: adds movement type classification |
| `create_notifications_tables.sql` | Migration: notification system tables |
| `create_batch_draft_table.sql` | Migration: batch operation drafts |

---

## Configuration

### config_local.py

The main configuration file (not tracked in Git for security):

```python
DATABASE_CONFIG = {
    'host': 'localhost',           # Database server
    'user': 'magazzino_webapp',    # Database user
    'password': 'your_password',   # Database password
    'database': 'magazzino_db'     # Database name
}

FLASK_CONFIG = {
    'secret_key': 'your_64_char_hex_key',  # Required for sessions
    'debug': True                           # False in production
}
```

### Environment Variables (Alternative)

You can also use environment variables instead of `config_local.py`:

```bash
export DB_HOST=localhost
export DB_USER=magazzino_webapp
export DB_PASSWORD=your_password
export DB_NAME=magazzino_db
export FLASK_SECRET_KEY=your_secret_key
```

### Maintenance Mode

To enable maintenance mode during updates, edit `app.py`:

```python
MAINTENANCE_MODE = True  # All users see maintenance page
MAINTENANCE_MESSAGE = "System update in progress - Est. 30 minutes"
```

---

## Running the Application

### Development Mode

```bash
# Activate virtual environment first
source .venv/bin/activate

# Run Flask development server
python3 app.py
```

The app runs on port 80 by default. Access at `http://localhost`.

### Change Port (if 80 is busy)

Edit the last lines of `app.py`:

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)  # Change port here
```

### Production Mode

See [Production Deployment](#production-deployment).

---

## Application Overview

### Main Pages

| Page | URL | Description |
|------|-----|-------------|
| Login | `/login` | User authentication |
| Dashboard | `/` | Main inventory view with filters |
| Load Stock | `/carico_merci` | Register incoming products |
| Unload Stock | `/scaricomerce` | Remove products (sales, consumption) |
| Return Stock | `/rientro_merce` | Return products from special states |
| Movements | `/movimento` | Advanced transfers between locations |
| Multiple Movement | `/movimento_multiplo` | Batch transfers |
| Movement Log | `/logmovimenti` | Complete movement history |
| Unload Log | `/logscarico` | Unload operation history |
| Reconciliation | `/warehouse_reconciliation` | AS400 comparison tool |
| Admin Panel | `/admin` | System administration (admin only) |
| User Management | `/admin/users` | Manage users (admin only) |
| Thresholds | `/gestione_soglie` | Stock alert configuration |

### Product States

| State | Description |
|-------|-------------|
| `IN_MAGAZZINO` | Standard in-stock |
| `BAIA_USCITA` | Dispatch bay (ready to ship) |
| `IN_PREPARAZIONE` | Being prepared |
| `SPEDITO` | Shipped |
| `IN_UTILIZZO` | In use externally |
| `LABORATORIO` | In lab/testing |
| `DANNEGGIATO` | Damaged |
| `ALTRO` | Other/custom |

### User Roles

- **Admin** (`is_admin = 1`): Full access, can create users, access admin panel
- **Operator** (`is_admin = 0`): Standard operations, no admin access

---

## REST API

The application provides REST endpoints for integration:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/ubicazioni/<product_id>` | GET | Get all locations for a product |
| `/api/ubicazioni_per_prodotto/<product_id>` | GET | Available warehouse locations |
| `/api/quantita_disponibile/<product_id>` | GET | Available quantity |
| `/api/debug-as400-format` | POST | Debug AS400 file format |

**Query parameters for `/api/quantita_disponibile`:**
- `ubicazione` - Filter by specific location

All API responses are in JSON format.

---

## Production Deployment

### Debian/Ubuntu with systemd

1. **Run the deployment script:**

```bash
sudo ./deploy_debian.sh
```

This script:
- Installs system dependencies
- Sets up Python virtual environment
- Configures file permissions
- Creates systemd service
- Enables auto-start on boot

2. **Or manually configure systemd:**

```bash
# Copy service file
sudo cp magazzino-port80.service /etc/systemd/system/

# Edit paths if needed
sudo nano /etc/systemd/system/magazzino-port80.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable magazzino-port80
sudo systemctl start magazzino-port80

# Check status
sudo systemctl status magazzino-port80
```

### Recommended Production Setup

1. **Use a reverse proxy** (nginx or Apache) in front of Flask
2. **Enable HTTPS** with Let's Encrypt
3. **Set `debug: False`** in config_local.py
4. **Use a strong secret_key**
5. **Set up regular database backups**
6. **Configure log rotation**

### Nginx Configuration Example

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/magazzino_webapp/static;
        expires 1d;
    }
}
```

---

## Troubleshooting

### "Cannot connect to database"

1. Verify MySQL is running: `sudo systemctl status mysql`
2. Check credentials in `config_local.py`
3. Test connection: `mysql -u magazzino_webapp -p magazzino_db`
4. Verify user permissions: `SHOW GRANTS FOR 'magazzino_webapp'@'localhost';`

### "Session expires immediately after login"

Missing or invalid `secret_key`. Generate a new one:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Add it to `config_local.py` and restart the app.

### "CSS/JS changes not appearing"

Browser cache issue. Force refresh with `Ctrl+F5` or `Cmd+Shift+R`.

### "Cannot register new users"

Only administrators can register users. The first admin must be created manually in the database.

### "Everyone sees maintenance page"

`MAINTENANCE_MODE = True` is set in `app.py`. Change to `False` and restart.

### "Port 80 requires root"

Either:
- Run with `sudo python3 app.py`
- Change to a higher port (e.g., 5000) in `app.py`
- Use `setcap` to allow binding: `sudo setcap 'cap_net_bind_service=+ep' $(which python3)`

---

## Project Structure

```
magazzino_webapp/
├── app.py                     # Main Flask application
├── database_connection.py     # Database connection pool
├── magazzino_reconciliation.py # AS400 reconciliation logic
├── config_local.py.template   # Configuration template
├── requirements.txt           # Python dependencies
├── database/
│   ├── schema.sql             # Database schema
│   └── sample_data.sql        # Test data
├── static/
│   ├── style.css              # Custom styles
│   └── *.js                   # JavaScript files
├── templates/
│   ├── base.html              # Base template
│   ├── index.html             # Dashboard
│   └── *.html                 # All page templates
├── deploy_debian.sh           # Production deployment script
├── generate-passwordhash.py   # Password hash generator
└── README.md                  # This file
```

---

## Contributing

1. **Found a bug?** Open an issue with reproduction steps.
2. **Want a feature?** Open an issue to discuss before implementing.
3. **Submitting code?** Create a pull request with clear description.

### Guidelines

- Follow existing code patterns
- Test your changes locally
- Document any schema changes
- Include migration scripts for database updates

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Support

For questions or issues, please open a GitHub issue or contact the development team.
