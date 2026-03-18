"""
core/efficiency.py
Calcula el Score Final de Eficiencia (SFE) por diputado.

Fórmula (del documento MEL-TP):
  SFE = (Asistencia × 0.20) + (Éxito Legislativo × 0.30) + (Eficiencia del Gasto × 0.50)

Donde:
  - Asistencia          = Participation_Index (de indicadores_votacion.csv)
  - Éxito Legislativo   = Bipartisanship_Score (proxy hasta tener datos de proyectos)
  - Eficiencia del Gasto = Comparación del costo del despacho vs promedio del bloque

Escala final: 0 a 100 puntos
  90-100 → 🟢 Muy eficiente
  70-89  → 🟡 Eficiente
  50-69  → 🟠 Regular
  0-49   → 🔴 Ineficiente
"""

import pandas as pd
import os

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


def calcular_eficiencia_gasto(df_costos: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el índice de eficiencia del gasto comparando el costo
    de cada diputado con el promedio de su bloque.

    Lógica:
      - Si el costo del diputado es igual o menor al promedio del bloque → 100 puntos
      - Si supera el promedio → se penaliza proporcionalmente
      - Escala: 0 a 100
    """
    if "Total_estimado_mensual" not in df_costos.columns:
        df_costos["Eficiencia_gasto"] = 50.0  # valor neutral si no hay datos
        return df_costos

    # Promedio por bloque
    prom_bloque = (
        df_costos.groupby("Bloque")["Total_estimado_mensual"]
        .mean()
        .rename("Promedio_bloque")
    )
    df = df_costos.merge(prom_bloque, on="Bloque", how="left")

    # Eficiencia: 100 si está en o bajo el promedio, penalizar si supera
    def score_gasto(row):
        costo = row["Total_estimado_mensual"]
        prom  = row["Promedio_bloque"]
        if pd.isna(costo) or pd.isna(prom) or prom == 0:
            return 50.0
        ratio = costo / prom
        if ratio <= 1.0:
            return 100.0
        else:
            # Penalización proporcional: 20% sobre promedio = 0 puntos
            score = max(0, 100 - (ratio - 1) * 500)
            return round(score, 2)

    df["Eficiencia_gasto"] = df.apply(score_gasto, axis=1)
    return df


def calcular_sfe(
    df_costos: pd.DataFrame = None,
    df_indicadores: pd.DataFrame = None,
    peso_asistencia: float = 0.20,
    peso_legislativo: float = 0.30,
    peso_gasto: float = 0.50,
) -> pd.DataFrame:
    """
    Calcula el Score Final de Eficiencia (SFE) para cada diputado.

    Parámetros:
        df_costos:       DataFrame de centro_costos.csv
        df_indicadores:  DataFrame de indicadores_votacion.csv
        peso_*:          Pesos de cada componente (deben sumar 1.0)

    Retorna:
        DataFrame con ranking completo ordenado por SFE descendente
    """
    print("\n" + "="*55)
    print("  CÁLCULO DE SCORE FINAL DE EFICIENCIA (SFE)")
    print("="*55)

    # ── Cargar datos si no se pasaron ─────────────────────────────────────────
    if df_costos is None:
        ruta = os.path.join(DATA_DIR, "centro_costos.csv")
        if os.path.exists(ruta):
            df_costos = pd.read_csv(ruta)
            print(f"  📂 Cargado: {ruta}")
        else:
            print("  ❌ No se encontró centro_costos.csv")
            return pd.DataFrame()

    if df_indicadores is None:
        ruta = os.path.join(DATA_DIR, "indicadores_votacion.csv")
        if os.path.exists(ruta):
            df_indicadores = pd.read_csv(ruta)
            print(f"  📂 Cargado: {ruta}")
        else:
            print("  ⚠️  No se encontró indicadores_votacion.csv — asistencia en 0")
            df_indicadores = pd.DataFrame()

    # ── Normalizar nombres para el merge ─────────────────────────────────────
    df_costos["Nombre_norm"] = (
        df_costos["Nombre"].str.upper().str.strip()
        .str.replace(r'[,.]', '', regex=True)
        .str.replace(r'\s+', ' ', regex=True)
    )

    if not df_indicadores.empty:
        df_indicadores["Nombre_norm"] = (
            df_indicadores["Nombre"].str.upper().str.strip()
            .str.replace(r'[,.]', '', regex=True)
            .str.replace(r'\s+', ' ', regex=True)
        )

    # ── Eficiencia del gasto ──────────────────────────────────────────────────
    df = calcular_eficiencia_gasto(df_costos.copy())

    # ── Merge con indicadores de votación ─────────────────────────────────────
    if not df_indicadores.empty:
        cols_ind = ["Nombre_norm", "Participation_Index", "Bipartisanship_Score"]
        cols_disponibles = [c for c in cols_ind if c in df_indicadores.columns]
        df = df.merge(df_indicadores[cols_disponibles], on="Nombre_norm", how="left")
    else:
        df["Participation_Index"]  = 0.0
        df["Bipartisanship_Score"] = 0.0

    # Rellenar NaN con 0 para diputados sin datos de votación
    df["Participation_Index"]  = df["Participation_Index"].fillna(0)
    df["Bipartisanship_Score"] = df["Bipartisanship_Score"].fillna(0)
    df["Eficiencia_gasto"]     = df["Eficiencia_gasto"].fillna(50)

    # ── Calcular SFE ──────────────────────────────────────────────────────────
    df["SFE"] = (
        df["Participation_Index"]  * peso_asistencia  +
        df["Bipartisanship_Score"] * peso_legislativo +
        df["Eficiencia_gasto"]     * peso_gasto
    ).round(2)

    # ── Clasificación ────────────────────────────────────────────────────────
    def clasificar(sfe):
        if sfe >= 90: return "🟢 Muy eficiente"
        if sfe >= 70: return "🟡 Eficiente"
        if sfe >= 50: return "🟠 Regular"
        return "🔴 Ineficiente"

    df["Categoria"] = df["SFE"].apply(clasificar)

    # ── Ranking ───────────────────────────────────────────────────────────────
    df = df.sort_values("SFE", ascending=False).reset_index(drop=True)
    df.index += 1  # ranking desde 1
    df.index.name = "Ranking"

    # Columnas finales
    cols_output = [
        "Nombre", "Distrito", "Bloque",
        "Participation_Index", "Bipartisanship_Score",
        "Eficiencia_gasto", "SFE", "Categoria",
        "Total_estimado_mensual", "Promedio_bloque",
    ]
    cols_output = [c for c in cols_output if c in df.columns]
    df_out = df[cols_output].copy()

    # ── Guardar ───────────────────────────────────────────────────────────────
    ruta_out = os.path.join(DATA_DIR, "ranking_sfe.csv")
    df_out.to_csv(ruta_out, index=True, encoding="utf-8-sig")
    print(f"\n  💾 Ranking guardado: {ruta_out}  ({len(df_out)} diputados)")

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n  📊 DISTRIBUCIÓN POR CATEGORÍA:")
    for cat, n in df_out["Categoria"].value_counts().items():
        print(f"    {cat}: {n} diputados")

    print(f"\n  🏆 TOP 10 MÁS EFICIENTES:")
    print(df_out.head(10)[["Nombre", "Bloque", "SFE", "Categoria"]].to_string())

    print(f"\n  ⚠️  BOTTOM 10 MENOS EFICIENTES:")
    print(df_out.tail(10)[["Nombre", "Bloque", "SFE", "Categoria"]].to_string())

    print(f"\n  📌 PROMEDIO SFE POR BLOQUE:")
    por_bloque = (
        df_out.groupby("Bloque")["SFE"]
        .agg(["mean", "count"])
        .sort_values("mean", ascending=False)
        .rename(columns={"mean": "SFE_promedio", "count": "Diputados"})
    )
    por_bloque["SFE_promedio"] = por_bloque["SFE_promedio"].round(2)
    print(por_bloque.to_string())

    return df_out


if __name__ == "__main__":
    df_ranking = calcular_sfe()