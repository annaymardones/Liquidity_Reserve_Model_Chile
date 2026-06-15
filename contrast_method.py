
"""Módulo independiente de contraste histórico para Liquidity Reserve.

Este módulo valida la cobertura histórica del RL estimado DESPUÉS de que
existan datos de settlement reales. NO es parte del cálculo predictivo.

Ejemplo de uso:
    python contrast_method.py \\
        --rl-reference-estimated 60793731314 \\
        --period-start 2025-01-01 \\
        --period-end 2025-06-30 \\
        --tipo-flujo ISSUING
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_SOURCE_FILE = "settlement_data.xlsx"
FIXED_BANCO_RL = 68_500_000_000  # CLP
PERCENTILE_THRESHOLD = 95
COVERAGE_TARGET = 0.95


@dataclass(frozen=True)
class ContrastResult:
    """Resultado de un contraste individual de cobertura."""

    rl_value: float
    rl_label: str
    total_observations: int
    covered_observations: int
    coverage_rate: float
    meets_target: bool
    coverage_target: float = COVERAGE_TARGET


@dataclass(frozen=True)
class HistoricalMinimumRL:
    """Resultado del cálculo de RL mínima histórica."""

    minimum_rl_95: float
    percentile_used: int
    total_observations: int
    percentile_observation: int
    comparison_vs_estimated: dict  # {rl_type: {rl_value, meets_target}}
    comparison_vs_banco: dict


@dataclass(frozen=True)
class ContrastMethodResult:
    """Resultado completo del análisis de contraste histórico."""

    period_start: pd.Timestamp
    period_end: pd.Timestamp
    flow_type: str
    total_observations: int
    contrast_estimated_rl: ContrastResult
    contrast_banco_rl: ContrastResult
    minimum_historical_rl: HistoricalMinimumRL


def validate_required_columns(columns: Iterable[str]) -> None:
    """Valida que el dataset contenga las columnas mínimas requeridas."""
    required = {"SETTLEMENT_DATE", "PAYMT_PRTY_AMT", "DB_CR_FLAG"}
    missing_columns = required.difference(columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"El archivo fuente no contiene las columnas requeridas: {missing}")


def normalize_flow_type(tipo_flujo: str) -> str:
    """Normaliza y valida el tipo de flujo ingresado por el usuario."""
    flow_type = str(tipo_flujo).strip().upper()
    valid_flow_types = {"ISSUING", "ACQUIRING"}
    if flow_type not in valid_flow_types:
        raise ValueError("tipo_flujo debe ser 'ISSUING' o 'ACQUIRING'.")
    return flow_type


def prepare_settlement_data(data: pd.DataFrame) -> pd.DataFrame:
    """Prepara tipos de datos necesarios para los cálculos."""
    validate_required_columns(data.columns)
    prepared = data.copy()
    prepared["SETTLEMENT_DATE"] = pd.to_datetime(prepared["SETTLEMENT_DATE"], errors="coerce")
    prepared["PAYMT_PRTY_AMT"] = pd.to_numeric(prepared["PAYMT_PRTY_AMT"], errors="coerce")
    prepared["DB_CR_FLAG"] = prepared["DB_CR_FLAG"].astype(str).str.strip().str.upper()

    invalid_dates = prepared["SETTLEMENT_DATE"].isna().sum()
    invalid_amounts = prepared["PAYMT_PRTY_AMT"].isna().sum()
    if invalid_dates:
        raise ValueError(f"Existen {invalid_dates} registros con SETTLEMENT_DATE inválido.")
    if invalid_amounts:
        raise ValueError(f"Existen {invalid_amounts} registros con PAYMT_PRTY_AMT inválido.")

    return prepared


def filter_settlement_data(
    data: pd.DataFrame,
    period_start: str | pd.Timestamp,
    period_end: str | pd.Timestamp,
    tipo_flujo: str,
) -> pd.DataFrame:
    """Filtra datos de settlement por período y tipo de flujo."""
    start = pd.Timestamp(period_start).normalize()
    end = pd.Timestamp(period_end).normalize()
    flow = normalize_flow_type(tipo_flujo)

    filtered = data.loc[
        (pd.to_datetime(data["SETTLEMENT_DATE"]) >= start)
        & (pd.to_datetime(data["SETTLEMENT_DATE"]) < end)
        & (data["DB_CR_FLAG"] == flow),
        ["SETTLEMENT_DATE", "PAYMT_PRTY_AMT", "DB_CR_FLAG"]
    ].copy()

    return filtered


def calculate_coverage(
    exposures: pd.Series,
    rl_reference: float,
) -> ContrastResult:
    """Calcula cobertura de un RL contra exposiciones reales.

    Args:
        exposures: Series con valores absolutos de exposiciones
        rl_reference: RL a evaluar

    Returns:
        ContrastResult con métricas de cobertura
    """
    total_obs = len(exposures)
    covered_obs = (exposures <= rl_reference).sum()
    coverage_rate = covered_obs / total_obs if total_obs > 0 else 0.0
    meets_target = coverage_rate >= COVERAGE_TARGET

    label = f"{rl_reference:,.0f}" if rl_reference > 0 else "N/A"

    return ContrastResult(
        rl_value=rl_reference,
        rl_label=label,
        total_observations=total_obs,
        covered_observations=covered_obs,
        coverage_rate=coverage_rate,
        meets_target=meets_target,
    )


def calculate_minimum_historical_rl(
    exposures: pd.Series,
    rl_estimated: float,
    percentile: int = PERCENTILE_THRESHOLD,
) -> HistoricalMinimumRL:
    """Calcula el RL mínimo histórico para cubrir el percentil especificado.

    Args:
        exposures: Series con valores absolutos de exposiciones
        rl_estimated: RL estimado para comparación
        percentile: Percentil a usar (default 95)

    Returns:
        HistoricalMinimumRL con análisis completo
    """
    total_obs = len(exposures)
    sorted_exposures = exposures.sort_values(ascending=True)
    minimum_rl = sorted_exposures.quantile(percentile / 100.0)
    percentile_idx = int((percentile / 100.0) * total_obs)

    # Contrasts
    contrast_estimated = calculate_coverage(exposures, rl_estimated)
    contrast_banco = calculate_coverage(exposures, FIXED_BANCO_RL)

    comparison_vs_estimated = {
        "rl_value": rl_estimated,
        "rl_label": f"{rl_estimated:,.0f}",
        "meets_95_threshold": contrast_estimated.meets_target,
    }

    comparison_vs_banco = {
        "rl_value": FIXED_BANCO_RL,
        "rl_label": f"{FIXED_BANCO_RL:,.0f}",
        "meets_95_threshold": contrast_banco.meets_target,
    }

    return HistoricalMinimumRL(
        minimum_rl_95=minimum_rl,
        percentile_used=percentile,
        total_observations=total_obs,
        percentile_observation=percentile_idx,
        comparison_vs_estimated=comparison_vs_estimated,
        comparison_vs_banco=comparison_vs_banco,
    )


def perform_contrast_analysis(
    data: pd.DataFrame,
    rl_reference_estimated: float,
    period_start: str | pd.Timestamp,
    period_end: str | pd.Timestamp,
    tipo_flujo: str,
) -> ContrastMethodResult:
    """Realiza análisis completo de contraste histórico.

    Args:
        data: DataFrame con datos de settlement preparados
        rl_reference_estimated: RL estimada a evaluar
        period_start: Inicio del período histórico
        period_end: Fin del período histórico
        tipo_flujo: Tipo de flujo (ISSUING, ACQUIRING)

    Returns:
        ContrastMethodResult con todos los contrastes y análisis
    """
    start = pd.Timestamp(period_start).normalize()
    end = pd.Timestamp(period_end).normalize()
    flow = normalize_flow_type(tipo_flujo)

    # Filtrar datos
    filtered = filter_settlement_data(data, start, end, flow)

    if len(filtered) == 0:
        raise ValueError(
            f"No se encontraron datos para {flow} entre {start.date()} y {end.date()}"
        )

    # Exposiciones absolutas
    exposures = filtered["PAYMT_PRTY_AMT"].abs()

    # Contraste 1: RL Estimada
    contrast_estimated = calculate_coverage(exposures, rl_reference_estimated)

    # Contraste 2: RL Banco de Chile
    contrast_banco = calculate_coverage(exposures, FIXED_BANCO_RL)

    # Contraste 3: RL Mínima Histórica 95%
    minimum_rl = calculate_minimum_historical_rl(exposures, rl_reference_estimated)

    return ContrastMethodResult(
        period_start=start,
        period_end=end,
        flow_type=flow,
        total_observations=len(filtered),
        contrast_estimated_rl=contrast_estimated,
        contrast_banco_rl=contrast_banco,
        minimum_historical_rl=minimum_rl,
    )


def format_clp(value: float, decimals: int = 0) -> str:
    """Formatea valor en CLP con separadores de miles."""
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Formatea valor como porcentaje."""
    return f"{value * 100:.{decimals}f}%"


