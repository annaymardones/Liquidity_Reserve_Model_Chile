"""Punto de entrada del modelo de Liquidity Reserve.

Ejemplo de uso:
    python main.py --fecha-objetivo 2025-12-31 --tipo-flujo ISSUING
"""

from __future__ import annotations

import argparse
from pathlib import Path
from py_compile import main
from unittest import result

import pandas as pd

from variable_2 import Variable2Result, calculate_variable_2
from variable_3 import calculate_variable_3
from variable_4 import calculate_variable_4
from variable_5 import calculate_variable_5


DEFAULT_SOURCE_FILE = "settlement_data.xlsx"


def parse_args() -> argparse.Namespace:
    """Define y parsea los inputs del usuario desde consola."""

    parser = argparse.ArgumentParser(description="Modelo de cálculo de Liquidity Reserve.")
    parser.add_argument(
        "--archivo",
        default=DEFAULT_SOURCE_FILE,
        help=f"Ruta del Excel fuente. Default: {DEFAULT_SOURCE_FILE}",
    )
    parser.add_argument(
        "--fecha-objetivo",
        required=True,
        help="Fecha objetivo del cálculo en formato YYYY-MM-DD.",
    )
    parser.add_argument(
        "--tipo-flujo",
        required=True,
        type=str.upper,
        choices=["ISSUING", "ACQUIRING"],
        help="Tipo de flujo a evaluar.",
    )
    parser.add_argument(
        "--umbral-cobertura",
        type=float,
        default=0.95,
        help="Cobertura acumulada requerida para Variable 1. Default: 0.95.",
    )
    return parser.parse_args()


def build_summary_table(result: Variable2Result) -> pd.DataFrame:
    """Construye la tabla final resumen solicitada."""

    return pd.DataFrame(
        [
           
            {
            "Variable": "Total_Periodo_Anterior",
            "Valor": result.previous_total_transacted,
        },
        {
            "Variable": "Total_Periodo_Actual",
            "Valor": result.current_total_transacted,
        },
        {
            "Variable": "Variacion_Variable_2",
            "Valor": f"{result.growth:.2%}",
        },
        {
            "Variable": "RL_Variable_1",
            "Valor": f"{result.rl_variable_1:,.0f}",
        },
        {
            "Variable": "Monto_Variable_2",
            "Valor": f"{result.amount_variable_2:,.0f}",
        },
        {
            "Variable": "RL_Acumulada_2",
            "Valor": f"{result.rl_accumulated_2:,.0f}",
        },
    ]
)


def print_variable_1_detail(result: Variable2Result) -> None:
    """Imprime tabla detallada de Variable 1 con desglose por participante."""
    
    current = result.current_window
    
    if current.participant_summary.empty:
        print("\n=== VARIABLE 1 DETAIL ===")
        print("No hay participantes en la ventana actual.")
        return
    
    # Crear dataframe con información detallada
    detail_df = current.participant_summary.copy()
    
    # Determinar cuáles participantes fueron seleccionados
    selected_member_ids = set(current.selected_participants["MEMBER_ID"].values)
    detail_df["INCLUDED"] = detail_df["MEMBER_ID"].isin(selected_member_ids).apply(
        lambda x: "YES" if x else "NO"
    )
    
    # Seleccionar y renombrar columnas
    display_df = detail_df[["MEMBER_ID", "MAX_HISTORICAL_ABS", "PARTICIPATION_PCT", "CUMULATIVE_COVERAGE_PCT", "INCLUDED"]].copy()
    display_df.columns = ["MEMBER_ID", "MAX_ABS_PAYMT_PRTY_AMT", "CONTRIBUTION_PCT", "CUMULATIVE_PCT", "INCLUDED"]
    
    # Imprimir tabla
    print("\n=== VARIABLE 1 DETAIL ===")
    
    # Formatear para impresión
    output_df = display_df.copy()
    output_df["MAX_ABS_PAYMT_PRTY_AMT"] = display_df["MAX_ABS_PAYMT_PRTY_AMT"].apply(lambda x: f"{x:,.0f}")
    output_df["CONTRIBUTION_PCT"] = display_df["CONTRIBUTION_PCT"].apply(lambda x: f"{x:.4%}")
    output_df["CUMULATIVE_PCT"] = display_df["CUMULATIVE_PCT"].apply(lambda x: f"{x:.4%}")
    
    print(output_df.to_string(index=False))
    
    # Imprimir línea de resumen
    final_cumulative_pct = current.participant_summary.iloc[current.participants_selected - 1]["CUMULATIVE_COVERAGE_PCT"] if current.participants_selected > 0 else 0.0
    print("\n--- Summary ---")
    print(f"Total Selected Participants: {current.participants_selected}/{current.participants_total}")
    print(f"Final Cumulative Coverage: {final_cumulative_pct:.4%}")
    print(f"RL Variable 1 Result: {current.value:,.0f}")
     


