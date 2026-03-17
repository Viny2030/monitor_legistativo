import requests
from bs4 import BeautifulSoup
import pandas as pd

def extraer_diputados():
    url = "https://www.diputados.gov.ar/diputados/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print("--- 🔍 Iniciando extracción de Diputados ---")
    try:
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        datos = []
        tabla = soup.find('table')
        
        if tabla:
            filas = tabla.find_all('tr')[1:]
            for fila in filas:
                cols = fila.find_all('td')
                if len(cols) > 3:
                    datos.append({
                        "Nombre": cols[1].get_text(strip=True),
                        "Distrito": cols[2].get_text(strip=True),
                        "Bloque": cols[3].get_text(strip=True)
                    })
            
            # ESTA ES LA PARTE CLAVE: Crear y guardar el CSV
            df = pd.DataFrame(datos)
            df.to_csv("nomina_diputados.csv", index=False, encoding='utf-8')
            
            print(f"✅ Éxito: Se encontraron {len(df)} diputados y se creó 'nomina_diputados.csv'")
        else:
            print("⚠️ No se encontró la tabla en la página.")
            
    except Exception as e:
        print(f"❌ Error durante la extracción: {e}")

if __name__ == "__main__":
    extraer_diputados()
