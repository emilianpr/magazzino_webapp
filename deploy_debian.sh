#!/bin/bash
# Magazzino WebApp - Debian Deployment Script

echo "🚀 Starting Magazzino WebApp deployment..."

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "📦 Installing dependencies..."
sudo apt install -y python3.11 python3.11-venv python3-pip mariadb-server mariadb-client nginx build-essential python3-dev

# Create app directory
echo "📁 Creating application directory..."
sudo mkdir -p /var/www/magazzino_webapp
cd /var/www/magazzino_webapp

# Setup virtual environment
echo "🐍 Setting up Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install Python packages
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install gunicorn Flask Werkzeug mysql-connector-python pandas numpy openpyxl XlsxWriter python-dateutil

# Setup MariaDB
echo "🗄️  Setting up MariaDB database..."
sudo systemctl start mariadb
sudo systemctl enable mariadb
sudo mysql -e "CREATE DATABASE IF NOT EXISTS magazzino_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'magazzino_user'@'localhost' IDENTIFIED BY 'changeme123';"
sudo mysql -e "GRANT ALL PRIVILEGES ON magazzino_db.* TO 'magazzino_user'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

# Create systemd service
echo "⚙️  Creating systemd service..."
sudo tee /etc/systemd/system/magazzino.service > /dev/null <<EOF
[Unit]
Description=Magazzino WebApp
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/magazzino_webapp
Environment="PATH=/var/www/magazzino_webapp/venv/bin"
ExecStart=/var/www/magazzino_webapp/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:5000 app:app

[Install]
WantedBy=multi-user.target
EOF

# Setup Nginx
echo "🌐 Configuring Nginx..."
sudo tee /etc/nginx/sites-available/magazzino > /dev/null <<EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }

    location /static {
        alias /var/www/magazzino_webapp/static;
    }

    client_max_body_size 50M;
}
EOF

sudo ln -sf /etc/nginx/sites-available/magazzino /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Set permissions
echo "🔒 Setting permissions..."
sudo chown -R www-data:www-data /var/www/magazzino_webapp

# Start services
echo "🚀 Starting services..."
sudo systemctl daemon-reload
sudo systemctl enable magazzino
sudo systemctl start magazzino
sudo systemctl restart nginx

echo "✅ Deployment complete!"
echo "📍 Access your app at: http://$(hostname -I | awk '{print $1}')"
echo "⚠️  Remember to:"
echo "   1. Copy your application files to /var/www/magazzino_webapp"
echo "   2. Import your database schema"
echo "   3. Change MySQL password in database_connection.py"
echo "   4. Update SECRET_KEY in app.py"
