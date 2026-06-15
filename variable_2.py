"""Cálculo de la Variable 2 para Liquidity Reserve.

La Variable 2 compara RL_Variable_1 de la ventana actual contra una ventana
anterior equivalente y aplica ese crecimiento sobre la reserva base actual.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from variable_1 import DEFAULT_WINDOW_MONTHS, Variable1Result, calculate_rl_variable_1_for_window


@dataclass(frozen=True)
class Variable2Result:
    """Resultado completo del cálculo rolling de Liquidity Reserve."""

    rl_variable_1: float
    rl_variable_1_previous: float
    current_total_transacted: float
    previous_total_transacted: float
    growth: float
    amount_variable_2: float
    rl_accumulated_2: float
    current_window: Variable1Result
    previous_window: Variable1Result
    warning: str | None = None


def calculate_variable_2(
    data: pd.DataFrame,
    fecha_objetivo: str | pd.Timestamp,
    tipo_flujo: str,
    *,
    window_months: int = DEFAULT_WINDOW_MONTHS,
    coverage_threshold: float = 0.95,
) -> Variable2Result:
    """Calcula Variable 2 usando dos ventanas consecutivas de igual duración."""

    projection_date = pd.Timestamp(fecha_objetivo).normalize()

    current_start = projection_date - pd.DateOffset(months=window_months)
    current_end = projection_date - pd.DateOffset(days=1)

    previous_start = current_start - pd.DateOffset(months=6)
    previous_end = current_end - pd.DateOffset(months=6)

    current_result = calculate_rl_variable_1_for_window(
        data=data,
        window_start=current_start,
        window_end=current_end + pd.DateOffset(days=1),
        tipo_flujo=tipo_flujo,
        coverage_threshold=coverage_threshold,
    )
    previous_result = calculate_rl_variable_1_for_window(
        data=data,
        window_start=previous_start,
        window_end=previous_end + pd.DateOffset(days=1),
        tipo_flujo=tipo_flujo,
        coverage_threshold=coverage_threshold,
    )

    current_period_mask = (
        (pd.to_datetime(data["SETTLEMENT_DATE"]) >= current_start)
        & (pd.to_datetime(data["SETTLEMENT_DATE"]) <= current_end)
        & (data["DB_CR_FLAG"].astype(str).str.upper() == tipo_flujo)
    )
    previous_period_mask = (
        (pd.to_datetime(data["SETTLEMENT_DATE"]) >= previous_start)
        & (pd.to_datetime(data["SETTLEMENT_DATE"]) <= previous_end)
        & (data["DB_CR_FLAG"].astype(str).str.upper() == tipo_flujo)
    )

    current_total_transacted = (
        data.loc[current_period_mask, "PAYMT_PRTY_AMT"]
        .abs()
        .sum()
    )
    previous_total_transacted = (
        data.loc[previous_period_mask, "PAYMT_PRTY_AMT"]
        .abs()
        .sum()
    )

    current_rows = int(data.loc[current_period_mask].shape[0])
    previous_rows = int(data.loc[previous_period_mask].shape[0])

    print("\n=== VARIABLE 2 DEBUG ===")
    print(f"Current window start : {current_start.date()}")
    print(f"Current window end   : {current_end.date()}")
    print(f"Previous window start: {previous_start.date()}")
    print(f"Previous window end  : {previous_end.date()}")
    print(f"Rows in current period : {current_rows}")
    print(f"Rows in previous period: {previous_rows}")
    print(f"Sum abs PAYMT_PRTY_AMT current period : {float(current_total_transacted):,.2f}")
    print(f"Sum abs PAYMT_PRTY_AMT previous period: {float(previous_total_transacted):,.2f}")

    warning = None
    if previous_result.value == 0:
        if current_result.value == 0:
            growth = 0.0
        else:
            growth = float("nan")
            warning = (
                "No es posible calcular crecimiento porcentual porque "
                "RL_Variable_1 anterior es 0."
            )
    else:
       growth = (
                    current_total_transacted - previous_total_transacted
                   ) / previous_total_transacted

    # Aplicar crecimiento ajustado para cálculos de reserva (nunca negativo)
    if pd.isna(growth):
        applied_growth = 0.0
    else:
        applied_growth = max(growth, 0.0)

    amount_variable_2 = current_result.value * applied_growth
    rl_accumulated_2 = current_result.value + amount_variable_2

    return Variable2Result(
        rl_variable_1=current_result.value,
        rl_variable_1_previous=previous_result.value,
        current_total_transacted=float(current_total_transacted),

    previous_total_transacted=float(previous_total_transacted),
        growth=float(growth),
        amount_variable_2=float(amount_variable_2),
        rl_accumulated_2=float(rl_accumulated_2),
        current_window=current_result,
        previous_window=previous_result,
        warning=warning,
    )
