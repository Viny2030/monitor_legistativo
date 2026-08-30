"""
actualizar_diputados.py
=======================
Actualiza data/diputados.json con datos reales de asistencia y votaciones
leyendo data/indicadores_votacion.csv (ya disponible en el repo).

No depende de scraping externo — usa solo archivos locales.

Uso:
    python actualizar_diputados.py
"""
import json
import os
import csv
from datetime import datetime

DATA_DIR    = "data"
JSON_FILE   = os.path.join(DATA_DIR, "diputados.json")
ASIST_CSV   = os.path.join(DATA_DIR, "indicadores_votacion.csv")


def load_asistencia():
    """Lee indicadores_votacion.csv y devuelve dict por nombre normalizado."""
    datos = {}
    if not os.path.exists(ASIST_CSV):
        print(f"[WARN] No encontrado: {ASIST_CSV}")
        return datos
    with open(ASIST_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            nombre = row.get("Nombre", "").strip().upper()
            if not nombre or nombre == ",":
                continue
            try:
                datos[nombre] = {
                    "asistencia_pct":       round(float(row.get("Participation_Index", 0) or 0), 1),
                    "proyectos_presentados": int(row.get("Presencias", 0) or 0),
                    "proyectos_aprobados":   int(row.get("Votos_afirmativos", 0) or 0),
                    "iqp": round(float(row.get("Affirmative_Rate", 0) or 0) / 100, 4),
                    "total_votaciones":      int(row.get("Total_votaciones", 0) or 0),
                    "bipartisanship":        round(float(row.get("Bipartisanship_Score", 0) or 0), 1),
                }
            except (ValueError, TypeError):
                continue
    print(f"[OK] {len(datos)} registros en indicadores_votacion.csv")
    return datos


def normalizar_nombre(nombre):
    """Normaliza nombre para matching: 'García, Juan' → 'GARCIA, JUAN'"""
    import unicodedata
    nombre = nombre.upper().strip()
    # quitar tildes
    nfkd = unicodedata.normalize("NFKD", nombre)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def main():
    # Cargar JSON actual
    if not os.path.exists(JSON_FILE):
        print(f"[ERROR] No encontrado: {JSON_FILE}")
        return

    with open(JSON_FILE, encoding="utf-8") as f:
        data = json.load(f)

    diputados = data.get("diputados", [])
    print(f"[INFO] {len(diputados)} diputados en diputados.json")

    # Cargar asistencia
    asistencia = load_asistencia()

    # Normalizar keys del CSV
    asistencia_norm = {normalizar_nombre(k): v for k, v in asistencia.items()}

    # Merge
    actualizados = 0
    for d in diputados:
        nombre_norm = normalizar_nombre(d.get("nombre", ""))
        if nombre_norm in asistencia_norm:
            a = asistencia_norm[nombre_norm]
            d["asistencia_pct"]        = a["asistencia_pct"]
            d["proyectos_presentados"] = a["total_votaciones"]
            d["proyectos_aprobados"]   = a["proyectos_aprobados"]
            d["iqp"]                   = a["iqp"]
            d["bipartisanship"]        = a["bipartisanship"]
            d["fuente_asistencia"]     = "indicadores_votacion.csv"
            # nape se calculaba antes en scraper_pipeline.py a partir del
            # asistencia_pct viejo (de la fuente en vivo, poco confiable) y
            # quedaba stale/inconsistente una vez que este merge pisaba
            # asistencia_pct con el valor real — recalculamos para que ambos
            # campos sigan siendo consistentes entre si.
            d["nape"]                  = round(1 - a["asistencia_pct"] / 100, 4)
            actualizados += 1

    print(f"[OK] {actualizados}/{len(diputados)} diputados actualizados con datos reales")

    # Guardar
    data["meta"]["ultima_actualizacion"] = datetime.now().isoformat()
    # Solo afirmamos la fuente si el merge realmente actualizo diputados. Antes
    # esta linea se ejecutaba incondicionalmente: si el matching por nombre
    # fallaba (o si nomina volvia a pisar data["diputados"] en una corrida
    # posterior que no repitiera este script), meta.fuente_asistencia quedaba
    # afirmando una fuente que en realidad no estaba aplicada a ningun
    # diputado — que es exactamente el bug que se detecto en produccion.
    if actualizados > 0:
        data["meta"]["fuente_asistencia"] = "indicadores_votacion.csv (HCDN votaciones)"
        data["meta"]["fuente_asistencia_actualizados"] = f"{actualizados}/{len(diputados)}"
    else:
        data["meta"]["fuente_asistencia"] = None
        data["meta"]["fuente_asistencia_actualizados"] = "0/0"
        print("[WARN] Ningun diputado matcheo contra indicadores_votacion.csv — "
              "no se marca fuente_asistencia para no mentir en meta.")
    data["diputados"] = diputados

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {JSON_FILE} actualizado")


if __name__ == "__main__":
    main()