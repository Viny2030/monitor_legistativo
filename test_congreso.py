import requests
from bs4 import BeautifulSoup

def test_camaras():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # Pruebas de acceso
    objetivos = {
        "Diputados (Nómina)": "https://www.diputados.gov.ar/diputados/",
        "Senado (Nómina)": "https://www.senado.gob.ar/senadores/listados/listaSenadoResumida"
    }

    for nombre, url in objetivos.items():
        print(f"--- Probando {nombre} ---")
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                # Buscamos tablas en el contenido
                tablas = soup.find_all('table')
                print(f"✅ Conexión exitosa. Se detectaron {len(tablas)} tablas de datos.")
            else:
                print(f"❌ Error {res.status_code} en {nombre}")
        except Exception as e:
            print(f"⚠️ Falló la conexión a {nombre}: {e}")

if __name__ == "__main__":
    test_camaras()
