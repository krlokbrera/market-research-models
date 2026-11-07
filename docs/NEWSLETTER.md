# Newsletter de mercados

El informe combina investigación editorial verificada con las salidas del radar
sectorial. El correo permite leer las conclusiones principales; el PDF conserva
las mismas secciones y añade contexto, tablas y detalle de las simulaciones.
Los dos deben compartir cifras, fechas de corte, conclusiones y fuentes.

## Estructura editorial estable

| Clave del brief | Sección | Contenido mínimo |
| --- | --- | --- |
| summary | Resumen ejecutivo | Qué cambió, oportunidades relativas, riesgos y prioridades |
| market | 01 / Panorama y cambios | Entorno, divisas, tipos y comparación con la edición anterior |
| flows | 02 / Flujos y posicionamiento | Fuente, periodo, magnitud, interpretación y limitaciones |
| sectors | 03 / ETF y rotación sectorial | Universo cubierto, baseline, clasificación, candidatos y cambios |
| stocks | 04 / Acciones en seguimiento | Tesis, valoración contextual, catalizadores, riesgos e invalidación |
| simulations | 05 / Simulaciones de modelo | Datos, horizonte, supuestos, costes, referencia y limitaciones |
| crypto | 06 / Criptoactivos y custodia | Mercado, escenarios, liquidez, concentración y custodia |
| agenda | 07 / Agenda y riesgos | Eventos, escenarios, señales de seguimiento e incertidumbres |
| news | 08 / Noticias relevantes | Fecha, hecho comprobado, fuente y lectura separada |
| earnings | 09 / Resultados publicados y próximos 14 días | Dos semanas, fechas y periodo fiscal, estado y qué observar |

Redactar frases completas, explicar por qué importa cada dato y distinguir
hechos, interpretación y escenarios. Evitar abreviaturas sin definir y listas de
cifras sin explicación. El contenido editorial habla de simulaciones de modelo;
no describe código, comandos, repositorios ni comprobaciones informáticas.
No se atribuye autoría a ninguna consultora. La investigación es independiente.

El PDF añade explicaciones y tablas mediante bloques pdf_only; no elimina del
correo ninguna de las diez secciones. Las tablas deben tener pocas columnas,
celdas breves, encabezados repetidos y fuentes visibles. Las gráficas comparan
datos con igual divisa, ventana y corte, e incluyen unidades, fecha y explicación.
No usar imágenes generadas para representar datos de mercado.

## Revisión de lunes y jueves

El lunes se revisa el universo sectorial completo y se decide qué candidatos
entran, salen o continúan según las reglas de [SECTOR_REPORTS.md](SECTOR_REPORTS.md).
Los seis sectores baseline siempre aparecen como observación. La clasificación
no significa una orden de inversión ni obliga a seleccionar tres candidatos.
No reducir el universo a los ganadores recientes.

El jueves actualiza precios, noticias, resultados y riesgos, manteniendo el
horizonte del lunes y su decisión semanal. Si no hay un cierre más reciente que
el estado guardado, conservar ese estado; no presentar una repetición como una
nueva rotación. Los sectores sin datos válidos se identifican como problema de
cobertura, sin convertirlos automáticamente en una señal económica.

Las programaciones y los destinatarios se administran de forma privada, fuera
del repositorio. Este paquete no instala un cron ni envía correo. Confirmar las
tareas existentes antes de crear otras para evitar duplicados, y usar la zona
Europe/Madrid para que el horario local respete los cambios estacionales.

## Calendario de resultados

calendar_anchor es un lunes. La ventana incluye ese lunes y los trece días
siguientes, hasta el domingo de la segunda semana. La edición del jueves conserva
el mismo anclaje. Una edición extraordinaria de fin de semana puede anticipar
el lunes siguiente si lo explica en cutoff_note.

