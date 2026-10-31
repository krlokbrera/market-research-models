# Seguridad y gestión de datos

## Alcance de esta publicación

Solo se publican el paquete, sus configuraciones sin secretos, las guías y pruebas con series generadas. No se publica ningún CSV, informe de inversión, resultado, caché, archivo de cuenta o credencial.

## Ejecución local

El paquete no contiene funciones de red, telemetría, conectores de cuentas ni envío de órdenes. No requiere API keys. No carga variables secretas del entorno ni archivos .env.

Las entradas son CSV y JSON; no se deserializa pickle, no se ejecutan expresiones ni se aceptan scripts en la configuración. Los precios, fechas, encabezados y parámetros se validan antes del cálculo.

Los identificadores de columnas no pueden empezar por operadores de fórmula. Esto reduce el riesgo de fórmulas en los CSV exportados. No es una herramienta general para limpiar hojas de cálculo externas.

## Protección del dato

- Mantén entradas en inputs/ y resultados en outputs/; están ignorados por Git.
- Usa identificadores de activos, sin números de cuenta ni datos personales.
- No publiques históricos sujetos a restricciones de licencia.
- No escribas credenciales en configuración, notebooks, comandos versionados o issues.
- Revisa los cambios preparados con git diff --cached antes de subirlos.
- No confíes solo en .gitignore: un archivo ya versionado no deja de estarlo por añadir una regla.

Cada ejecución usa una carpeta nueva. Las entradas no se sobrescriben. El manifiesto guarda versión, configuración, fechas y SHA-256 del archivo fuente, sin su ruta. Los libros, operaciones, capital y manifiestos pueden revelar tu investigación: mantenlos locales.

## Dependencias y revisión

Utiliza un entorno virtual. Instala desde el registro de paquetes habitual, conserva un registro local de las versiones efectivamente utilizadas y revisa avisos de seguridad al actualizar. Los rangos de versiones evitan actualizaciones mayores automáticas; no equivalen a una auditoría de vulnerabilidades ni a un lock completo.

Las pruebas se ejecutan sin datos de mercado y sin credenciales. No existe una afirmación de que las dependencias estén libres de vulnerabilidades.

## Si se filtra un secreto

Revócalo o rótalo en el proveedor. Borrarlo del último commit no elimina su presencia en el historial. No publiques el valor en un issue para reportar el problema.

No se otorgan garantías de custodia, acceso a fondos o seguridad de un exchange mediante estos modelos.
