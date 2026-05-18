import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys
from datetime import date

URL = "https://www.diputados.gov.ar/diputados/"
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; monitor-legislativo/1.0)'}
CSV_OUT = "nomina_diputados.csv"

def extraer_diputados():
    print(f"--- 🔍 Extracción Diputados | {date.today()} ---")
    try:
        res = requests.get(URL, headers=HEADERS, timeout=30)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        tabla = soup.find('table')
        if not tabla:
            print("❌ No se encontró tabla en la página. La estructura del sitio puede haber cambiado.")
            sys.exit(1)

        datos = []
        for fila in tabla.find_all('tr')[1:]:
            cols = fila.find_all('td')
            if len(cols) > 3:
                datos.append({
                    "Nombre":   cols[1].get_text(strip=True),
                    "Distrito": cols[2].get_text(strip=True),
                    "Bloque":   cols[3].get_text(strip=True),
                })

        if not datos:
            print("❌ La tabla estaba vacía.")
            sys.exit(1)

        df = pd.DataFrame(datos)
        df.to_csv(CSV_OUT, index=False, encoding='utf-8')
        print(f"✅ {len(df)} diputados guardados en '{CSV_OUT}'")
        print("\n📌 Top bloques:")
        print(df['Bloque'].value_counts().head(10).to_string())

    except requests.RequestException as e:
        print(f"❌ Error de red: {e}")
        sys.exit(1)

if __name__ == "__main__":
    extraer_diputados()