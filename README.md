# Liquidity Reserve Model

Modelo modular en Python para calcular Liquidity Reserve con datos históricos de liquidación desde `settlement_data.xlsx`.

## Estructura

- `main.py`: punto de entrada por consola, carga el Excel, ejecuta el modelo e imprime resultados.
- `variable_1.py`: calcula `RL_Variable_1` con máximos históricos absolutos por participante y cobertura acumulada del 95%.
- `variable_2.py`: calcula el crecimiento rolling, `Monto_Variable_2` y `RL_Acumulada_2`.
- `variable_3.py`: calcula ajuste macroeconómico usando IPoM, `Monto_Variable_3` y `RL_Acumulada_3`.
- `variable_4.py`: calcula impacto de feriados largos consecutivos, `Monto_Variable_4` y `RL_Acumulada_4`.
- `variable_5.py`: calcula buffer móvil dinámico basado en estrés de feriados, `RL_Final`.
- `requirements.txt`: dependencias mínimas del proyecto.

## Instalación

```bash
python -m pip install -r requirements.txt
```

## Uso

```bash
python main.py --fecha-objetivo 2025-12-31 --tipo-flujo ISSUING
```

También se puede indicar una ruta alternativa para el Excel:

```bash
python main.py --archivo settlement_data.xlsx --fecha-objetivo 2025-12-31 --tipo-flujo ACQUIRING
```

## Lógica implementada

### Variable 1

1. Filtra registros de los últimos 12 meses respecto a `fecha_objetivo`.
2. Filtra por `DB_CR_FLAG == tipo_flujo`.
3. Convierte `PAYMT_PRTY_AMT` a valor absoluto.
4. Agrupa por `MEMBER_ID`.
5. Obtiene el máximo histórico absoluto por participante.
6. Ordena de mayor a menor.
7. Calcula participación porcentual y cobertura acumulada.
8. Selecciona participantes hasta alcanzar el umbral de cobertura acumulada, por defecto 95%.
9. Calcula el promedio de los máximos seleccionados como `RL_Variable_1`.

### Variable 2

1. Calcula `RL_Variable_1` para la ventana actual de 12 meses.
2. Calcula `RL_Variable_1` para la ventana anterior equivalente de 12 meses.
3. Calcula crecimiento porcentual.
4. Aplica el crecimiento sobre `RL_Variable_1` actual para obtener `Monto_Variable_2`.
5. Suma `RL_Variable_1 + Monto_Variable_2` para obtener `RL_Acumulada_2`.

### Variable 3

1. Carga datos IPoM desde `ipom_data.xlsx`.
2. Selecciona la publicación IPoM más reciente anterior a `fecha_objetivo`.
3. Extrae IPC y Consumo para el año de proyección.
4. Calcula VarIndEcon = (IPC + Consumo) / 100.
5. Aplica VarIndEcon sobre `RL_Acumulada_2` para obtener `Monto_Variable_3`.
6. Suma `RL_Acumulada_2 + Monto_Variable_3` para obtener `RL_Acumulada_3`.

### Variable 4

1. Genera calendario operacional chileno usando holidays library (fines de semana + feriados).
2. Opcionalmente aplica overrides desde `operational_overrides.xlsx`.
3. Detecta la secuencia máxima de días no operacionales consecutivos para el año anterior y año de proyección.
4. Encuentra el primer día operacional después de la secuencia máxima del año anterior.
5. Filtra settlement amounts para ese día operacional y obtiene los top 3 montos más altos.
6. Calcula DailyAverage = Sum(Top3) / MaxConsecutiveHolidayDaysPriorYear.
7. Proyecta ProjectedAmount = DailyAverage * MaxConsecutiveHolidayDaysProjectionYear.
8. Calcula AdjustmentRL = ProjectedAmount * 5%.
9. Suma `RL_Acumulada_3 + AdjustmentRL` para obtener `RL_Acumulada_4`.

### Variable 5

1. Calcula RL_without_buffer = RL_Accumulated_4 - AdjustmentRL.
2. Calcula BufferMovil = AdjustmentRL / RL_without_buffer (como porcentaje).
3. Calcula RL_Final = RL_Accumulated_4 * (1 + BufferMovil).
4. Retorna RL sin buffer, ajuste RL de referencia, buffer móvil porcentaje, y RL final.
