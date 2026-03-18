"""
core/personal.py
Calcula el costo de personal por diputado cruzando:
  - nomina_personal.csv    → empleados con escalafón y área
  - escala_salarial.csv    → escalafón → sueldo en módulos
  - nomina_diputados.csv   → diputados con bloque

LÓGICA DE ASIGNACIÓN:
  - "AGENTE AFECTADO A BLOQUE POLITICO" → se distribuye entre los diputados
    del bloque proporcionalmente (cantidad de asesores / diputados del bloque)
  - Todo lo demás → "Gastos Generales de Cámara" (no se asigna a ningún diputado)

NOTA SOBRE MÓDULOS:
  La escala salarial usa "módulos" como unidad base.
  El valor del módulo se actualiza por paritaria. Último valor conocido: ~$55,000
  Se puede ajustar con la constante VALOR_MODULO.
"""

import pandas as pd
import os
import re

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Valor del módulo salarial en pesos (actualizar según paritaria vigente)
# Fuente: Comisión Negociadora del Valor del Módulo - Ley 24.600
# Historial confirmado por fuentes periodísticas:
#   Abril 2025:    $2,285.73  (APL, Parlamentario.com)
#   Mayo 2025:     $2,376.04  (La Nación, 03/06/2025)
#   Nov 2025:      $2,554.72  (+7.52% paritaria semestral, La Nación 22/08/2025)
#   Marzo 2026:    $2,729.72  (+6.85% acum: 2%+2.2%+2.5%, iProfesional 12/03/2026)
# Verificación: 4000 módulos × $2,729 = $10,918,866 ≈ dieta senadores $11M (✓)
# Última actualización: Marzo 2026
VALOR_MODULO = 2_730


def extraer_numero_escalafon(escalafon: str) -> int:
    """
    Extrae el número del escalafón para buscar en la tabla de sueldos.
    Ejemplos:
      'A-6-T' → 6
      'M-3-P' → 3
      'S-10-P' → 10
    """
    if not isinstance(escalafon, str):
        return None
    match = re.search(r'-(\d+)-', escalafon)
    return int(match.group(1)) if match else None


def calcular_sueldo_mensual(escalafon: str, df_escala: pd.DataFrame) -> float:
    """
    Calcula el sueldo mensual estimado de un empleado según su escalafón.
    Fórmula: (DEDICACION_FUNCIONAL_MODULO + SUELDO_BASICO_MODULO) × VALOR_MODULO
    """
    num = extraer_numero_escalafon(escalafon)
    if num is None:
        return 0

    fila = df_escala[df_escala["ESCALAFON"] == num]
    if fila.empty:
        return 0

    dedicacion = fila["DEDICACION_FUNCIONAL_MODULO"].iloc[0]
    basico     = fila["SUELDO_BASICO_MODULO"].iloc[0]
    return round((dedicacion + basico) * VALOR_MODULO)