def print_contrast_results(result: ContrastMethodResult) -> None:
    """Imprime resultados formateados del análisis de contraste."""

    print("\n" + "=" * 80)
    print("ANÁLISIS DE CONTRASTE HISTÓRICO - LIQUIDITY RESERVE MODEL")
    print("=" * 80)

    print(f"\nPERÍODO EVALUADO:")
    print(f"  Inicio:        {result.period_start.strftime('%Y-%m-%d')}")
    print(f"  Fin:           {result.period_end.strftime('%Y-%m-%d')}")
    print(f"  Tipo de flujo: {result.flow_type}")
    print(f"  Total de obs:  {result.total_observations:,}")

    # CONTRASTE 1: RL CALCULADA
    print("\n" + "-" * 80)
    print("CONTRASTE 1: RL CALCULADA")
    print("-" * 80)

    c1 = result.contrast_estimated_rl
    print(f"\n  RL evaluada:        {format_clp(c1.rl_value)}")
    print(f"  Total de obs:       {c1.total_observations:,}")
    print(f"  Obs. cubiertas:     {c1.covered_observations:,}")
    print(f"  Tasa de cobertura:  {format_percentage(c1.coverage_rate)}")
    print(f"  ¿Cumple 95%?:       {'SÍ ✓' if c1.meets_target else 'NO ✗'}")

    # CONTRASTE 2: RL BANCO DE CHILE
    print("\n" + "-" * 80)
    print("CONTRASTE 2: RL BANCO DE CHILE (Línea Operacional Fija)")
    print("-" * 80)

    c2 = result.contrast_banco_rl
    print(f"\n  RL Banco:           {format_clp(c2.rl_value)}")
    print(f"  Total de obs:       {c2.total_observations:,}")
    print(f"  Obs. cubiertas:     {c2.covered_observations:,}")
    print(f"  Tasa de cobertura:  {format_percentage(c2.coverage_rate)}")
    print(f"  ¿Cumple 95%?:       {'SÍ ✓' if c2.meets_target else 'NO ✗'}")

    # CONTRASTE 3: RL MÍNIMA HISTÓRICA
    print("\n" + "-" * 80)
    print("CONTRASTE 3: RL MÍNIMA HISTÓRICA PARA 95% DE COBERTURA")
    print("-" * 80)

    c3 = result.minimum_historical_rl
    print(f"\n  RL Mínima (P95):    {format_clp(c3.minimum_rl_95)}")
    print(f"  Percentil usado:    {c3.percentile_used}%")
    print(f"  Total de obs:       {c3.total_observations:,}")
    print(f"  Obs. en P95:        {c3.percentile_observation:,}")

    print(f"\n  Comparación vs RL Calculada:")
    print(f"    RL Calculada:     {format_clp(c3.comparison_vs_estimated['rl_value'])}")
    print(
        f"    Cumple P95:       "
        f"{'SÍ ✓' if c3.comparison_vs_estimated['meets_95_threshold'] else 'NO ✗'}"
    )
    if c3.comparison_vs_estimated["meets_95_threshold"]:
        diff = c3.comparison_vs_estimated["rl_value"] - c3.minimum_rl_95
        print(f"    Margen excedente:  {format_clp(diff)} ({format_percentage(diff / c3.minimum_rl_95)})")
    else:
        deficit = c3.minimum_rl_95 - c3.comparison_vs_estimated["rl_value"]
        print(f"    Déficit:           {format_clp(deficit)} ({format_percentage(deficit / c3.minimum_rl_95)})")

    print(f"\n  Comparación vs RL Banco de Chile:")
    print(f"    RL Banco:         {format_clp(c3.comparison_vs_banco['rl_value'])}")
    print(
        f"    Cumple P95:       "
        f"{'SÍ ✓' if c3.comparison_vs_banco['meets_95_threshold'] else 'NO ✗'}"
    )
    if c3.comparison_vs_banco["meets_95_threshold"]:
        diff = c3.comparison_vs_banco["rl_value"] - c3.minimum_rl_95
        print(f"    Margen excedente:  {format_clp(diff)} ({format_percentage(diff / c3.minimum_rl_95)})")
    else:
        deficit = c3.minimum_rl_95 - c3.comparison_vs_banco["rl_value"]
        print(f"    Déficit:           {format_clp(deficit)} ({format_percentage(deficit / c3.minimum_rl_95)})")

    # RESUMEN COMPARATIVO
    print("\n" + "-" * 80)
    print("RESUMEN COMPARATIVO DE LOS TRES ESCENARIOS")
    print("-" * 80)

    print(f"\n{'Métrica':<30} {'RL Calculada':<20} {'RL Banco':<20} {'RL Mínima P95':<20}")
    print("  " + "-" * 76)

    print(
        f"{'Valor RL':<30} {format_clp(c1.rl_value):<20} "
        f"{format_clp(c2.rl_value):<20} {format_clp(c3.minimum_rl_95):<20}"
    )
    print(
        f"{'Obs. cubiertas':<30} {c1.covered_observations:<20,} "
        f"{c2.covered_observations:<20,} {int(c3.percentile_observation):<20,}"
    )
    print(
        f"{'Tasa cobertura':<30} {format_percentage(c1.coverage_rate):<20} "
        f"{format_percentage(c2.coverage_rate):<20} ~95%"
    )
    print(
        f"{'Cumple objetivo':<30} {'SÍ ✓' if c1.meets_target else 'NO ✗':<20} "
        f"{'SÍ ✓' if c2.meets_target else 'NO ✗':<20} {'SÍ ✓':<20}"
    )

    print("\n" + "=" * 80 + "\n")


