/**
 * fix-gap.js - Risolve il problema dello spazio tra la barra di navigazione e il contenuto
 *
 * Questo script:
 * 1. Identifica la barra di navigazione sticky e il contenitore principale
 * 2. Rimuove tutti i margini e padding che causano il gap
 * 3. Applica regole di stile per forzare l'aderenza
 * 4. Si aggiorna al ridimensionamento della finestra
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('[fix-gap] Script caricato');
    
    // Funzione per correggere il gap
    function fixNavigationGap() {
        // Trova la barra di navigazione sticky (testa diverse selezioni)
        const stickyNavOptions = [
            document.querySelector('.sticky.top-0'),
            document.querySelector('.main-content-area > .sticky'),
            document.querySelector('div.sticky')
        ];
        
        // Usa il primo selettore che funziona
        const stickyNav = stickyNavOptions.find(el => el !== null);
        
        // Trova il container principale di contenuto
        const mainContentArea = document.querySelector('.main-content-area');
        
        // Tenta diversi selettori per trovare il contenitore principale
        const contentElementOptions = [
            document.querySelector('[x-data] > div:first-child'),
            document.querySelector('.main-content-area > [x-data] > div:first-child'),
            document.querySelector('.main-content-area > div:first-child')
        ];
        
        // Usa il primo selettore che funziona
        const contentElement = contentElementOptions.find(el => el !== null);
        
        // Logghiamo i risultati della ricerca
        console.log('[fix-gap] Elementi trovati:', {
            stickyNav: stickyNav ? true : false,
            mainContentArea: mainContentArea ? true : false,
            contentElement: contentElement ? true : false
        });
        
        // Se abbiamo trovato gli elementi necessari
        if (stickyNav && contentElement) {
            console.log('[fix-gap] Applicazione correzioni');
            
            // Calcola l'altezza della navbar
            const navHeight = stickyNav.offsetHeight;
            console.log('[fix-gap] Altezza navbar:', navHeight + 'px');
            
            // Rimuovi margini e padding che causano il gap
            contentElement.style.marginTop = '0';
            contentElement.style.paddingTop = '0';
            
            // Applica posizione relativa e top negativo minimo per forzare sovrapposizione
            contentElement.style.position = 'relative';
            contentElement.style.top = '-1px';
            
            // Assicurati che la barra di navigazione non abbia margini inferiori
            stickyNav.style.marginBottom = '0';
            
            // Aggiungi altre regole personalizzate in base alle classi rilevate
            if (contentElement.classList.contains('px-2')) {
                console.log('[fix-gap] Rilevata classe px-2, preservando padding laterali');
            }
            
            console.log('[fix-gap] Correzioni applicate');
        } else {
            console.error('[fix-gap] Impossibile trovare tutti gli elementi necessari');
        }
    }
    
    // Esegui la correzione in diverse fasi per assicurarsi che funzioni
    fixNavigationGap();                  // Esecuzione immediata
    setTimeout(fixNavigationGap, 100);   // Dopo 100ms
    setTimeout(fixNavigationGap, 500);   // Dopo 500ms
    setTimeout(fixNavigationGap, 1000);  // Dopo 1 secondo
    
    // Esegui anche quando la finestra viene ridimensionata
    window.addEventListener('resize', fixNavigationGap);
    
    // Esegui quando Alpine è pronto (potrebbe influire sul layout)
    document.addEventListener('alpine:initialized', fixNavigationGap);
});
