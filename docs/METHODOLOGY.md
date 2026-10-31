# Metodología

## Momentum y asignación

Tradicional: P[t-21] / P[t-252] - 1. Cripto: P[t-30] / P[t-365] - 1. Se exige momentum positivo y precio por encima de la media de 200 observaciones.

Se seleccionan hasta top_n activos. Los pesos iniciales son inversos a su volatilidad de 63 observaciones, limitados por cap. La matriz de covarianzas reciente determina si es necesario reducirlos para respetar la volatilidad objetivo estimada. El resto queda en caja.

No es una optimización de contribuciones iguales al riesgo ni una garantía de volatilidad futura.

## Ridge temporal

Variables: momentum a 21, 63 y 126 observaciones, volatilidad a 21 y distancia a SMA200. Objetivo: retorno a 21 observaciones.

Se fija alpha=10. La estandarización se ajusta solo con los datos de entrenamiento, con ventana máxima de 1.260 observaciones y al menos 252 ejemplos completos. Se purgan 21 observaciones para que la etiqueta haya terminado estrictamente antes del instante del ajuste.

No se genera una señal válida hasta disponer de entrenamiento. Las predicciones superiores al 0,3%, sujetas al filtro de tendencia, se utilizan para seleccionar posiciones. El umbral es una hipótesis de investigación.

## Ejecución y comparación

Una señal formada al cierre t se ejecuta al cierre t+1 después del retorno de ese día. La nueva posición captura retornos posteriores. Se descuentan costes, se venden posiciones antes de comprar y se limita la compra al saldo disponible.

Se compara con comprar y mantener el benchmark y una cartera equiponderada inicial en el mismo intervalo posterior al entrenamiento de ambos modelos. Se añade sensibilidad al doble de costes.

Las unidades de cartera son fracciones de retorno total, no cantidades de acciones para enviar a un intermediario. La caja usa una tasa fija configurable, no una curva histórica reconstruida.

## Métricas y escenarios

CAGR, volatilidad anualizada, Sharpe frente a la caja supuesta, drawdown desde el capital inicial, expected shortfall diario empírico al 95%, costes y volumen negociado anualizado.

El resumen de riesgo añade EWMA de retornos cuadrados con alpha=0,06. El bootstrap usa bloques de 21 sesiones o 7 días según calendario. Es una distribución condicionada a las observaciones; no representa una probabilidad objetiva de ganancias ni un pronóstico de pérdidas extremas nuevas.

## Evento cripto

Para activos distintos del benchmark se estima un modelo de retorno logarítmico frente a este. El propio benchmark se compara con su media previa.

Se usan los 120 días anteriores, excluyendo los 10 inmediatos, con al menos 60 observaciones completas. Las ventanas son 0, 0–1, 0–3 y 0–7 días. Una ventana incompleta permanece ausente.

Es un análisis descriptivo sobre cierres diarios alineados. Un solo evento no identifica un efecto causal; las barras diarias mezclan horas anteriores y posteriores.

## Flujos

robust_flow_z compara la observación actual con una mediana y MAD exclusivamente pasadas, por defecto 52 observaciones y un mínimo de 26. Cinco observaciones no bastan para producir una señal. Una MAD cero produce ausencia de valor, no una división artificial.

## Límites

No se ha validado una ventaja con históricos reales en esta publicación. Elegir universo y diseño introduce sesgos; los datos ajustados actuales pueden incluir revisiones y no equivalen a una base point-in-time. Los resultados dependen de costes, calidad del dato y fecha en que cada observación era conocida.

No se modelan impuestos personales, aportaciones, retiradas, restricciones de liquidez, insolvencia del custodio, financiación, staking ni derivados. La investigación necesita validación fuera de muestra y revisión del contexto antes de cualquier uso financiero.
