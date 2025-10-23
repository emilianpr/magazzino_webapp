#!/bin/bash
# Script per avviare Flask sulla porta 80

echo "🚀 Avviando Magazzino WebApp sulla porta 80..."

# Controlla se authbind è installato
if ! command -v authbind &> /dev/null; then
    echo "📦 Installando authbind..."
    sudo apt install authbind -y
fi

# Configura authbind per la porta 80
if [ ! -f /etc/authbind/byport/80 ]; then
    echo "🔧 Configurando permessi porta 80..."
    sudo touch /etc/authbind/byport/80
    sudo chmod 755 /etc/authbind/byport/80
    sudo chown $USER /etc/authbind/byport/80
fi

# Attiva virtual environment se esiste
if [ -d "venv" ]; then
    echo "🐍 Attivando virtual environment..."
    source venv/bin/activate
fi

# Avvia Flask con authbind
echo "🌐 Flask disponibile su http://$(hostname -I | awk '{print $1}'):80"
authbind --deep python app.py