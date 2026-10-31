# Validación realizada

- Instalación editable del paquete completada en un entorno virtual local, sin descargar dependencias.
- 14 pruebas superadas, incluidas ejecuciones completas de backtest tradicional y cripto sobre series sintéticas.
- Comprobación de ejecución diferida, costes sin deuda, ausencia de información futura, ventanas incompletas y cambios de configuración inválidos.
- Rechazo de encabezados duplicados o con fórmulas, fechas inválidas, precios no positivos/no finitos y sobrescritura de ejemplos.
- Comprobación de manifiestos locales: etiqueta sintética, hash de entrada y ausencia de la ruta de origen.
- Compilación de los módulos completada.

El entorno de validación usa Python 3.11.4, numpy 1.26.1, pandas 2.2.1 y scikit-learn 1.3.2. La instalación de dependencias en un entorno limpio con otras versiones compatibles requiere su propia validación.

No se publica un backtest con datos reales ni una afirmación de rendimiento financiero. No se ha realizado una auditoría externa del código o de vulnerabilidades de dependencias.

