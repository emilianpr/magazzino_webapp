#!/usr/bin/env python3
"""
Script per applicare il dark mode AMOLED a tutte le pagine HTML del progetto
"""

import os
import re

# Lista delle pagine da aggiornare (escludendo index.html che è già fatto)
pages_to_update = [
    'logmovimenti.html',
    'logscarico.html', 
    'login.html',
    'register.html',
    'nuovo-prodotto.html',
    'changelogs.html',
    'scarico_merce_non_in_magazzino.html'
]

# CSS dark mode variables da aggiungere
dark_mode_css = '''
    :root {
      --bg-primary: #f8fafc;
      --bg-secondary: #ffffff;
      --bg-tertiary: #f1f5f9;
      --text-primary: #1e293b;
      --text-secondary: #64748b;
      --border-color: #e2e8f0;
    }
    
    .dark {
      --bg-primary: #000000;
      --bg-secondary: #0a0a0a;
      --bg-tertiary: #1a1a1a;
      --text-primary: #ffffff;
      --text-secondary: #d1d5db;
      --border-color: #2a2a2a;
    }
'''

def update_html_file(filepath):
    """Aggiorna un file HTML con dark mode support"""
    print(f"Updating {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Aggiornare body tag per includere dark mode Alpine.js
    body_pattern = r'<body([^>]*?)x-data="([^"]*?)"([^>]*?)>'
    if re.search(body_pattern, content):
        # Se già ha x-data, aggiungere darkMode
        def replace_body(match):
            before = match.group(1)
            x_data = match.group(2)
            after = match.group(3)
            
            if 'darkMode' not in x_data:
                if x_data.strip():
                    new_x_data = f"{x_data}, darkMode: localStorage.getItem('darkMode') === 'true'"
                else:
                    new_x_data = "darkMode: localStorage.getItem('darkMode') === 'true'"
                
                x_init = ''' x-init="$watch('darkMode', val => { 
  localStorage.setItem('darkMode', val); 
  if(val) document.documentElement.classList.add('dark'); 
  else document.documentElement.classList.remove('dark'); 
}); 
if(darkMode) document.documentElement.classList.add('dark')"'''
                
                return f'<body{before}x-data="{new_x_data}"{x_init}{after}>'
            return match.group(0)
        
        content = re.sub(body_pattern, replace_body, content)
    
    # 2. Aggiungere dark mode CSS variables
    css_pattern = r'(\s*body\s*\{[^}]+\})'
    if re.search(css_pattern, content):
        def replace_css(match):
            original_body_css = match.group(1)
            
            # Aggiungere transition al body CSS esistente
            updated_body_css = re.sub(
                r'(\s*body\s*\{[^}]+)(background-color:\s*[^;]+;)([^}]*\})',
                r'\1\2\n      color: var(--text-primary);\3',
                original_body_css
            )
            
            return dark_mode_css + '\n' + updated_body_css
        
        content = re.sub(css_pattern, replace_css, content, count=1)
    
    # 3. Aggiornare sidebar backgrounds
    content = re.sub(
        r'bg-white shadow-lg z-20',
        r'bg-white dark:bg-black shadow-lg z-20',
        content
    )
    
    # 4. Aggiungere Alpine.js script se non presente
    if 'alpinejs' not in content.lower():
        content = re.sub(
            r'</body>',
            r'  <script src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js" defer></script>\n</body>',
            content
        )
    
    # 5. Aggiungere dark mode toggle se c'è già una navbar
    if 'changelogs' in content and 'dark-mode-toggle' not in content:
        # Trova la sezione changelogs e aggiungi il toggle
        changelog_pattern = r'(<!-- Icona Changelog -->\s*<a href[^>]+title="Changelog"[^>]*>[^<]*</a>)'
        if re.search(changelog_pattern, content):
            toggle_html = '''<!-- Dark Mode Toggle -->
          <button id="dark-mode-toggle" 
                  @click="darkMode = !darkMode"
                  class="p-2 text-gray-500 hover:text-phg-primary hover:bg-phg-secondary dark:text-gray-400 dark:hover:text-yellow-400 dark:hover:bg-gray-700 rounded-lg transition-colors duration-200" 
                  title="Toggle Dark Mode">
            <i class="fas fa-sun text-lg dark:hidden"></i>
            <i class="fas fa-moon text-lg hidden dark:inline"></i>
          </button>
          '''
            content = re.sub(changelog_pattern, toggle_html + r'\1', content)
    
    # Salva il file aggiornato
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Updated {filepath}")

def main():
    templates_dir = 'templates'
    
    for page in pages_to_update:
        filepath = os.path.join(templates_dir, page)
        if os.path.exists(filepath):
            try:
                update_html_file(filepath)
            except Exception as e:
                print(f"❌ Error updating {filepath}: {e}")
        else:
            print(f"⚠️  File not found: {filepath}")
    
    print("\n🎉 Dark mode update completed!")

if __name__ == "__main__":
    main()
