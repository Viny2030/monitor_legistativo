import requests
from bs4 import BeautifulSoup

def scraping_congreso():
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # URLs actualizadas
    urls = {
        "Diputados": "https://www.diputados.gov.ar/diputados/",
        "Senado": "https://www.senado.gob.ar/senadores/listados/listaSenadoResumida" 
    }

    for camara, url in urls.items():
        print(f"\n--- Extrayendo datos de {camara} ---")
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Buscamos los nombres (en Diputados están en <td>, en Senado suele ser similar)
                nombres = []
                for fila in soup.find_all('tr')[1:6]: # Solo probamos con los primeros 5 para ver si funciona
                    columnas = fila.find_all('td')
                    if len(columnas) > 1:
                        nombre = columnas[1].text.strip()
                        nombres.append(nombre)
                
                if nombres:
                    print(f"✅ Éxito en {camara}. Primeros nombres encontrados:")
                    for n in nombres: print(f" - {n}")
                else:
                    print(f"⚠️ Conectado a {camara}, pero no se encontraron filas en la tabla.")
            else:
                print(f"❌ Error {res.status_code} en {camara}. Revisa la URL.")
        except Exception as e:
            print(f"⚠️ Error técnico en {camara}: {e}")

if __name__ == "__main__":
    scraping_congreso()
