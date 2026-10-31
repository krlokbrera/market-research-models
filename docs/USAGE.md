# Guía de uso

Ejecuta todos los comandos desde la raíz del repositorio, tras instalar con pip install -e . dentro de un entorno virtual.

## Entradas

Cada CSV debe tener una cabecera date seguida de uno o más identificadores de activos, hasta un máximo de 256 columnas de precios. El benchmark configurado debe existir para el backtest y el estudio de evento.

- Fechas diarias ISO YYYY-MM-DD, sin hora ni zona horaria.
- Filas únicas, en orden ascendente.
- Precios numéricos, positivos y finitos; no se imputan huecos.
- Encabezados únicos y con identificadores seguros; no nombres de personas, cuentas o fórmulas.
- Tamaño máximo de entrada: 100 MiB.
- Para comparar modelos hacen falta al menos 600 observaciones comunes y suficiente historia para el entrenamiento.
- Para cripto y el estudio de evento: calendario diario completo, incluidos fines de semana.

Usa cierres ajustados por splits y distribuciones para aproximar retornos totales. No mezcles monedas dentro de una matriz. El paquete no descarga ni convierte divisas.

Para métricas monetarias expresadas en EUR aporta precios en EUR y configura los costes de divisa que correspondan. Para el estudio de evento puedes usar USD si todos los activos comparten esa divisa y el cierre diario UTC.

## Demostración tradicional

```powershell
python -m market_models example --market traditional --output inputs/synthetic_traditional.csv
python -m market_models backtest --prices inputs/synthetic_traditional.csv --config config/traditional.json --capital 3000 --output outputs/traditional --data-label synthetic
```

El archivo es sintético, reproducible y no representa el comportamiento de SPY aunque se utilice ese identificador como benchmark de la demostración. El generador no reemplaza un archivo existente.

## Demostración cripto

```powershell
python -m market_models example --market crypto --output inputs/synthetic_crypto.csv
python -m market_models backtest --prices inputs/synthetic_crypto.csv --config config/crypto.json --capital 300 --output outputs/crypto --data-label synthetic
python -m market_models risk --prices inputs/synthetic_crypto.csv --config config/crypto.json --data-label synthetic
python -m market_models event --prices inputs/synthetic_crypto.csv --config config/crypto.json --event-date 2023-10-29 --data-label synthetic
```

El evento de este ejemplo es una fecha arbitraria sobre precios sintéticos. No es evidencia sobre un incidente real.

## Ejecutar con datos propios

```powershell
python -m market_models backtest --prices inputs/prices_eur.csv --config config/traditional.json --capital 3000 --asof 2026-10-31
```

--asof excluye esa fecha y todas las posteriores. Por defecto usa el día UTC actual. El usuario debe comprobar que los precios previos sean cierres completos.

## Salidas locales

Cada ejecución crea un subdirectorio nuevo bajo --output, con fecha UTC y un identificador aleatorio. No se reutiliza una carpeta anterior.

El backtest genera:
- Libro diario, operaciones y costes por estrategia.
- Pesos objetivo y predicciones de los modelos.
- metrics.json con rendimiento, riesgo, costes y sensibilidad al doble de costes.
- run_manifest.json con versión del paquete, parámetros, intervalo, etiqueta del dato y hash del archivo de entrada.

risk produce risk.csv; event produce event.csv. Una ventana de evento incompleta queda vacía, no como cero. Los resultados se escriben en local y no se transmiten.

No agregues datos o resultados al repositorio. El hash identifica el archivo exacto y no garantiza la calidad o legitimidad de su fuente.

## Funciones de biblioteca

```python
from market_models.models import robust_flow_z, event_study

# flows es una serie numérica ya preparada por el usuario.
z = robust_flow_z(flows, window=52, min_obs=26)

# prices usa cierres diarios alineados; ninguna función descarga datos.
events = event_study(prices, event_date="2026-10-29", benchmark="BTC-USD")
```

Los flujos publicados deben alinearse por la fecha en que se conocieron. El paquete no reconstruye revisiones, metadatos o calendarios de publicación.