def print_results(result: Variable2Result) -> None:
    """Imprime resultados y diagnósticos principales en consola."""

    current = result.current_window
    previous = result.previous_window
    summary = build_summary_table(result)

    print("\n=== Liquidity Reserve Model ===")
    print(f"Tipo de flujo: {current.flow_type}")
    print(f"Ventana actual: {current.window_start.date()} < fecha <= {current.window_end.date()}")
    print(f"Ventana anterior: {previous.window_start.date()} < fecha <= {previous.window_end.date()}")
    print(f"Participantes actuales seleccionados: {current.participants_selected}/{current.participants_total}")
    print(f"Umbral de cobertura: {current.coverage_threshold:.2%}")

    if result.warning:
        print(f"\nADVERTENCIA: {result.warning}")

    print("\n--- Tabla final resumen ---")
    pd.options.display.float_format = '{:,.0f}'.format
    print(summary.to_string(index=False))

    print("\n--- Participantes seleccionados Variable 1 actual ---")
    if current.selected_participants.empty:
        print("No hay participantes seleccionados para la ventana actual.")
    else:
        print(current.selected_participants.to_string(index=False))   

def main() -> None:
    print("MAIN EJECUTANDO")

    args = parse_args()
    source_path = Path(args.archivo)

    if not source_path.exists():
        raise FileNotFoundError(f"No se encontró el archivo fuente: {source_path}")

    settlement_data = pd.read_excel(source_path)

    result_v2 = calculate_variable_2(
        data=settlement_data,
        fecha_objetivo=args.fecha_objetivo,
        tipo_flujo=args.tipo_flujo,
        coverage_threshold=args.umbral_cobertura,
    )

    ipom_data = pd.read_excel("ipom_data.xlsx")

    result_v3 = calculate_variable_3(
        data=ipom_data,
        fecha_objetivo=args.fecha_objetivo,
        rl_accumulated_2=result_v2.rl_accumulated_2,
    )

    result_v4 = calculate_variable_4(
        settlement_data=settlement_data,
        fecha_objetivo=args.fecha_objetivo,
        tipo_flujo=args.tipo_flujo,
        rl_accumulated_3=result_v3.rl_accumulated_3,
    )

    result_v5 = calculate_variable_5(
        rl_accumulated_4=result_v4.rl_accumulated_4,
        rl_adjustment=result_v4.rl_adjustment,
    )
    print_variable_1_detail(result_v2)
    print("\n=== VARIABLE 2 ===")
    print(f"Total Periodo Anterior: {result_v2.previous_total_transacted:,.0f}")
    print(f"Total Periodo Actual: {result_v2.current_total_transacted:,.0f}")
    print(f"Variacion Variable 2: {result_v2.growth:.2%}")
    print(f"Monto Variable 2: {result_v2.amount_variable_2:,.0f}")
    print("\n=== RL Acumulada hasta la VARIABLE 2 ===")
    print(f"RL Acumulada 2: {result_v2.rl_accumulated_2:,.0f}")

    print("\n=== VARIABLE 3 ===")
    print(f"Fecha IPoM seleccionada: {result_v3.selected_ipom_date}")
    print(f"Año proyección: {result_v3.projection_year}")
    print(f"IPC: {result_v3.ipc}")
    print(f"Consumo: {result_v3.consumo}")
    print(f"VarIndEcon: {result_v3.var_ind_econ:.2%}")
    print(f"Monto Variable 3: {result_v3.monto_variable_3:,.0f}")
    print("\n=== RL Acumulada hasta la VARIABLE 3 ===")
    print(f"RL Acumulada 3: {result_v3.rl_accumulated_3:,.0f}")

    print("\n=== VARIABLE 4 ===")
    print(f"Secuencia máxima año anterior: {result_v4.prior_year_max_sequence.start_date.date()} - {result_v4.prior_year_max_sequence.end_date.date()} ({result_v4.prior_year_max_sequence.consecutive_days} días)")
    print(f"Secuencia máxima año proyección: {result_v4.projection_year_max_sequence.start_date.date()} - {result_v4.projection_year_max_sequence.end_date.date()} ({result_v4.projection_year_max_sequence.consecutive_days} días)")
    print(f"Top 3 montos settlement: {', '.join([f'{amt:,.0f}' for amt in result_v4.top_3_settlement_amounts])}")
    print(f"Monto proyectado: {result_v4.projected_amount:,.0f}")
    print(f"Ajuste RL: {result_v4.rl_adjustment:,.0f}")
    print("\n=== RL Acumulada hasta la VARIABLE 4 ===")
    print(f"RL Acumulada 4: {result_v4.rl_accumulated_4:,.0f}")

    print("\n=== VARIABLE 5 ===")
    print(f"RL sin buffer: {result_v5.rl_without_buffer:,.0f}")
    print(f"Ajuste RL (referencia): {result_v5.rl_adjustment:,.0f}")
    print(f"Buffer Móvil: {result_v5.buffer_movil_pct:.2%}")
    print("\n=== LIQUIDITY RESERVE FINAL ===")
    print(f"RL Final: {result_v5.rl_final:,.0f}")


if __name__ == "__main__":
    main()       
