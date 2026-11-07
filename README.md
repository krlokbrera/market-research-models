# Market Research Models

Modelos cuantitativos locales para mercado tradicional y cripto, con configuración separada y una interfaz de línea de comandos.

Este repositorio contiene **solo código de modelos, configuración, documentación y pruebas sintéticas**. No incluye informes de inversión, históricos de mercado, resultados de cartera, credenciales ni conectores a cuentas o APIs. No realiza solicitudes de red, telemetría ni operaciones financieras.

## Modelos incluidos

- Momentum 12–1 con filtro de tendencia SMA200.
- Asignación inversa a volatilidad, límites por activo y control de riesgo de cartera.
- Regresión Ridge con ajuste temporal, estandarización en entrenamiento y purga de etiquetas.
- Simulación con costes, caja y ejecución diferida.
- Comparación con comprar y mantener y equiponderación inicial.
- Volatilidad, EWMA, drawdown, Sharpe y expected shortfall.
- Escenarios por bootstrap de bloques.
- Estudio de evento respecto a un benchmark cripto.
- Z-score robusto de flujos como función de biblioteca.

Los modelos son herramientas de investigación. Las pruebas sintéticas verifican el comportamiento del software y no acreditan rentabilidad con datos reales.

## Estructura

| Ruta | Contenido |
| --- | --- |
| src/market_models/models.py | Modelos y simulación |
| src/market_models/cli.py | Validación, carga local y ejecución |
| config/traditional.json | Parámetros del mercado tradicional |
| config/crypto.json | Parámetros independientes de cripto |
| docs/USAGE.md | Formato de datos y guía de ejecución |
| docs/CONFIGURATION.md | Parámetros y unidades |
| docs/METHODOLOGY.md | Ecuaciones, calendario y límites |
| docs/SECURITY.md | Tratamiento de datos y credenciales |
| tests/ | Validación con series sintéticas |

## Instalar

Python 3.11 o 3.12.

```powershell
git clone https://github.com/krlokbrera/market-research-models.git
cd market-research-models
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

En Linux/macOS sustituye el ejecutable por .venv/bin/python. No es necesario activar el entorno ni cambiar la política de ejecución de PowerShell.

## Demostración sin datos de mercado

```powershell
.\.venv\Scripts\python.exe -m market_models example --output inputs/synthetic_traditional.csv --market traditional
.\.venv\Scripts\python.exe -m market_models backtest --prices inputs/synthetic_traditional.csv --config config/traditional.json --capital 3000 --output outputs/traditional --data-label synthetic
```

El generador usa precios sintéticos y se niega a sobrescribir un archivo existente. Los resultados van a una carpeta nueva por ejecución, ignorada por Git.

## Usar tus propios precios

```powershell
.\.venv\Scripts\python.exe -m market_models backtest --prices inputs/prices_eur.csv --config config/traditional.json --capital 3000 --asof 2026-10-31
.\.venv\Scripts\python.exe -m market_models risk --prices inputs/crypto_prices_eur.csv --config config/crypto.json --asof 2026-10-31
.\.venv\Scripts\python.exe -m market_models event --prices inputs/crypto_prices_usd.csv --config config/crypto.json --event-date 2026-10-29 --asof 2026-10-31
```

Formato CSV: date y una columna por activo. Fechas YYYY-MM-DD únicas y ascendentes; precios positivos, finitos y ajustados. Los backtests monetarios esperan precios en EUR; el estudio de evento espera cierres diarios UTC comparables en una misma divisa. Consulta la [guía de datos](docs/USAGE.md) antes de ejecutar.

El corte --asof es exclusivo. Si se omite, se excluye el día UTC actual para evitar barras incompletas.

## Configurar

Edita una copia de config/traditional.json o config/crypto.json y pásala mediante --config. Se rechazan claves desconocidas, valores no finitos y parámetros fuera de rango.

[Guía de configuración](docs/CONFIGURATION.md) · [Metodología](docs/METHODOLOGY.md) · [Seguridad y datos](docs/SECURITY.md).

## Seguridad y gestión de datos

- Ninguna credencial es necesaria o procesada por este paquete.
- Los archivos de entrada se leen localmente; no se suben ni se modifican.
- Datos, resultados, cachés y archivos de secretos están excluidos en .gitignore.
- El manifiesto de cada ejecución conserva parámetros y un hash SHA-256 del archivo de entrada; no incluye su ruta.
- Los identificadores de activos se validan para evitar encabezados con fórmulas al exportar CSV.
- No se usa pickle, eval, ejecución de comandos o carga de código desde la configuración.

El ignore no sustituye una revisión antes de publicar. Mantén fuera del repositorio los datos personales o sujetos a licencias. Los manifiestos y resultados también pueden contener información sensible de una investigación: se guardan solo en local.

## Estado y límites

La lógica se ha probado con series sintéticas. No se publica un historial de rentabilidad real ni se afirma que un modelo supere al mercado.

El universo elegido puede introducir sesgo de selección. El backtest usa unidades fraccionarias de retorno total, costes supuestos y caja sin deuda; no incorpora impuestos personales, aportaciones, pérdidas por custodia, financiación, staking o derivados. Una volatilidad objetivo no limita las pérdidas. Los escenarios de bootstrap no son probabilidades objetivas del futuro.


## Radar sectorial dinamico

El filtro compara ETF sectoriales en EUR y conserva seis sectores como baseline de observacion. La configuracion incluye 13 representantes; la lista destacada puede incorporar o retirar sectores cada semana, con umbrales de entrada/salida y motivos auditables. Consulta [SECTOR_REPORTS.md](docs/SECTOR_REPORTS.md) para datos, ejecucion y limites. Los datos, informes y destinatarios permanecen fuera del repositorio.
