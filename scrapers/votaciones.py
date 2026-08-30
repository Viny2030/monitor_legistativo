"""
scrapers/votaciones.py
Extrae el historial de votaciones por diputado desde votaciones.hcdn.gob.ar

ESTRUCTURA CONFIRMADA:
  URL: https://votaciones.hcdn.gob.ar/votacion/{ID}
  Tabla HTML: col0=vacía | col1=DIPUTADO | col2=BLOQUE | col3=PROVINCIA | col4=VOTO | col5=vacía
  ID más reciente confirmado: 5881 (Feb 2026)
  IDs van hacia atrás hasta 1993.

INDICADORES QUE GENERA:
  - Participation_Index:    % de votaciones donde el diputado estuvo presente
  - Affirmative_Rate:       % de votos afirmativos sobre total emitidos
  - Bipartisanship_Score:   % de veces que votó igual que al menos un bloque distinto al propio
"""

import requests
import pandas as pd
import time
import os
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
BASE_URL = "https://votaciones.hcdn.gob.ar/votacion/{id}"
# Apunta a /data relativo a la raíz del proyecto, no a scrapers/
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(_BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ID más reciente conocido (actualizar si es necesario)
ID_MAX = 5881
# Cuántas votaciones procesar (ajustar según necesidad)
# 500 votaciones ~ últimos 2 años aprox.
DEFAULT_LIMITE = 200


def obtener_votacion(id_votacion: int) -> dict:
    """
    Descarga y parsea una votación individual.
    Retorna dict con metadata + lista de votos.
    """
    url = BASE_URL.format(id=id_votacion)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        # Título y resultado
        titulo = ""
        resultado = ""
        encabezados = soup.find_all(["h2", "h3", "h4"])
        for h in encabezados:
            t = h.get_text(strip=True)
            if any(x in t.upper() for x in ["AFIRMATIVO", "NEGATIVO", "EMPATE", "RETIRADO"]):
                resultado = t
            elif len(t) > 10:
                titulo = t

        # Tabla de votos
        tabla = soup.find("table")
        if not tabla:
            return None

        votos = []
        for fila in tabla.find_all("tr")[1:]:  # saltar header
            cols = fila.find_all("td")
            if len(cols) < 5:
                continue
            nombre = cols[1].get_text(strip=True)
            bloque = cols[2].get_text(strip=True)
            provincia = cols[3].get_text(strip=True)
            voto = cols[4].get_text(strip=True)

            if nombre:
                votos.append({
                    "ID_votacion": id_votacion,
                    "Nombre": nombre,
                    "Bloque": bloque,
                    "Provincia": provincia,
                    "Voto": voto,
                })

        return {
            "id": id_votacion,
            "titulo": titulo,
            "resultado": resultado,
            "votos": votos,
            "total_presentes": len(votos),
        }

    except Exception as e:
        return None


def descargar_votaciones(
    id_desde: int = None,
    id_hasta: int = None,
    limite: int = DEFAULT_LIMITE,
    guardar: bool = True,
    pausa: float = 0.3,
) -> pd.DataFrame:
    """
    Descarga múltiples votaciones y retorna DataFrame con todos los votos.

    Parámetros:
        id_desde:  ID de inicio (default: ID_MAX - limite)
        id_hasta:  ID de fin    (default: ID_MAX)
        limite:    Máx votaciones a procesar
        guardar:   Si guardar el CSV
        pausa:     Segundos entre requests (respetar al servidor)
    """
    id_hasta = id_hasta or ID_MAX
    id_desde = id_desde or max(1, id_hasta - limite)

    print(f"\n{'='*55}")
    print(f"  DESCARGA DE VOTACIONES")
    print(f"  IDs: {id_desde} → {id_hasta}  ({id_hasta - id_desde} votaciones)")
    print(f"{'='*55}")

    todos_los_votos = []
    metadata = []
    errores = 0
    procesadas = 0

    for id_v in range(id_hasta, id_desde - 1, -1):
        resultado = obtener_votacion(id_v)

        if resultado is None:
            errores += 1
            continue

        todos_los_votos.extend(resultado["votos"])
        metadata.append({
            "ID": resultado["id"],
            "Titulo": resultado["titulo"],
            "Resultado": resultado["resultado"],
            "Total_presentes": resultado["total_presentes"],
        })
        procesadas += 1

        if procesadas % 20 == 0:
            print(f"  ✅ {procesadas} votaciones procesadas | {len(todos_los_votos)} votos acumulados")

        time.sleep(pausa)

    print(f"\n  📊 Total: {procesadas} votaciones | {len(todos_los_votos)} registros de voto")
    print(f"  ❌ Errores/404: {errores}")

    if not todos_los_votos:
        print("  ⚠️  Sin datos de votaciones.")
        return pd.DataFrame()

    df_votos = pd.DataFrame(todos_los_votos)
    df_meta  = pd.DataFrame(metadata)

    if guardar:
        ruta_votos = os.path.join(DATA_DIR, "votaciones_detalle.csv")
        ruta_meta  = os.path.join(DATA_DIR, "votaciones_meta.csv")
        df_votos.to_csv(ruta_votos, index=False, encoding="utf-8-sig")
        df_meta.to_csv(ruta_meta,   index=False, encoding="utf-8-sig")
        print(f"  💾 Guardado: {ruta_votos}  ({len(df_votos)} filas)")
        print(f"  💾 Guardado: {ruta_meta}   ({len(df_meta)} filas)")

    return df_votos


def calcular_indicadores_votacion(df_votos: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula indicadores de votación por diputado.

    Indicadores:
      - Total_votaciones:      cuántas votaciones hubo en el período
      - Presencias:            en cuántas estuvo presente
      - Participation_Index:   % asistencia
      - Votos_afirmativos:     cuántos veces votó SI
      - Votos_negativos:       cuántos veces votó NO
      - Affirmative_Rate:      % de votos positivos sobre emitidos
      - Bipartisanship_Score:  % de votaciones donde coincidió con otro bloque
    """
    if df_votos.empty:
        return pd.DataFrame()

    # Filas basura del scraper: nombre vacio/solo coma con Bloque en NaN
    # (visto en votaciones_detalle.csv para una banca "PENDIENTE DE
    # INCORPORACION" que la tabla de HCDN listo sin nombre todavia asignado).
    # No corresponden a ningun diputado real — si se dejan pasar, rompen el
    # cálculo de Bipartisanship_Score (agg sobre un grupo con Bloque=NaN) y
    # además aparecían como una fila fantasma en indicadores_votacion.csv.
    nombre_valido = df_votos["Nombre"].astype(str).str.strip().str.strip(",") != ""
    descartadas = (~nombre_valido).sum()
    if descartadas:
        print(f"  ⚠️  Descartando {descartadas} filas con nombre vacio/invalido (banca pendiente de incorporacion)")
    df_votos = df_votos[nombre_valido]

    total_votaciones = df_votos["ID_votacion"].nunique()
    print(f"\n📊 Calculando indicadores para {total_votaciones} votaciones...")

    # ── Participation Index ────────────────────────────────────────────────────
    # BUG (encontrado 2026-08 al ver que ~99% de los diputados daban 100% de
    # asistencia en el dashboard): esto contaba CUALQUIER fila en la tabla de
    # la votacion como "presente", pero votaciones.hcdn.gob.ar lista a TODOS
    # los diputados en cada votacion, incluidos los ausentes, con Voto =
    # "AUSENTE" (384 de 10280 filas en votaciones_detalle.csv). Con
    # nunique(ID_votacion) sin filtrar, un diputado ausente en las 40
    # votaciones igual contaba como "40 presencias" -> Participation_Index
    # quedaba en ~100% para casi todos, sin discriminar nada.
    # Presente ahora = emitio un voto real o presidio la sesion. No cuenta
    # AUSENTE ni PENDIENTE DE INCORPORACION (legislador que todavia no habia
    # jurado para esa votacion, no es lo mismo que estar ausente).
    NO_PRESENTE = {"AUSENTE", "PENDIENTE DE INCORPORACIÓN"}
    df_presentes = df_votos[~df_votos["Voto"].str.upper().isin(NO_PRESENTE)]
    presencias = (
        df_presentes.groupby("Nombre")["ID_votacion"]
        .nunique()
        .reset_index()
        .rename(columns={"ID_votacion": "Presencias"})
    )
    # Diputados que nunca tuvieron una fila "presente" (p.ej. ausentes en las
    # 40 votaciones) no aparecen en el groupby de arriba — hay que sumarlos
    # con Presencias=0 en vez de perderlos.
    todos_los_nombres = df_votos[["Nombre"]].drop_duplicates()
    presencias = todos_los_nombres.merge(presencias, on="Nombre", how="left")
    presencias["Presencias"] = presencias["Presencias"].fillna(0).astype(int)
    presencias["Total_votaciones"] = total_votaciones
    presencias["Participation_Index"] = (
        presencias["Presencias"] / total_votaciones * 100
    ).round(2)

    # ── Votos afirmativos / negativos ─────────────────────────────────────────
    tipo_voto = (
        df_votos.groupby(["Nombre", "Voto"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    # Normalizar nombres de columnas de voto
    tipo_voto.columns = [
        str(c).upper().replace(" ", "_") for c in tipo_voto.columns
    ]
    col_afirmativo = next((c for c in tipo_voto.columns if "AFIRMATIVO" in c), None)
    col_negativo   = next((c for c in tipo_voto.columns if "NEGATIVO"   in c), None)

    if col_afirmativo:
        tipo_voto = tipo_voto.rename(columns={col_afirmativo: "Votos_afirmativos"})
    else:
        tipo_voto["Votos_afirmativos"] = 0

    if col_negativo:
        tipo_voto = tipo_voto.rename(columns={col_negativo: "Votos_negativos"})
    else:
        tipo_voto["Votos_negativos"] = 0

    tipo_voto = tipo_voto[["NOMBRE", "Votos_afirmativos", "Votos_negativos"]].copy()
    tipo_voto.columns = ["Nombre", "Votos_afirmativos", "Votos_negativos"]
    denominador = (tipo_voto["Votos_afirmativos"] + tipo_voto["Votos_negativos"])
    tipo_voto["Affirmative_Rate"] = (
        tipo_voto["Votos_afirmativos"] / denominador.where(denominador > 0) * 100
    ).fillna(0).round(2)

    # ── Bipartisanship Score ───────────────────────────────────────────────────
    # Por cada votación, detectar si el diputado votó igual que algún bloque distinto
    bloque_diputado = (
        df_votos.groupby("Nombre")["Bloque"]
        .agg(lambda x: x.mode()[0] if not x.empty else "")
        .reset_index()
    )

    bipartisan_scores = []
    for _, row in bloque_diputado.iterrows():
        nombre = row["Nombre"]
        bloque_propio = row["Bloque"]

        votos_diputado = df_votos[df_votos["Nombre"] == nombre][["ID_votacion", "Voto"]]
        total = len(votos_diputado)
        if total == 0:
            bipartisan_scores.append({"Nombre": nombre, "Bipartisanship_Score": 0})
            continue

        coincidencias = 0
        for _, v in votos_diputado.iterrows():
            id_vot = v["ID_votacion"]
            voto_emitido = v["Voto"]
            # Ver si otros bloques votaron igual en esta votación
            otros_bloques = df_votos[
                (df_votos["ID_votacion"] == id_vot) &
                (df_votos["Bloque"] != bloque_propio) &
                (df_votos["Voto"] == voto_emitido)
            ]
            if len(otros_bloques) > 0:
                coincidencias += 1

        bipartisan_scores.append({
            "Nombre": nombre,
            "Bipartisanship_Score": round(coincidencias / total * 100, 2)
        })

    df_bipartisan = pd.DataFrame(bipartisan_scores)

    # ── Merge final ───────────────────────────────────────────────────────────
    df_ind = presencias.merge(tipo_voto, on="Nombre", how="left")
    df_ind = df_ind.merge(df_bipartisan, on="Nombre", how="left")
    df_ind = df_ind.merge(
        bloque_diputado.rename(columns={"Bloque": "Bloque_votaciones"}),
        on="Nombre", how="left"
    )

    ruta = os.path.join(DATA_DIR, "indicadores_votacion.csv")
    df_ind.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"  💾 Indicadores guardados: {ruta}  ({len(df_ind)} diputados)")

    # Resumen
    print(f"\n  📌 Top 5 Participation Index:")
    print(df_ind.nlargest(5, "Participation_Index")[
        ["Nombre", "Participation_Index", "Bipartisanship_Score"]
    ].to_string(index=False))

    return df_ind


if __name__ == "__main__":
    print("Descargando últimas 50 votaciones para prueba...")
    df = descargar_votaciones(limite=50)
    if not df.empty:
        calcular_indicadores_votacion(df)