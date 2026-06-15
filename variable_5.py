"""Cálculo de la Variable 5 para Liquidity Reserve.

Variable 5 implementa un buffer móvil dinámico basado en el estrés de feriados
operacionales de la Variable 4, representando una reserva prudencial de liquidez.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Variable5Result:
    """Resultado completo del cálculo de Variable 5."""

    rl_without_buffer: float
    rl_adjustment: float
    buffer_movil_pct: float
    rl_final: float


def calculate_variable_5(
    rl_accumulated_4: float,
    rl_adjustment: float,
) -> Variable5Result:
    """
    Calcula Variable 5: buffer móvil dinámico basado en estrés de feriados.

    Args:
        rl_accumulated_4: RL acumulada hasta Variable 4
        rl_adjustment: Ajuste RL de Variable 4 (estrés de feriados)

    Returns:
        Variable5Result con los cálculos del buffer móvil
    """
    # RL sin buffer es RL acumulada 4 (ya incluye el ajuste de feriados)
    rl_without_buffer = rl_accumulated_4

    # Calcular buffer móvil como porcentaje
    if rl_accumulated_4 == 0:
        buffer_movil_pct = 0.0
    else:
        buffer_movil_pct = rl_adjustment / rl_accumulated_4

    # Calcular RL final con buffer aplicado
    rl_final = rl_accumulated_4 * (1 + buffer_movil_pct)

    return Variable5Result(
        rl_without_buffer=rl_without_buffer,
        rl_adjustment=rl_adjustment,
        buffer_movil_pct=buffer_movil_pct,
        rl_final=rl_final
    )