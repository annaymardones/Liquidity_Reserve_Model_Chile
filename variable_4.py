"""Cálculo de la Variable 4 para Liquidity Reserve.

Variable 4 estima el impacto de periodos largos de feriados consecutivos
sobre la liquidez, considerando el estrés post-feriados.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import holidays
import pandas as pd


@dataclass(frozen=True)
class HolidaySequence:
    """Información de una secuencia de días no operacionales."""

    start_date: pd.Timestamp
    end_date: pd.Timestamp
    consecutive_days: int


@dataclass(frozen=True)
class Variable4Result:
    """Resultado completo del cálculo de Variable 4."""

    prior_year_max_sequence: HolidaySequence
    projection_year_max_sequence: HolidaySequence
    top_3_settlement_amounts: list[float]
    projected_amount: float
    rl_adjustment: float
    rl_accumulated_4: float


def generate_operational_calendar(
    year: int,
    operational_overrides_path: Optional[Path] = None
) -> set[pd.Timestamp]:
    """
    Genera calendario operacional chileno para un año específico.

    Incluye fines de semana y feriados chilenos, con posibilidad de overrides.
    """
    # Feriados chilenos
    chile_holidays = holidays.Chile(years=[year])

    # Días no operacionales base: fines de semana + feriados
    non_operational = set()

    # Agregar fines de semana
    start_date = pd.Timestamp(year, 1, 1)
    end_date = pd.Timestamp(year, 12, 31)

    current_date = start_date
    while current_date <= end_date:
        # Si es fin de semana (5=sábado, 6=domingo) o feriado
        if current_date.weekday() >= 5 or current_date in chile_holidays:
            non_operational.add(current_date)
        current_date += pd.Timedelta(days=1)

    # Aplicar overrides si existe el archivo
    if operational_overrides_path and operational_overrides_path.exists():
        try:
            overrides_df = pd.read_excel(operational_overrides_path)
            overrides_df['date'] = pd.to_datetime(overrides_df['date'])

            # Filtrar por año
            year_overrides = overrides_df[
                overrides_df['date'].dt.year == year
            ]

            for _, row in year_overrides.iterrows():
                override_date = row['date'].normalize()
                is_operational = row.get('is_operational', True)

                if is_operational:
                    # Remover de no operacionales si está marcado como operacional
                    non_operational.discard(override_date)
                else:
                    # Agregar a no operacionales si está marcado como no operacional
                    non_operational.add(override_date)

        except Exception as e:
            # Si hay error leyendo overrides, continuar sin ellos
            print(f"Warning: Could not read operational overrides: {e}")

    return non_operational


def find_max_consecutive_non_operational_days(
    non_operational_days: set[pd.Timestamp],
    year: int
) -> HolidaySequence:
    """
    Encuentra la secuencia máxima de días no operacionales consecutivos en un año.
    """
    if not non_operational_days:
        return HolidaySequence(
            start_date=pd.Timestamp(year, 1, 1),
            end_date=pd.Timestamp(year, 1, 1),
            consecutive_days=0
        )

    # Ordenar las fechas no operacionales
    sorted_days = sorted(non_operational_days)

    max_sequence = HolidaySequence(
        start_date=sorted_days[0],
        end_date=sorted_days[0],
        consecutive_days=1
    )

    current_sequence = HolidaySequence(
        start_date=sorted_days[0],
        end_date=sorted_days[0],
        consecutive_days=1
    )

    for i in range(1, len(sorted_days)):
        current_date = sorted_days[i]
        previous_date = sorted_days[i-1]

        # Si son consecutivos (diferencia de 1 día)
        if (current_date - previous_date).days == 1:
            current_sequence = HolidaySequence(
                start_date=current_sequence.start_date,
                end_date=current_date,
                consecutive_days=current_sequence.consecutive_days + 1
            )
        else:
            # Nueva secuencia
            current_sequence = HolidaySequence(
                start_date=current_date,
                end_date=current_date,
                consecutive_days=1
            )

        # Actualizar máximo si es necesario
        if current_sequence.consecutive_days > max_sequence.consecutive_days:
            max_sequence = current_sequence

    return max_sequence


def find_first_operational_day_after_sequence(
    sequence_end: pd.Timestamp,
    non_operational_days: set[pd.Timestamp]
) -> pd.Timestamp:
    """
    Encuentra el primer día operacional después de una secuencia de feriados.
    """
    current_date = sequence_end + pd.Timedelta(days=1)

    while current_date in non_operational_days:
        current_date += pd.Timedelta(days=1)

    return current_date


def get_top_3_settlement_amounts(
    settlement_data: pd.DataFrame,
    target_date: pd.Timestamp,
    flow_type: str
) -> list[float]:
    """
    Obtiene los 3 montos de settlement más altos por participante para una fecha específica.
    """
    # Filtrar por fecha y tipo de flujo
    filtered = settlement_data[
        (pd.to_datetime(settlement_data['SETTLEMENT_DATE']).dt.date == target_date.date()) &
        (settlement_data['DB_CR_FLAG'].str.upper() == flow_type.upper())
    ].copy()

    if filtered.empty:
        return [0.0, 0.0, 0.0]

    # Agregar por MEMBER_ID y obtener el máximo absoluto de PAYMT_PRTY_AMT
    participant_maxes = (
        filtered.assign(ABS_AMOUNT=filtered['PAYMT_PRTY_AMT'].abs())
        .groupby('MEMBER_ID', as_index=False)['ABS_AMOUNT']
        .max()
        .nlargest(3, 'ABS_AMOUNT')
    )

    # Extraer los top 3 máximos absolutos
    top_3 = participant_maxes['ABS_AMOUNT'].tolist()

    # Rellenar con 0s si hay menos de 3
    while len(top_3) < 3:
        top_3.append(0.0)

    return top_3


def calculate_variable_4(
    settlement_data: pd.DataFrame,
    fecha_objetivo: str | pd.Timestamp,
    tipo_flujo: str,
    rl_accumulated_3: float,
    operational_overrides_path: Optional[str | Path] = None
) -> Variable4Result:
    """
    Calcula Variable 4 basada en estrés post-feriados largos.
    """
    projection_date = pd.Timestamp(fecha_objetivo).normalize()
    projection_year = projection_date.year
    prior_year = projection_year - 1

    # Convertir path si es string
    overrides_path = Path(operational_overrides_path) if operational_overrides_path else None

    # Generar calendarios operacionales
    prior_year_non_operational = generate_operational_calendar(prior_year, overrides_path)
    projection_year_non_operational = generate_operational_calendar(projection_year, overrides_path)

    # Encontrar secuencias máximas
    prior_year_max_sequence = find_max_consecutive_non_operational_days(
        prior_year_non_operational, prior_year
    )
    projection_year_max_sequence = find_max_consecutive_non_operational_days(
        projection_year_non_operational, projection_year
    )

    # Encontrar primer día operacional después de la secuencia del año anterior
    first_operational_day = find_first_operational_day_after_sequence(
        prior_year_max_sequence.end_date, prior_year_non_operational
    )

    # Obtener top 3 montos de settlement para ese día
    top_3_amounts = get_top_3_settlement_amounts(
        settlement_data, first_operational_day, tipo_flujo
    )

    # Calcular promedio diario
    sum_top_3 = sum(top_3_amounts)
    daily_average = sum_top_3 / prior_year_max_sequence.consecutive_days

    # Proyectar monto
    projected_amount = daily_average * projection_year_max_sequence.consecutive_days

    # Calcular ajuste RL (5% del monto proyectado)
    rl_adjustment = projected_amount * 0.05

    # RL acumulada 4
    rl_accumulated_4 = rl_accumulated_3 + rl_adjustment

    return Variable4Result(
        prior_year_max_sequence=prior_year_max_sequence,
        projection_year_max_sequence=projection_year_max_sequence,
        top_3_settlement_amounts=top_3_amounts,
        projected_amount=projected_amount,
        rl_adjustment=rl_adjustment,
        rl_accumulated_4=rl_accumulated_4
    )