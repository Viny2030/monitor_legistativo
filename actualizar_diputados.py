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

DATA_DIR    = "../data"
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
            actualizados += 1

    print(f"[OK] {actualizados}/{len(diputados)} diputados actualizados con datos reales")

    # Guardar
    data["meta"]["ultima_actualizacion"] = datetime.now().isoformat()
    data["meta"]["fuente_asistencia"]    = "indicadores_votacion.csv (HCDN votaciones)"
    data["diputados"] = diputados

    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] {JSON_FILE} actualizado")


if __name__ == "__main__":
    main()