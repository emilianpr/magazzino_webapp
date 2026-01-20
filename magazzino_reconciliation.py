"""
Sistema di Riconciliazione Magazzino AS400 vs WebApp
Pharmagest Italia S.r.l.

Versione: 1.0
Data: 19 Settembre 2025

Descrizione:
Sistema completo per la riconciliazione automatica tra i magazzini AS400 
(Magazzino 27 - Grossisti e Magazzino 28 - Deposito) e l'export della WebApp.
"""

import pandas as pd
import re
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import os


class MagazzinoReconciliation:
    """
    Classe principale per la riconciliazione automatica tra magazzini AS400 e WebApp.
    """

    def __init__(self, log_level: str = "INFO", log_file: str = "magazzino_reconciliation.log"):
        """Inizializza il sistema di riconciliazione."""
        self.log_file = log_file
        self.setup_logging(log_level)
        self.logger = logging.getLogger(__name__)

        # Statistiche dell'ultima riconciliazione
        self.last_reconciliation = {
            'timestamp': None,
            'total_products': 0,
            'aligned_products': 0,
            'differences_count': 0,
            'total_units_as400': 0,
            'total_units_webapp': 0,
            'net_difference': 0,
            'alignment_percentage': 0.0,
            'data_quality': 'UNKNOWN'
        }

    def setup_logging(self, level: str):
        """Configura il sistema di logging."""
        logging.basicConfig(
            level=getattr(logging, level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    def parse_as400_magazzino(self, file_content: str, magazzino_name: str = "") -> pd.DataFrame:
        """Estrae i dati dal formato AS400 valorizzazione magazzino."""
        self.logger.info(f"Parsing file AS400 per magazzino: {magazzino_name}")

        if not file_content or not file_content.strip():
            self.logger.warning(f"File AS400 vuoto per magazzino: {magazzino_name}")
            return pd.DataFrame(columns=['Codice', 'Descrizione', 'Quantita_AS400', 'Fonte_AS400'])

        righe = file_content.split('\n')
        dati = []
        
        # Debug: mostra le prime righe del file
        self.logger.info(f"File AS400 {magazzino_name} - Total righe: {len(righe)}")
        self.logger.info(f"Prime 5 righe del file:")
        for i, riga in enumerate(righe[:5]):
            self.logger.info(f"  Riga {i+1}: '{riga}'")

        pattern_originale = r'\s*(\d{6,7})\s+(.+?)\s+[A-Z]\.\s+(\d{1,3}(?:\.\d{3})*|\d+)\s*$'
        pattern_alternativo = r'\s*(\d{6,7})\s+(.+)\s+(\d{1,3}(?:\.\d{3})*|\d+)\s*$'  # Greedy + fine riga
        
        righe_processate = 0
        righe_match_originale = 0
        righe_match_alternativo = 0

        for i, riga in enumerate(righe):
            try:
                if not riga.strip():
                    continue
                    
                righe_processate += 1
                
                # Debug specifico per prodotti problematici
                is_target_product = any(target in riga for target in ['95413', '0095413', '095413'])
                if is_target_product:
                    self.logger.info(f"FOUND TARGET PRODUCT in {magazzino_name} line {i+1}: '{riga.strip()}'")
                
                # Prova pattern originale
                match = re.match(pattern_originale, riga.strip())
                if match:
                    righe_match_originale += 1
                    codice = match.group(1).strip()
                    descrizione = match.group(2).strip()
                    quantita_str = match.group(3).strip()
                    
                    # Converti quantità gestendo separatori delle migliaia
                    quantita = int(quantita_str.replace('.', ''))

                    if len(codice) >= 6 and quantita >= 0:
                        dati.append({
                            'Codice': codice,
                            'Descrizione': descrizione,
                            'Quantita_AS400': quantita,
                            'Fonte_AS400': magazzino_name or 'AS400'
                        })
                        
                        # Debug per prodotti target
                        if codice.endswith('95413') or codice == '95413':
                            self.logger.info(f"PARSED TARGET PRODUCT: {codice} -> {quantita} units (from '{quantita_str}') from {magazzino_name}")
                        
                        if len(dati) <= 3:  # Log primi 3 match per debug
                            self.logger.info(f"Match trovato: Codice={codice}, Desc='{descrizione}', Qty={quantita}")
                    continue
                
                # Prova pattern alternativo
                match_alt = re.match(pattern_alternativo, riga.strip())
                if match_alt:
                    righe_match_alternativo += 1
                    codice = match_alt.group(1).strip()
                    descrizione = match_alt.group(2).strip()
                    quantita_str = match_alt.group(3).strip()
                    
                    # Converti quantità gestendo separatori delle migliaia
                    quantita = int(quantita_str.replace('.', ''))

                    if len(codice) >= 6 and quantita >= 0:
                        dati.append({
                            'Codice': codice,
                            'Descrizione': descrizione,
                            'Quantita_AS400': quantita,
                            'Fonte_AS400': magazzino_name or 'AS400'
                        })
                        
                        # Debug per prodotti target
                        if codice.endswith('95413') or codice == '95413':
                            self.logger.info(f"PARSED TARGET PRODUCT (alt pattern): {codice} -> {quantita} units (from '{quantita_str}') from {magazzino_name}")
                        
                        if len(dati) <= 3:
                            self.logger.info(f"Match alternativo: Codice={codice}, Desc='{descrizione}', Qty={quantita}")
                    continue
                
                # Se nessun pattern funziona, log per debug
                if righe_processate <= 10:  # Solo prime 10 righe per evitare spam
                    self.logger.debug(f"Nessun match riga {i+1}: '{riga.strip()}'")
                    
            except Exception as e:
                if '95413' in riga:
                    self.logger.error(f"ERROR parsing target product line {i+1}: {str(e)} - Line: '{riga.strip()}'")
                continue
                self.logger.debug(f"Errore parsing riga {i+1}: {str(e)}")
                continue

        df = pd.DataFrame(dati)
        self.logger.info(f"AS400 {magazzino_name} - Statistiche parsing:")
        self.logger.info(f"  Righe processate: {righe_processate}")
        self.logger.info(f"  Match pattern originale: {righe_match_originale}")
        self.logger.info(f"  Match pattern alternativo: {righe_match_alternativo}")
        self.logger.info(f"  Prodotti estratti: {len(df)}")
        
        return df

    def debug_as400_format(self, file_content: str, sample_lines: int = 10) -> Dict:
        """Funzione di debug per analizzare il formato AS400."""
        if not file_content:
            return {'error': 'File vuoto'}
        
        righe = file_content.split('\n')
        sample_righe = [riga for riga in righe[:sample_lines] if riga.strip()]
        
        patterns_test = {
            'originale': r'\s*(\d{6,7})\s+(.+?)\s+[A-Z]\.\s+(\d+)',
            'senza_lettera': r'\s*(\d{6,7})\s+(.+?)\s+(\d+)',
            'con_decimali': r'\s*(\d{6,7})\s+(.+?)\s+[A-Z]\.\s+(\d+[,.]?\d*)',
            'flessibile': r'\s*(\d{4,8})\s+(.+?)\s+(\d+)',
        }
        
        risultati = {
            'total_lines': len(righe),
            'non_empty_lines': len([r for r in righe if r.strip()]),
            'sample_lines': sample_righe,
            'pattern_matches': {}
        }
        
        for nome_pattern, pattern in patterns_test.items():
            matches = 0
            examples = []
            for riga in sample_righe:
                match = re.match(pattern, riga.strip())
                if match:
                    matches += 1
                    if len(examples) < 3:
                        examples.append({
                            'line': riga.strip(),
                            'groups': match.groups()
                        })
            
            risultati['pattern_matches'][nome_pattern] = {
                'matches': matches,
                'examples': examples
            }
        
        return risultati

    def parse_webapp_export(self, file_content: str) -> pd.DataFrame:
        """Estrae i dati dall'export WebApp con parser infallibile."""
        self.logger.info("Parsing export WebApp")

        if not file_content or not file_content.strip():
            self.logger.warning("File export WebApp vuoto")
            return pd.DataFrame(columns=['Codice', 'Descrizione', 'Magazzino_Web', 'Ubicazione', 'Stato', 'Quantita_WebApp', 'Note'])

        righe = file_content.strip().split('\n')
        dati = []
        
        # Debug: conta le righe e mostra alcuni esempi
        righe_dati = [r for r in righe if r.strip() and not any(header in r.lower() for header in 
                     ['pharmagest', 'data esportazione', 'codice        prodotto', '---'])]
        
        self.logger.info(f"File WebApp - Righe totali: {len(righe)}")
        self.logger.info(f"File WebApp - Righe di dati (senza header): {len(righe_dati)}")
        self.logger.info(f"Prime 3 righe di dati:")
        for i, riga in enumerate(righe_dati[:3]):
            self.logger.info(f"  Riga {i+1}: '{riga[:100]}...' se lunga")

        righe_processate = 0
        righe_valide = 0

        for i, riga in enumerate(righe):
            try:
                if not riga.strip() or any(header in riga.lower() for header in 
                    ['pharmagest', 'data esportazione', 'codice        prodotto', '---']):
                    continue

                righe_processate += 1
                
                # Parser infallibile basato su posizioni e pattern
                riga_clean = riga.strip()
                
                # Verifica che inizi con un codice numerico
                words = riga_clean.split()
                if not words or not words[0].isdigit():
                    self.logger.debug(f"Riga {i+1} scartata - non inizia con codice numerico")
                    continue
                
                codice = words[0]
                
                # Strategia bilanciata per trovare la quantità:
                # 1. Se c'è solo 1 numero oltre al codice -> è la quantità
                # 2. Se ci sono 2+ numeri, cerca pattern di note per distinguere
                # 3. Pattern di note: "*", "(", parole specifiche DOPO la posizione 5
                
                numeri_con_posizione = []
                for j, word in enumerate(words):
                    if word.isdigit() and j > 0:  # Esclude il codice (posizione 0)
                        numeri_con_posizione.append((j, int(word)))
                
                if not numeri_con_posizione:
                    self.logger.debug(f"Riga {i+1} scartata - nessuna quantità trovata")
                    continue
                
                # Strategia intelligente basata sul numero di cifre trovate
                if len(numeri_con_posizione) == 1:
                    # Solo un numero -> è sicuramente la quantità
                    quantita = numeri_con_posizione[0][1]
                else:
                    # Multipli numeri -> usa euristica semplice e affidabile
                    # La quantità è il primo numero in posizione ragionevole (4-6)
                    # dopo codice, descrizione, magazzino, ubicazione, stato
                    
                    # Cerca il primo numero in posizione 4-6 (posizione tipica della quantità)
                    qty_candidates = [(pos, val) for pos, val in numeri_con_posizione if 4 <= pos <= 6]
                    if qty_candidates:
                        quantita = qty_candidates[0][1]  # Primo numero in posizione corretta
                    else:
                        # Fallback: primo numero dopo il codice
                        quantita = numeri_con_posizione[0][1]
                
                # Debug per righe specifiche
                if codice in ['94906', '95774', '94964', '95592']:
                    self.logger.info(f"DEBUG {codice}: riga_completa='{riga.strip()}'")
                    self.logger.info(f"DEBUG {codice}: words={words}")
                    self.logger.info(f"DEBUG {codice}: tutti_numeri={numeri_con_posizione}, qty_finale={quantita}")
                
                # Estrai gli altri campi usando regex split come base, ma con logica robusta
                import re
                campi = re.split(r'\s{2,}', riga_clean)
                
                # Ricostruisci i campi in modo intelligente
                if len(campi) >= 5:
                    # Campo 1: descrizione (può contenere il magazzino)
                    desc_raw = campi[1].replace('_', ' ').strip()
                    
                    # Identifica il magazzino
                    if desc_raw.endswith(' farmacia'):
                        descrizione = desc_raw[:-9].strip()
                        magazzino = 'farmacia'
                        # Formato con desc+magazzino uniti
                        ubicazione = campi[2].strip()
                        stato = campi[3].strip()
                        note = ' '.join(campi[5:]).strip() if len(campi) > 5 else ''
                    elif desc_raw.endswith(' grossisti'):
                        descrizione = desc_raw[:-10].strip()
                        magazzino = 'grossisti'
                        # Formato con desc+magazzino uniti
                        ubicazione = campi[2].strip()
                        stato = campi[3].strip()
                        note = ' '.join(campi[5:]).strip() if len(campi) > 5 else ''
                    elif len(campi) >= 6 and campi[2] in ['farmacia', 'grossisti']:
                        # Formato normale separato
                        descrizione = desc_raw
                        magazzino = campi[2].strip()
                        ubicazione = campi[3].strip()
                        stato = campi[4].strip()
                        note = ' '.join(campi[6:]).strip() if len(campi) > 6 else ''
                    else:
                        # Fallback: descrizione come campo completo
                        descrizione = desc_raw
                        magazzino = ''
                        ubicazione = campi[2].strip() if len(campi) > 2 else ''
                        stato = campi[3].strip() if len(campi) > 3 else ''
                        note = ' '.join(campi[5:]).strip() if len(campi) > 5 else ''
                    
                    # Validazione finale
                    if len(codice) >= 3 and quantita >= 0:
                        righe_valide += 1
                        dati.append({
                            'Codice': codice,
                            'Descrizione': descrizione,
                            'Magazzino_Web': magazzino,
                            'Ubicazione': ubicazione,
                            'Stato': stato,
                            'Quantita_WebApp': quantita,
                            'Note': note
                        })
                        self.logger.debug(f"Riga {i+1} OK - Codice: {codice}, Qty: {quantita}, Desc: {descrizione[:30]}...")
                    else:
                        self.logger.debug(f"Riga {i+1} scartata - validazione fallita: codice={codice}, qty={quantita}")
                else:
                    self.logger.debug(f"Riga {i+1} scartata - troppo pochi campi ({len(campi)}): {campi}")

            except Exception as e:
                self.logger.debug(f"Errore parsing riga WebApp {i+1}: {str(e)} - Riga: {riga}")
                continue

        df = pd.DataFrame(dati)
        self.logger.info(f"WebApp parsing completato:")
        self.logger.info(f"  - Righe processate: {righe_processate}")
        self.logger.info(f"  - Righe valide: {righe_valide}")
        self.logger.info(f"  - Prodotti estratti: {len(df)}")
        return df

    def aggregate_webapp_data(self, df_webapp: pd.DataFrame) -> pd.DataFrame:
        """Aggrega i dati WebApp sommando le quantità per codice prodotto."""
        self.logger.info("Aggregazione dati WebApp per codice prodotto")

        if df_webapp.empty:
            return pd.DataFrame(columns=['Codice', 'Descrizione', 'Quantita_WebApp', 'Magazzino_Web', 'Stato', 'Ubicazione', 'Note'])

        try:
            df_agg = df_webapp.groupby('Codice').agg({
                'Descrizione': 'first',
                'Quantita_WebApp': 'sum',
                'Magazzino_Web': lambda x: ', '.join(sorted([str(v) for v in x.unique() if v and str(v).strip()])),
                'Stato': lambda x: ', '.join(sorted([str(v) for v in x.unique() if v and str(v).strip()])),
                'Ubicazione': lambda x: ', '.join(sorted([str(v) for v in x.unique() if v and str(v).strip() and str(v) != 'None'])),
                'Note': lambda x: ' | '.join(sorted([str(v) for v in x.unique() if v and str(v).strip()]))
            }).reset_index()

            self.logger.info(f"Aggregati in {len(df_agg)} prodotti unici")
            return df_agg

        except Exception as e:
            self.logger.error(f"Errore durante aggregazione: {str(e)}")
            return pd.DataFrame(columns=['Codice', 'Descrizione', 'Quantita_WebApp', 'Magazzino_Web', 'Stato', 'Ubicazione', 'Note'])

    def perform_reconciliation(self, df_as400: pd.DataFrame, df_webapp_agg: pd.DataFrame) -> pd.DataFrame:
        """Esegue la riconciliazione tra AS400 unificato e WebApp."""
        self.logger.info("Esecuzione riconciliazione AS400 vs WebApp")

        # Debug: verifica dati in ingresso
        self.logger.info(f"Input AS400: {len(df_as400)} righe")
        if not df_as400.empty:
            sample_as400 = df_as400.head(3)
            for _, row in sample_as400.iterrows():
                self.logger.info(f"AS400 sample: {row['Codice']} -> Qty: {row['Quantita_AS400']} (type: {type(row['Quantita_AS400'])})")
            self.logger.info(f"AS400 total quantity sum: {df_as400['Quantita_AS400'].sum()}")
            
            # Debug: mostra alcuni codici AS400
            codici_as400 = sorted(df_as400['Codice'].unique())[:10]
            self.logger.info(f"Sample codici AS400: {codici_as400}")

        self.logger.info(f"Input WebApp: {len(df_webapp_agg)} righe")
        if not df_webapp_agg.empty:
            sample_webapp = df_webapp_agg.head(3)
            for _, row in sample_webapp.iterrows():
                self.logger.info(f"WebApp sample: {row['Codice']} -> Qty: {row['Quantita_WebApp']} (type: {type(row['Quantita_WebApp'])})")
            
            # Debug: mostra alcuni codici WebApp
            codici_webapp = sorted(df_webapp_agg['Codice'].unique())[:10]
            self.logger.info(f"Sample codici WebApp: {codici_webapp}")

        if df_as400.empty and df_webapp_agg.empty:
            return pd.DataFrame()

        if df_as400.empty:
            df_as400 = pd.DataFrame(columns=['Codice', 'Descrizione', 'Quantita_AS400', 'Fonte_AS400'])

        if df_webapp_agg.empty:
            df_webapp_agg = pd.DataFrame(columns=['Codice', 'Descrizione', 'Quantita_WebApp', 'Magazzino_Web', 'Stato', 'Ubicazione', 'Note'])

        try:
            # Debug: cerca codici in comune PRIMA della normalizzazione
            if not df_as400.empty and not df_webapp_agg.empty:
                codici_as400_orig = set(df_as400['Codice'].unique())
                codici_webapp_orig = set(df_webapp_agg['Codice'].unique())
                codici_comuni_orig = codici_as400_orig.intersection(codici_webapp_orig)
                
                self.logger.info(f"PRIMA normalizzazione - Codici in comune: {len(codici_comuni_orig)}")
            
            # NORMALIZZAZIONE CODICI: rimuovi zeri iniziali
            df_as400_norm = df_as400.copy()
            df_webapp_norm = df_webapp_agg.copy()
            
            df_as400_norm['Codice'] = df_as400_norm['Codice'].astype(str).str.lstrip('0')
            df_webapp_norm['Codice'] = df_webapp_norm['Codice'].astype(str).str.lstrip('0')
            
            # Handle edge case: se il codice diventa vuoto (era tutto zeri), mantieni uno zero
            df_as400_norm['Codice'] = df_as400_norm['Codice'].replace('', '0')
            df_webapp_norm['Codice'] = df_webapp_norm['Codice'].replace('', '0')
            
            self.logger.info("Codici normalizzati (zeri iniziali rimossi)")
            
            # Debug: verifica dopo normalizzazione
            if not df_as400_norm.empty and not df_webapp_norm.empty:
                codici_as400_set = set(df_as400_norm['Codice'].unique())
                codici_webapp_set = set(df_webapp_norm['Codice'].unique())
                codici_comuni = codici_as400_set.intersection(codici_webapp_set)
                
                self.logger.info(f"DOPO normalizzazione:")
                self.logger.info(f"  - Codici AS400 unici: {len(codici_as400_set)}")
                self.logger.info(f"  - Codici WebApp unici: {len(codici_webapp_set)}")
                self.logger.info(f"  - Codici in comune: {len(codici_comuni)}")
                
                if codici_comuni:
                    self.logger.info(f"Esempi codici comuni: {sorted(list(codici_comuni))[:5]}")
                    # Esempi di match trovati
                    for codice in list(codici_comuni)[:3]:
                        as400_qty = df_as400_norm[df_as400_norm['Codice'] == codice]['Quantita_AS400'].iloc[0]
                        webapp_qty = df_webapp_norm[df_webapp_norm['Codice'] == codice]['Quantita_WebApp'].iloc[0]
                        self.logger.info(f"  Match: {codice} -> AS400:{as400_qty}, WebApp:{webapp_qty}")

            # Merge con codici normalizzati
            self.logger.info("Esecuzione merge con codici normalizzati...")
            confronto = df_as400_norm.merge(df_webapp_norm, on='Codice', how='outer', suffixes=('', '_web'))
            self.logger.info(f"Dopo merge: {len(confronto)} righe")
            
            # Conversione numerica
            confronto['Quantita_AS400'] = pd.to_numeric(confronto['Quantita_AS400'], errors='coerce').fillna(0).astype(int)
            confronto['Quantita_WebApp'] = pd.to_numeric(confronto['Quantita_WebApp'], errors='coerce').fillna(0).astype(int)
            
            # Calcolo differenza
            confronto['Differenza'] = confronto['Quantita_WebApp'] - confronto['Quantita_AS400']
            
            # Debug: analisi post-merge
            entrambi_presenti = confronto[(confronto['Quantita_AS400'] > 0) & (confronto['Quantita_WebApp'] > 0)]
            self.logger.info(f"Prodotti presenti in ENTRAMBI i sistemi: {len(entrambi_presenti)}")
            
            if len(entrambi_presenti) > 0:
                # Mostra esempi di prodotti presenti in entrambi
                sample_entrambi = entrambi_presenti[['Codice', 'Quantita_AS400', 'Quantita_WebApp', 'Differenza']].head(5)
                self.logger.info(f"Sample prodotti in entrambi:\n{sample_entrambi.to_string()}")

            # Pulizia colonne
            confronto['Descrizione'] = confronto['Descrizione'].fillna('').fillna(confronto.get('Descrizione_web', pd.Series([''] * len(confronto)))).fillna('')
            confronto['Fonte_AS400'] = confronto['Fonte_AS400'].fillna('Solo_WebApp')
            confronto['Magazzino_Web'] = confronto['Magazzino_Web'].fillna('')
            confronto['Stato'] = confronto['Stato'].fillna('')
            confronto['Ubicazione'] = confronto['Ubicazione'].fillna('')
            confronto['Note'] = confronto['Note'].fillna('')

            confronto['Status'] = confronto['Differenza'].apply(self._classify_difference)

            colonne_finali = [
                'Codice', 'Descrizione', 'Fonte_AS400', 'Quantita_AS400',
                'Quantita_WebApp', 'Differenza', 'Status', 'Magazzino_Web',
                'Stato', 'Ubicazione', 'Note'
            ]

            colonne_disponibili = [col for col in colonne_finali if col in confronto.columns]
            risultato = confronto[colonne_disponibili].copy()
            risultato = risultato.sort_values(['Differenza', 'Codice'], ascending=[False, True])

            # Debug finale
            final_as400_sum = risultato['Quantita_AS400'].sum()
            final_webapp_sum = risultato['Quantita_WebApp'].sum()
            self.logger.info(f"RISULTATO FINALE - AS400 total: {final_as400_sum}, WebApp total: {final_webapp_sum}")

            self._update_reconciliation_stats(risultato)
            self.logger.info(f"Riconciliazione completata: {len(risultato)} prodotti analizzati")
            return risultato

        except Exception as e:
            self.logger.error(f"Errore durante riconciliazione: {str(e)}")
            return pd.DataFrame()

    def _classify_difference(self, diff: int) -> str:
        """Classifica le differenze con emoji e descrizioni."""
        if diff == 0:
            return "✅ ALLINEATO"
        elif diff > 0:
            return f"⚠️ WEBAPP +{diff}"
        else:
            return f"🔴 AS400 +{abs(diff)}"

    def _update_reconciliation_stats(self, df_risultato: pd.DataFrame):
        """Aggiorna le statistiche dell'ultima riconciliazione."""
        if df_risultato.empty:
            return

        aligned_count = len(df_risultato[df_risultato['Differenza'] == 0])
        total_count = len(df_risultato)
        alignment_pct = (aligned_count / total_count * 100) if total_count > 0 else 0.0

        self.last_reconciliation.update({
            'timestamp': datetime.now().isoformat(),
            'total_products': total_count,
            'aligned_products': aligned_count,
            'differences_count': total_count - aligned_count,
            'total_units_as400': int(df_risultato['Quantita_AS400'].sum()),
            'total_units_webapp': int(df_risultato['Quantita_WebApp'].sum()),
            'net_difference': int(df_risultato['Differenza'].sum()),
            'alignment_percentage': round(alignment_pct, 2),
            'data_quality': 'HIGH' if alignment_pct >= 90 else 'MEDIUM' if alignment_pct >= 70 else 'LOW'
        })

    def generate_reconciliation_report(self, df_risultato: pd.DataFrame) -> Dict:
        """Genera un report completo della riconciliazione."""
        if df_risultato.empty:
            return {
                'success': False,
                'error': 'Nessun dato da analizzare',
                'timestamp': datetime.now().isoformat()
            }

        allineati = df_risultato[df_risultato['Differenza'] == 0]
        webapp_maggiore = df_risultato[df_risultato['Differenza'] > 0]
        as400_maggiore = df_risultato[df_risultato['Differenza'] < 0]

        # Debug: analisi dettagliata dei risultati
        self.logger.info(f"Analisi riconciliazione:")
        self.logger.info(f"  - Prodotti allineati (diff=0): {len(allineati)}")
        self.logger.info(f"  - WebApp maggiore (diff>0): {len(webapp_maggiore)}")
        self.logger.info(f"  - AS400 maggiore (diff<0): {len(as400_maggiore)}")
        
        # Debug: mostra distribution delle differenze
        if not df_risultato.empty:
            diff_unique = df_risultato['Differenza'].value_counts().head(10)
            self.logger.info(f"Top 10 differenze: {diff_unique.to_dict()}")
            
            # Mostra alcuni esempi di ogni categoria
            if len(allineati) > 0:
                self.logger.info(f"Esempio prodotto allineato: {allineati.iloc[0]['Codice']}")
            if len(webapp_maggiore) > 0:
                sample_webapp = webapp_maggiore.iloc[0]
                self.logger.info(f"Esempio WebApp maggiore: {sample_webapp['Codice']} (AS400:{sample_webapp['Quantita_AS400']}, WebApp:{sample_webapp['Quantita_WebApp']}, Diff:{sample_webapp['Differenza']})")
            if len(as400_maggiore) > 0:
                sample_as400 = as400_maggiore.iloc[0]
                self.logger.info(f"Esempio AS400 maggiore: {sample_as400['Codice']} (AS400:{sample_as400['Quantita_AS400']}, WebApp:{sample_as400['Quantita_WebApp']}, Diff:{sample_as400['Differenza']})")

        report = {
            'success': True,
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_products': len(df_risultato),
                'data_quality': self.last_reconciliation['data_quality']
            },
            'statistics': {
                'aligned_products': len(allineati),
                'alignment_percentage': self.last_reconciliation['alignment_percentage'],
                'products_with_differences': len(df_risultato) - len(allineati),
                'webapp_higher_count': len(webapp_maggiore),
                'as400_higher_count': len(as400_maggiore),
                'total_units': {
                    'as400': int(df_risultato['Quantita_AS400'].sum()),
                    'webapp': int(df_risultato['Quantita_WebApp'].sum()),
                    'net_difference': int(df_risultato['Differenza'].sum())
                }
            },
            'products': {
                'aligned': self._format_products_for_json(allineati, ['Codice', 'Descrizione', 'Quantita_AS400']),
                'webapp_higher': self._format_products_for_json(webapp_maggiore, ['Codice', 'Descrizione', 'Quantita_AS400', 'Quantita_WebApp', 'Differenza', 'Stato', 'Note']),
                'as400_higher': self._format_products_for_json(as400_maggiore, ['Codice', 'Descrizione', 'Quantita_AS400', 'Quantita_WebApp', 'Differenza', 'Fonte_AS400'])
            },
            'recommendations': self._generate_recommendations(webapp_maggiore, as400_maggiore)
        }

        return report

    def _format_products_for_json(self, df: pd.DataFrame, columns: List[str]) -> List[Dict]:
        """Formatta i prodotti per output JSON."""
        if df.empty:
            return []

        available_columns = [col for col in columns if col in df.columns]
        records = df[available_columns].fillna('').to_dict('records')

        cleaned_records = []
        for record in records:
            cleaned_record = {}
            for key, value in record.items():
                if pd.isna(value):
                    cleaned_record[key] = ''
                elif isinstance(value, (int, float)):
                    cleaned_record[key] = value
                else:
                    cleaned_record[key] = str(value).strip()
            cleaned_records.append(cleaned_record)

        return cleaned_records

    def _generate_recommendations(self, webapp_maggiore: pd.DataFrame, as400_maggiore: pd.DataFrame) -> List[str]:
        """Genera raccomandazioni automatiche."""
        recommendations = []

        if len(webapp_maggiore) > 0:
            recommendations.append(f"Verificare {len(webapp_maggiore)} prodotti con quantità maggiori in WebApp")

            stati_presenti = ' '.join(webapp_maggiore['Stato'].fillna(''))
            if 'baia_uscita' in stati_presenti:
                recommendations.append("Bollettare prodotti in baia_uscita per sincronizzare AS400")
            if 'spedito' in stati_presenti:
                recommendations.append("Aggiornare AS400 per prodotti già spediti")

        if len(as400_maggiore) > 0:
            recommendations.append(f"Aggiornare ubicazioni fisiche per {len(as400_maggiore)} prodotti")

        if len(webapp_maggiore) == 0 and len(as400_maggiore) == 0:
            recommendations.append("Sistema perfettamente allineato - nessuna azione richiesta")

        return recommendations

    def reconcile_warehouses(self, as400_files: Dict[str, str], webapp_export: str) -> Dict:
        """API principale per riconciliazione completa."""
        try:
            self.logger.info("AVVIO RICONCILIAZIONE COMPLETA MAGAZZINI")

            # Parsing file AS400 con debug dettagliato
            df_as400_unificato = pd.DataFrame()
            self.logger.info(f"File AS400 da processare: {list(as400_files.keys())}")
            
            for nome_mag, contenuto in as400_files.items():
                if contenuto and contenuto.strip():
                    self.logger.info(f"Processando {nome_mag}...")
                    df_temp = self.parse_as400_magazzino(contenuto, nome_mag)
                    if not df_temp.empty:
                        self.logger.info(f"{nome_mag}: {len(df_temp)} prodotti estratti, somma quantità: {df_temp['Quantita_AS400'].sum()}")
                        df_as400_unificato = pd.concat([df_as400_unificato, df_temp], ignore_index=True)
                    else:
                        self.logger.warning(f"{nome_mag}: nessun prodotto estratto")
                else:
                    self.logger.info(f"{nome_mag}: file vuoto o non fornito")

            self.logger.info(f"AS400 unificato: {len(df_as400_unificato)} prodotti totali")
            if not df_as400_unificato.empty:
                self.logger.info(f"AS400 unificato - somma quantità totale: {df_as400_unificato['Quantita_AS400'].sum()}")
                
                # Debug: verifica duplicati per codice
                duplicati = df_as400_unificato['Codice'].duplicated().sum()
                if duplicati > 0:
                    self.logger.warning(f"Trovati {duplicati} codici duplicati in AS400 - verranno sommati")
                    
                    # Debug specifico per 95413
                    target_rows = df_as400_unificato[df_as400_unificato['Codice'].str.endswith('95413')]
                    if not target_rows.empty:
                        self.logger.info(f"TARGET PRODUCT 95413 BEFORE aggregation: {len(target_rows)} rows")
                        for idx, row in target_rows.iterrows():
                            self.logger.info(f"  Row {idx}: Code={row['Codice']}, Qty={row['Quantita_AS400']}, Source={row['Fonte_AS400']}")
                    
                    # Aggrega i duplicati sommando le quantità
                    df_as400_unificato = df_as400_unificato.groupby('Codice').agg({
                        'Descrizione': 'first',
                        'Quantita_AS400': 'sum',
                        'Fonte_AS400': lambda x: ', '.join(x.unique())
                    }).reset_index()
                    
                    # Debug dopo aggregazione
                    target_after = df_as400_unificato[df_as400_unificato['Codice'].str.endswith('95413')]
                    if not target_after.empty:
                        self.logger.info(f"TARGET PRODUCT 95413 AFTER aggregation: {len(target_after)} rows")
                        for idx, row in target_after.iterrows():
                            self.logger.info(f"  Final: Code={row['Codice']}, Qty={row['Quantita_AS400']}, Sources={row['Fonte_AS400']}")
                    
                    self.logger.info(f"Dopo aggregazione duplicati AS400: {len(df_as400_unificato)} prodotti, somma: {df_as400_unificato['Quantita_AS400'].sum()}")
                else:
                    # Anche se non ci sono duplicati, controlla 95413
                    target_single = df_as400_unificato[df_as400_unificato['Codice'].str.endswith('95413')]
                    if not target_single.empty:
                        self.logger.info(f"TARGET PRODUCT 95413 (no duplicates): {len(target_single)} rows")
                        for idx, row in target_single.iterrows():
                            self.logger.info(f"  Single: Code={row['Codice']}, Qty={row['Quantita_AS400']}, Source={row['Fonte_AS400']}")
                    else:
                        self.logger.warning(f"TARGET PRODUCT 95413 NOT FOUND in AS400 data!")

            # Parsing export WebApp
            df_webapp = self.parse_webapp_export(webapp_export)
            df_webapp_agg = self.aggregate_webapp_data(df_webapp)

            # Riconciliazione
            df_risultato = self.perform_reconciliation(df_as400_unificato, df_webapp_agg)

            # Generazione report
            report = self.generate_reconciliation_report(df_risultato)

            # Salvataggio audit
            if not df_risultato.empty:
                self._save_reconciliation_data(df_risultato)

            self.logger.info("RICONCILIAZIONE COMPLETATA CON SUCCESSO")
            return report

        except Exception as e:
            error_msg = f"Errore durante riconciliazione: {str(e)}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }

    def _save_reconciliation_data(self, df_risultato: pd.DataFrame) -> str:
        """Salva i dati per audit trail."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reconciliation_{timestamp}.csv"
            df_risultato.to_csv(filename, index=False, encoding='utf-8')
            self.logger.info(f"Audit salvato: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Errore salvataggio audit: {str(e)}")
            return ""


def process_uploaded_files(as400_mag27_file=None, as400_mag28_file=None, webapp_export_file=None) -> Dict:
    """Processa i file caricati dalla webapp."""
    if not webapp_export_file:
        raise ValueError("File export WebApp è obbligatorio")

    reconciler = MagazzinoReconciliation(log_level="INFO")
    as400_files = {}

    try:
        if as400_mag27_file:
            content_27 = as400_mag27_file.read()
            if isinstance(content_27, bytes):
                content_27 = content_27.decode('utf-8')
            as400_files['Magazzino_27_Grossisti'] = content_27

        if as400_mag28_file:
            content_28 = as400_mag28_file.read()
            if isinstance(content_28, bytes):
                content_28 = content_28.decode('utf-8')
            as400_files['Magazzino_28_Deposito'] = content_28

        webapp_content = webapp_export_file.read()
        if isinstance(webapp_content, bytes):
            webapp_content = webapp_content.decode('utf-8')

        return reconciler.reconcile_warehouses(as400_files, webapp_content)

    except Exception as e:
        return {
            'success': False,
            'error': f"Errore lettura file: {str(e)}",
            'timestamp': datetime.now().isoformat()
        }


def get_webapp_api_response(report: Dict) -> Dict:
    """Formatta la risposta per l'API della webapp."""
    if not report.get('success', False):
        return {
            'success': False,
            'error': report.get('error', 'Errore sconosciuto'),
            'timestamp': report.get('timestamp', datetime.now().isoformat())
        }

    stats = report.get('statistics', {})
    metadata = report.get('metadata', {})

    response = {
        'success': True,
        'timestamp': metadata.get('timestamp', datetime.now().isoformat()),
        'summary': {
            'total_products': stats.get('aligned_products', 0) + stats.get('products_with_differences', 0),
            'alignment_percentage': stats.get('alignment_percentage', 0.0),
            'products_aligned': stats.get('aligned_products', 0),
            'products_with_differences': stats.get('products_with_differences', 0),
            'data_quality': metadata.get('data_quality', 'UNKNOWN')
        },
        'details': {
            'webapp_higher': report.get('products', {}).get('webapp_higher', []),
            'as400_higher': report.get('products', {}).get('as400_higher', []),
            'aligned_products': report.get('products', {}).get('aligned', [])
        },
        'actions': {
            'recommendations': report.get('recommendations', [])
        }
    }
    
    return response