Cada anuncio debe incluir empresa, fecha, trimestre o ejercicio fiscal exacto,
estado, foco de seguimiento y enlace a relaciones con inversores. Los estados
permitidos son confirmed, provisional y published. No presentar fechas estimadas
como confirmadas ni una publicación futura como ya realizada. La validación
comprueba coherencia de fechas y formato; no demuestra que una fuente sea
auténtica, que confirme el evento o que se haya actualizado. Verificarlo antes
de componer cada edición.

Separar los resultados recientes ya publicados del calendario futuro. Durante
la semana, los anuncios del lunes a la fecha pueden marcarse published dentro
de su tabla semanal. Los resultados anteriores al anclaje se incluyen en
recent_earnings, dentro de los catorce días anteriores, solo si se verificó su
publicación. Una semana vacía significa que no se incluyeron eventos verificados,
no que no existan publicaciones.

## Composición local

Instalar el paquete y las dependencias opcionales de informes:

    python -m pip install -e ".[reports]"
    python -m market_models.newsletter --brief private/edition.json --output outputs --font-regular /ruta/georgia.ttf --font-bold /ruta/georgiab.ttf --font-italic /ruta/georgiai.ttf

Las tres fuentes locales generan el PDF con tipografía incrustada. Usar Georgia
cuando se disponga de licencia y acceso local; los archivos de fuentes no se
publican. Sin las tres opciones de fuentes, se genera solo HTML. Cada ejecución
crea una carpeta nueva con newsletter.html, newsletter.pdf cuando procede,
assets/ y manifest.json. El PDF es el informe editorial completo; el PDF de
market_models.sectors continúa siendo un anexo cuantitativo.

El HTML usa imágenes cid: y el manifiesto describe sus content_id, mime_type y
archivo relativo. El adaptador privado de correo debe adjuntar esas imágenes
como partes MIME inline y el PDF como adjunto, comprobando destinatarios y
contenido antes del envío. El compositor no accede a cuentas ni a la red.

## Contrato del brief privado

El JSON tiene title, edition_date (YYYY-MM-DD), calendar_anchor, cutoff_note y
sections con las diez claves de la tabla. Cada sección contiene una lista de
bloques:

- paragraph o subheading: text y, opcionalmente, source_url.
- table: rows con encabezado y filas rectangulares; una celda es texto o
  {"text": "...", "url": "https://..."}.
- chart: path relativo a la carpeta del brief y caption, que debe explicar
  unidades, periodo, corte y procedencia.
- Cualquier bloque admite pdf_only: true para ampliar solo el PDF.

Los textos se tratan como texto plano y se escapan al renderizar. Las tablas
admiten hasta ocho columnas y cien filas de datos; para lectura editorial se
recomiendan menos. Las gráficas deben ser PNG/JPEG dentro de la carpeta del brief,
incluidas sus subcarpetas; se rechazan rutas que salgan de ella.

news es una lista de objetos con date, title, summary, reading y source_url.
earnings y recent_earnings son listas con date, company, period, status, focus
y source_url. Los enlaces deben ser HTTPS y no incluir credenciales. La
composición añade las noticias y las tablas de ambas semanas a las secciones
correspondientes. Los bloques de esas secciones aportan introducción y contexto,
sin repetir manualmente los eventos.

No se suministra un brief de mercado de ejemplo para evitar que datos ficticios
se reutilicen como análisis real. Las pruebas usan exclusivamente empresas y
fuentes ficticias claramente identificadas, sin evidencia de rentabilidad.

## Privacidad y revisión

Guardar briefs, datos, estado semanal, informes, gráficas, resultados, fuentes
licenciadas, listas de destinatarios y credenciales en private/ u outputs/, o
fuera del checkout. No adjuntarlos a commits ni a incidencias públicas. Revisar
siempre el contenido staged; .gitignore es una ayuda, no una garantía.

Comprobar visualmente el PDF final para detectar encabezados aislados, filas
cortadas, gráficos ilegibles o espacios excesivos. Contrastar las cifras del
correo y PDF, los enlaces, la frescura de datos y cada fecha de resultados.
Si faltan datos, explicitar la cobertura y las conclusiones provisionales.
Las pruebas del formato no verifican rentabilidad ni sustituyen esa revisión.
