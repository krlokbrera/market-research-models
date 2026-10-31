# Configuración

Los archivos JSON contienen exactamente las claves siguientes. No aceptan código, rutas de secretos ni claves API. Todos los números deben ser finitos; los booleanos no se aceptan como números.

| Parámetro | Significado y unidades |
| --- | --- |
| benchmark | Identificador existente en el CSV |
| annualization | 252 observaciones para sesiones o 365 para calendario diario |
| target_vol | Volatilidad anual objetivo estimada, en tanto por uno; positiva y hasta 5 |
| cap | Peso máximo de cada activo, entre 0 exclusivo y 1 incluido |
| top_n | Número máximo de activos, entero entre 1 y 256 |
| rebalance | monthly o weekly |
| commission_eur | Coste fijo por orden simulada, EUR |
| spread_bps | Spread completo; el motor aplica la mitad por lado |
| slippage_bps | Deslizamiento por lado, puntos básicos |
| fx_bps | Conversión de moneda por lado, puntos básicos |
| fee_bps | Comisión proporcional adicional por lado, puntos básicos |
| min_trade_eur | Importe mínimo para simular una operación |
| cash_rate | Tasa anual fija de caja como supuesto, de 0 a 1 |

Un punto básico equivale a 0,01%. El coste variable por lado es:
(spread_bps / 2 + slippage_bps + fx_bps + fee_bps) / 10.000.

## Perfiles iniciales

| Parámetro | Tradicional | Cripto |
| --- | --- | --- |
| benchmark | SPY | BTC-USD |
| annualization | 252 | 365 |
| target_vol | 0,10 | 0,20 |
| cap | 0,35 | 0,50 |
| top_n | 3 | 2 |
| rebalance | monthly | weekly |
| commission_eur | 1 | 0 |
| spread_bps | 4 | 20 |
| slippage_bps | 3 | 15 |
| fx_bps | 10 | 0 |
| fee_bps | 0 | 25 |
| min_trade_eur | 25 | 10 |
| cash_rate | 0 | 0 |

Estos valores son hipótesis ilustrativas, no tarifas verificadas, una asignación personalizada o parámetros optimizados.

Si aportas precios de vehículos negociados en EUR, revisa si procede aplicar fx_bps. La moneda de cotización no elimina la exposición económica a otras divisas.

No se redistribuye automáticamente todo el saldo tras aplicar límites y control de volatilidad: la cartera puede conservar caja. No se resta un TER adicional si el coste del vehículo ya está implícito en su serie histórica.

La comisión fija se aplica por orden. El capital de un bloque cripto es independiente del capital asignado al bloque tradicional.
