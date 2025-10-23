#!/usr/bin/env python3
"""
Script per fixare tutti i blocchi try-except-finally in app.py
aggiungendo l'inizializzazione di cursor e conn prima del try
"""

import re

def fix_try_blocks(content):
    """Aggiunge cursor = None e conn = None prima dei blocchi try che usano connect_to_database"""
    
    # Pattern per trovare blocchi try senza inizializzazione
    # Cerca righe con "try:" seguite da conn = connect_to_database()
    pattern = r'(\n    )(try:)\n([ ]*)(conn = connect_to_database\(\))'
    
    # Sostituisce aggiungendo le inizializzazioni
    replacement = r'\1cursor = None\n\1conn = None\n\1\2\n\3\4'
    
    # Applica la sostituzione
    fixed_content = re.sub(pattern, replacement, content)
    
    return fixed_content

# Leggi il file
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Conta quante occorrenze ci sono
try_blocks_count = content.count('try:\n        conn = connect_to_database()')
print(f"Trovati {try_blocks_count} blocchi try da fixare")

# Applica le fix
fixed_content = fix_try_blocks(content)

# Salva il backup
with open('app.py.backup', 'w', encoding='utf-8') as f:
    f.write(content)
print("Backup salvato in app.py.backup")

# Salva il file fixato
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("✅ File app.py fixato!")
print("Verifica manualmente e testa l'applicazione")
