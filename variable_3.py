"""Cálculo de la Variable 3 para Liquidity Reserve.

Variable 3 aplica un ajuste macroeconómico sobre RL_Acumulada_2 utilizando los
indicadores IPC y Consumo de la última IPoM publicada antes de la fecha objetivo.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = {"fecha_ipom", "anio", "ipc", "consumo"}


@dataclass(frozen=True)
class Variable3Result:
    """Resultado completo del cálculo de Variable 3."""

    selected_ipom_date: pd.Timestamp
    projection_year: int
    ipc: float
    consumo: float
    var_ind_econ: float
    monto_variable_3: float
    rl_accumulated_3: float


def validate_ipom_columns(columns: pd.Index) -> None:
    """Valida que las columnas requeridas existan en el dataset IPoM."""

    missing = REQUIRED_COLUMNS.difference(columns)
    if missing:
        raise ValueError(
            f"El archivo IPoM no contiene las columnas requeridas: {', '.join(sorted(missing))}"
        )


def calculate_variable_3(
    data: pd.DataFrame,
    fecha_objetivo: str | pd.Timestamp,
    rl_accumulated_2: float,
) -> Variable3Result:
    """Calcula Variable 3 usando la última IPoM previa a la fecha objetivo."""
    data = data.rename(columns={
    "año": "anio",
    "Año": "anio",
})

    validate_ipom_columns(data.columns)

    ipom = data.copy()
    ipom["fecha_ipom"] = pd.to_datetime(ipom["fecha_ipom"], errors="coerce")
    ipom["anio"] = pd.to_numeric(ipom["anio"], errors="coerce").astype("Int64")
    ipom["ipc"] = pd.to_numeric(ipom["ipc"], errors="coerce")
    ipom["consumo"] = pd.to_numeric(ipom["consumo"], errors="coerce")

    projection_date = pd.Timestamp(fecha_objetivo).normalize()
    projection_year = int(projection_date.year)

    published_before = ipom.loc[ipom["fecha_ipom"] < projection_date].copy()
    if published_before.empty:
        raise ValueError(
            "No se encontró ninguna IPoM publicada antes de la fecha objetivo."
        )

    latest_publication_date = published_before["fecha_ipom"].max()
    selected_ipom = published_before.loc[
        published_before["fecha_ipom"] == latest_publication_date
    ]

    row = selected_ipom.loc[selected_ipom["anio"] == projection_year]
    if row.empty:
        raise ValueError(
            f"No se encontró un registro IPoM para el año de proyección {projection_year} "
            f"en la última publicación ({latest_publication_date.date()})."
        )

    ipc = float(row["ipc"].iloc[0])
    consumo = float(row["consumo"].iloc[0])
    var_ind_econ =(ipc + consumo)/100
    monto_variable_3 = float(rl_accumulated_2) * var_ind_econ
    rl_accumulated_3 = float(rl_accumulated_2) + monto_variable_3

    return Variable3Result(
        selected_ipom_date=latest_publication_date,
        projection_year=projection_year,
        ipc=ipc,
        consumo=consumo,
        var_ind_econ=var_ind_econ,
        monto_variable_3=monto_variable_3,
        rl_accumulated_3=rl_accumulated_3,
    )
