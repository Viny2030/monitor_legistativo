import requests
from bs4 import BeautifulSoup

def scraping_congreso():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
        'Referer': 'https://www.google.com/'
    }
    
    urls = {
        "Diputados": "https://www.diputados.gov.ar/diputados/",
        "Senado": "https://www.senado.gob.ar/senadores/listados/listaSenadoResumida"
    }

    for camara, url in urls.items():
        print(f"\n--- 🔍 Intentando {camara} ---")
        try:
            # Usamos una sesión para mantener cookies, a veces ayuda con el Senado
            session = requests.Session()
            res = session.get(url, headers=headers, timeout=25)
            
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                filas = soup.find_all('tr')
                nombres = []

                for fila in filas[1:6]: 
                    columnas = fila.find_all('td')
                    if len(columnas) > 1:
                        # En el Senado la estructura de la tabla puede variar, probamos capturar texto
                        texto = columnas[1].get_text(strip=True)
                        if len(texto) > 2: nombres.append(texto)
                
                if nombres:
                    print(f"✅ Éxito en {camara}:")
                    for n in nombres: print(f"   👤 {n}")
                else:
                    print(f"⚠️ {camara} conectado, pero la tabla no devolvió nombres.")
            else:
                print(f"❌ Error {res.status_code} en {camara}")
        except Exception as e:
            print(f"⚠️ Falló {camara}: El servidor cerró la conexión (Anti-Bot).")

if __name__ == "__main__":
    scraping_congreso()
