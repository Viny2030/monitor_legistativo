import requests
from bs4 import BeautifulSoup
import pandas as pd

def obtener_diputados():
    url = "https://www.diputados.gov.ar/diputados/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscamos la tabla o los elementos que contienen los nombres
        # En esa web, los diputados suelen estar en una tabla con clase 'table'
        diputados = []
        tabla = soup.find('table') 
        
        if tabla:
            filas = tabla.find_all('tr')[1:] # Saltamos el encabezado
            for fila in filas:
                columnas = fila.find_all('td')
                if len(columnas) > 1:
                    nombre = columnas[1].text.strip()
                    bloque = columnas[3].text.strip()
                    diputados.append({"Nombre": nombre, "Bloque": bloque})
            
            df = pd.DataFrame(diputados)
            print(f"📊 Se encontraron {len(df)} diputados.")
            print("\n📌 Resumen por Bloque:")
            print(df['Bloque'].value_counts())
        else:
            print("❌ No se encontró la tabla de datos. La estructura del sitio podría haber cambiado.")
            
    except Exception as e:
        print(f"⚠️ Error en el scraping: {e}")

if __name__ == "__main__":
    obtener_diputados()
