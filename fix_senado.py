import requests
from bs4 import BeautifulSoup

def intentar_senado():
    # URL de la Home - Es la que tiene menos probabilidades de dar 404
    url = "https://www.senado.gob.ar/senadores/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'es-AR,es;q=0.9',
        'Connection': 'keep-alive',
    }

    print(f"--- 📡 Intentando conectar con el Senado ---")
    try:
        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Buscamos cualquier enlace que contenga la palabra 'senador' o 'senadores'
            enlaces = soup.find_all('a', href=True)
            nombres = [e.get_text(strip=True) for e in enlaces if '/senadores/' in e['href']]
            
            if nombres:
                print(f"✅ ¡Conexión lograda! Se encontraron {len(nombres)} posibles registros.")
                for n in nombres[:5]: print(f" - {n}")
            else:
                print("⚠️ Conectó, pero la página no mostró la lista de nombres (posible JavaScript).")
        else:
            print(f"❌ El Senado sigue rechazando la conexión. Código: {res.status_code}")
    except Exception as e:
        print(f"⚠️ Error de red: {e}")

if __name__ == "__main__":
    intentar_senado()
