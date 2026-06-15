"""Cálculo de la Variable 1 para Liquidity Reserve.

La Variable 1 estima una reserva base usando los máximos históricos absolutos
por participante dentro de una ventana móvil de 12 meses y conserva los
participantes necesarios para cubrir el 95% del total acumulado.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


REQUIRED_COLUMNS = {"MEMBER_ID", "SETTLEMENT_DATE", "PAYMT_PRTY_AMT", "DB_CR_FLAG"}
DEFAULT_COVERAGE_THRESHOLD = 0.95
DEFAULT_WINDOW_MONTHS = 12


@dataclass(frozen=True)
class Variable1Result:
    """Resultado completo del cálculo de RL_Variable_1."""

    value: float
    total_transacted: float
    window_start: pd.Timestamp
    window_end: pd.Timestamp
    flow_type: str
    coverage_threshold: float
    total_transacted: float
    participants_total: int
    participants_selected: int
    participant_summary: pd.DataFrame
    selected_participants: pd.DataFrame


def validate_required_columns(columns: Iterable[str]) -> None:
    """Valida que el dataset contenga las columnas mínimas requeridas."""

    missing_columns = REQUIRED_COLUMNS.difference(columns)
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
    """Prepara tipos de datos necesarios para los cálculos financieros."""

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


def calculate_rl_variable_1(
    data: pd.DataFrame,
    fecha_objetivo: str | pd.Timestamp,
    tipo_flujo: str,
    *,
    window_months: int = DEFAULT_WINDOW_MONTHS,
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
) -> Variable1Result:
    """Calcula RL_Variable_1 para los últimos ``window_months`` meses."""

    window_end = pd.Timestamp(fecha_objetivo).normalize()
    window_start = window_end - pd.DateOffset(months=window_months)
    return calculate_rl_variable_1_for_window(
        data=data,
        window_start=window_start,
        window_end=window_end,
        tipo_flujo=tipo_flujo,
        coverage_threshold=coverage_threshold,
    )


def calculate_rl_variable_1_for_window(
    data: pd.DataFrame,
    window_start: str | pd.Timestamp,
    window_end: str | pd.Timestamp,
    tipo_flujo: str,
    *,
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
) -> Variable1Result:
    """Calcula RL_Variable_1 para una ventana específica.

    La ventana usa límite inferior abierto y límite superior cerrado:
    ``window_start < SETTLEMENT_DATE <= window_end``. Esta convención evita
    solapamientos cuando se compara la ventana actual contra la anterior.
    """

    if not 0 < coverage_threshold <= 1:
        raise ValueError("coverage_threshold debe estar entre 0 y 1.")

    prepared = prepare_settlement_data(data)
    flow_type = normalize_flow_type(tipo_flujo)
    start = pd.Timestamp(window_start).normalize()
    end = pd.Timestamp(window_end).normalize()
    if start >= end:
        raise ValueError("window_start debe ser menor que window_end.")

    filtered = prepared.loc[
        (prepared["SETTLEMENT_DATE"] >= start)
        & (prepared["SETTLEMENT_DATE"] < end)
        & (prepared["DB_CR_FLAG"] == flow_type)
    ].copy()
    filtered["ABS_PAYMT_PRTY_AMT"] = filtered["PAYMT_PRTY_AMT"].abs()
    daily_net_positions = (
    filtered.groupby(
        ["SETTLEMENT_DATE"],
        as_index=False
    )["PAYMT_PRTY_AMT"]
    .sum()
)

    daily_net_positions["ABS_NET_POSITION"] = (
    daily_net_positions["PAYMT_PRTY_AMT"].abs()
)

    participant_summary = (
        filtered.groupby("MEMBER_ID", as_index=False)["ABS_PAYMT_PRTY_AMT"]
        .max()
        .rename(columns={"ABS_PAYMT_PRTY_AMT": "MAX_HISTORICAL_ABS"})
        .sort_values("MAX_HISTORICAL_ABS", ascending=False)
        .reset_index(drop=True)
    )

    if participant_summary.empty or participant_summary["MAX_HISTORICAL_ABS"].sum() == 0:
        participant_summary["PARTICIPATION_PCT"] = 0.0
        participant_summary["CUMULATIVE_COVERAGE_PCT"] = 0.0
        return Variable1Result(
            value=0.0,
            window_start=start,
            window_end=end,
            flow_type=flow_type,
            coverage_threshold=coverage_threshold,
            total_transacted=float(daily_net_positions["ABS_NET_POSITION"].sum()),
            participants_total=len(participant_summary),
            participants_selected=0,
            participant_summary=participant_summary,
            selected_participants=participant_summary.head(0).copy(),
        )

    total_maxima = participant_summary["MAX_HISTORICAL_ABS"].sum()
    participant_summary["PARTICIPATION_PCT"] = participant_summary["MAX_HISTORICAL_ABS"] / total_maxima
    participant_summary["CUMULATIVE_COVERAGE_PCT"] = participant_summary["PARTICIPATION_PCT"].cumsum()

    # Incluye el primer participante que permite alcanzar o superar el umbral.
    coverage_reached = participant_summary["CUMULATIVE_COVERAGE_PCT"].ge(coverage_threshold)
    selected_count = int((participant_summary["CUMULATIVE_COVERAGE_PCT"] <= coverage_threshold).sum())
    selected_participants = participant_summary.head(selected_count).copy()
    rl_variable_1 = float(selected_participants["MAX_HISTORICAL_ABS"].mean())

    return Variable1Result(
        value=rl_variable_1,
        window_start=start,
        window_end=end,
        flow_type=flow_type,
        coverage_threshold=coverage_threshold,
        total_transacted=float(daily_net_positions["ABS_NET_POSITION"].sum()),
        participants_total=len(participant_summary),
        participants_selected=selected_count,
        participant_summary=participant_summary,
        selected_participants=selected_participants,
    )