def calcular_costo_personal_por_bloque(
    df_nomina_personal: pd.DataFrame = None,
    df_escala: pd.DataFrame = None,
    df_diputados: pd.DataFrame = None,
    guardar: bool = True,
) -> pd.DataFrame:
    """
    Calcula el costo de personal asignado a cada diputado.

    Retorna DataFrame con columnas:
      Nombre | Bloque | Asesores_bloque | Asesores_por_diputado | Costo_personal_mensual
    """
    print("\n" + "="*55)
    print("  CÁLCULO DE COSTO DE PERSONAL POR DIPUTADO")
    print("="*55)

    # ── Cargar datos ─────────────────────────────────────────────────────────
    if df_nomina_personal is None:
        ruta = os.path.join(DATA_DIR, "nomina_personal.csv")
        df_nomina_personal = pd.read_csv(ruta)
        print(f"  📂 Nómina personal: {len(df_nomina_personal)} empleados")

    if df_escala is None:
        ruta = os.path.join(DATA_DIR, "escala_salarial.csv")
        df_escala = pd.read_csv(ruta)
        print(f"  📂 Escala salarial: {len(df_escala)} categorías")

    if df_diputados is None:
        ruta = os.path.join(DATA_DIR, "nomina_diputados.csv")
        df_diputados = pd.read_csv(ruta)
        print(f"  📂 Nómina diputados: {len(df_diputados)} diputados")

    # ── Calcular sueldo por empleado ──────────────────────────────────────────
    print(f"\n  💰 Calculando sueldos por escalafón (módulo = ${VALOR_MODULO:,})...")
    df_nomina_personal["Sueldo_mensual"] = df_nomina_personal["ESCALAFON"].apply(
        lambda e: calcular_sueldo_mensual(e, df_escala)
    )

    total_masa_salarial = df_nomina_personal["Sueldo_mensual"].sum()
    print(f"  📊 Masa salarial total estimada: ${total_masa_salarial:,.0f}/mes")

    # ── Separar empleados de bloques vs. administración ───────────────────────
    mask_bloque = df_nomina_personal["ESTRUCTURA_DESEMPENO"] == "AGENTE AFECTADO A BLOQUE POLITICO"
    df_bloques = df_nomina_personal[mask_bloque].copy()
    df_admin   = df_nomina_personal[~mask_bloque].copy()

    costo_bloques = df_bloques["Sueldo_mensual"].sum()
    costo_admin   = df_admin["Sueldo_mensual"].sum()

    print(f"\n  👥 Empleados de bloques:      {len(df_bloques):,}  (${costo_bloques:,.0f}/mes)")
    print(f"  🏛️  Empleados administrativos: {len(df_admin):,}  (${costo_admin:,.0f}/mes)")

    # ── Distribuir costo de bloques entre diputados ───────────────────────────
    # Como no sabemos a qué bloque pertenece cada empleado,
    # distribuimos el costo total de bloques proporcionalmente
    # al tamaño de cada bloque.
    diputados_por_bloque = df_diputados["Bloque"].value_counts().reset_index()
    diputados_por_bloque.columns = ["Bloque", "N_diputados"]
    total_diputados = diputados_por_bloque["N_diputados"].sum()

    # Costo por diputado = costo_bloques / total_diputados (distribución uniforme)
    # Refinamiento: podría ponderarse por tamaño del bloque si se consigue el dato
    costo_por_diputado = round(costo_bloques / total_diputados)
    print(f"\n  💡 Costo personal estimado por diputado: ${costo_por_diputado:,}/mes")

    # ── Construir tabla por diputado ─────────────────────────────────────────
    df_resultado = df_diputados[["Nombre", "Bloque", "Distrito"]].copy()
    df_resultado = df_resultado.merge(diputados_por_bloque, on="Bloque", how="left")

    # Asesores proporcionales al tamaño del bloque
    df_resultado["Asesores_bloque_total"] = df_resultado["Bloque"].map(
        lambda b: len(df_bloques) * (
            diputados_por_bloque[diputados_por_bloque["Bloque"] == b]["N_diputados"].iloc[0]
            / total_diputados
        ) if b in diputados_por_bloque["Bloque"].values else 0
    )
    df_resultado["Asesores_por_diputado"] = (
        df_resultado["Asesores_bloque_total"] / df_resultado["N_diputados"]
    ).round(1)

    df_resultado["Costo_personal_mensual"] = costo_por_diputado
    df_resultado["Costo_personal_anual"]   = costo_por_diputado * 12

    # ── Guardar ───────────────────────────────────────────────────────────────
    if guardar:
        ruta = os.path.join(DATA_DIR, "costo_personal_diputados.csv")
        df_resultado.to_csv(ruta, index=False, encoding="utf-8-sig")
        print(f"\n  💾 Guardado: {ruta}  ({len(df_resultado)} diputados)")

    # ── Resumen por bloque ────────────────────────────────────────────────────
    print(f"\n  📌 RESUMEN POR BLOQUE (top 8):")
    resumen = (
        df_resultado.groupby("Bloque")
        .agg(
            Diputados=("Nombre", "count"),
            Asesores_estimados=("Asesores_bloque_total", "first"),
            Costo_mensual_bloque=("Costo_personal_mensual", "sum"),
        )
        .sort_values("Diputados", ascending=False)
        .head(8)
    )
    resumen["Asesores_estimados"] = resumen["Asesores_estimados"].round(0).astype(int)
    resumen["Costo_mensual_bloque"] = resumen["Costo_mensual_bloque"].apply(lambda x: f"${x:,.0f}")
    print(resumen.to_string())

    return df_resultado


def enriquecer_centro_costos(guardar: bool = True) -> pd.DataFrame:
    """
    Enriquece el centro_costos.csv incorporando el costo de personal calculado.
    Actualiza las columnas:
      - Asesores_contados → Asesores_por_diputado
      - Costo_personal_mensual (nuevo rubro)
      - Total_estimado_mensual → recalculado con personal incluido
    """
    ruta_cc = os.path.join(DATA_DIR, "centro_costos.csv")
    if not os.path.exists(ruta_cc):
        print("❌ No se encontró centro_costos.csv")
        return pd.DataFrame()

    df_cc = pd.read_csv(ruta_cc)

    # Limpiar columnas de corridas anteriores para evitar duplicados
    cols_limpiar = ["Costo_personal_mensual", "Asesores_contados",
                    "Total_con_personal", "Nombre_norm"]
    df_cc.drop(columns=[c for c in cols_limpiar if c in df_cc.columns],
               inplace=True)
    df_personal = calcular_costo_personal_por_bloque()

    # Merge — solo columnas necesarias, sin duplicar Nombre
    df_personal_merge = df_personal[["Nombre", "Asesores_por_diputado", "Costo_personal_mensual"]].copy()
    df_personal_merge = df_personal_merge.rename(columns={"Nombre": "Nombre_norm"})
    df_personal_merge["Nombre_norm"] = df_personal_merge["Nombre_norm"].str.strip()
    df_cc["Nombre_norm"] = df_cc["Nombre"].str.strip()

    df_cc = df_cc.merge(df_personal_merge, on="Nombre_norm", how="left")

    # Actualizar columnas
    if "Asesores_por_diputado" in df_cc.columns:
        df_cc["Asesores_contados"] = df_cc["Asesores_por_diputado"]
        df_cc.drop(columns=["Asesores_por_diputado"], inplace=True)

    if "Costo_personal_mensual" in df_cc.columns:
        # Recalcular total con personal
        df_cc["Total_con_personal"] = (
            df_cc["Total_estimado_mensual"].fillna(0) +
            df_cc["Costo_personal_mensual"].fillna(0)
        )

    df_cc.drop(columns=["Nombre_norm"], inplace=True, errors="ignore")

    if guardar:
        df_cc.to_csv(ruta_cc, index=False, encoding="utf-8-sig")
        print(f"\n  ✅ centro_costos.csv actualizado con costo de personal")
        print(f"     Total con personal promedio: ${df_cc['Total_con_personal'].mean():,.0f}/mes")

    return df_cc


if __name__ == "__main__":
    df = calcular_costo_personal_por_bloque()
    print("\n--- Enriqueciendo centro de costos ---")
    enriquecer_centro_costos()