def parse_args() -> argparse.Namespace:
    """Define y parsea los inputs del usuario desde consola."""

    parser = argparse.ArgumentParser(
        description="Módulo de contraste histórico para Liquidity Reserve Model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python contrast_method.py \\
    --rl-reference-estimated 60793731314 \\
    --period-start 2025-01-01 \\
    --period-end 2025-06-30 \\
    --tipo-flujo ISSUING

  python contrast_method.py \\
    --archivo datos_historicos.xlsx \\
    --rl-reference-estimated 55000000000 \\
    --period-start 2024-07-01 \\
    --period-end 2024-12-31 \\
    --tipo-flujo ACQUIRING
        """,
    )

    parser.add_argument(
        "--archivo",
        default=DEFAULT_SOURCE_FILE,
        help=f"Ruta del Excel fuente. Default: {DEFAULT_SOURCE_FILE}",
    )

    parser.add_argument(
        "--rl-reference-estimated",
        type=float,
        required=True,
        help="RL estimada a evaluar (valor numérico en CLP).",
    )

    parser.add_argument(
        "--period-start",
        required=True,
        help="Inicio del período histórico en formato YYYY-MM-DD.",
    )

    parser.add_argument(
        "--period-end",
        required=True,
        help="Fin del período histórico en formato YYYY-MM-DD.",
    )

    parser.add_argument(
        "--tipo-flujo",
        required=True,
        type=str.upper,
        choices=["ISSUING", "ACQUIRING"],
        help="Tipo de flujo a evaluar.",
    )

    return parser.parse_args()


def main() -> None:
    """Punto de entrada principal del módulo de contraste."""

    args = parse_args()

    # Validar archivo
    archivo = Path(args.archivo)
    if not archivo.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {archivo}")

    # Leer datos
    print(f"Leyendo datos desde: {archivo}")
    data = pd.read_excel(archivo)
    print(f"  Registros cargados: {len(data):,}")

    # Preparar datos
    data = prepare_settlement_data(data)
    print(f"  Datos validados y preparados ✓")

    # Realizar análisis
    print(
        f"\nRealizando análisis de contraste para {args.tipo_flujo} "
        f"({args.period_start} a {args.period_end})..."
    )
    result = perform_contrast_analysis(
        data=data,
        rl_reference_estimated=args.rl_reference_estimated,
        period_start=args.period_start,
        period_end=args.period_end,
        tipo_flujo=args.tipo_flujo,
    )

    # Imprimir resultados
    print_contrast_results(result)


if __name__ == "__main__":
    main()
