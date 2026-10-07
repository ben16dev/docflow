## FASE 1 — ESTABILIZACIÓN FUNCIONAL ✅

Estado: Cerrada en desarrollo en macOS.

### Pendiente para Release

* Validar Chrome y Edge en Windows.
* Validar Chrome/Chromium en Linux.
* Confirmar apertura del log en Windows.
* Confirmar apertura del log en Linux.
* Validación final sobre .app y .exe.

## FASE 2 — HERRAMIENTAS

### 1. Renombrar archivos

Estado: Funcional y cerrado en desarrollo.

#### Implementado

* Selección múltiple.
* Reordenación.
* TXT y texto pegado.
* Validaciones.
* Previsualización.
* Detección de conflictos.
* Carpeta destino.
* Copia segura.
* Progreso.
* Cancelación.
* Resumen.
* Registro de incidencias.
* Apertura de carpeta resultado.
* Arquitectura desacoplada.
* Ejecución real.
* Cobertura automática integrada en la suite general.
* Integración en la pestaña RENOMBRADO.

#### Mejoras futuras

* Modificar originales.
* Confirmación previa.
* Numeración automática.
* Prefijos y sufijos.
* Edición directa de nombres.
* Deshacer operaciones.
* Patrones de renombrado.
* Guardar y cargar listas.
* Filtros por extensión.
* Plantillas reutilizables.

### 2. Agrupar y unir PDFs por patrón

Estado: Pendiente.

#### Objetivos

* Agrupar por:
    * nombre;
    * DNI;
    * expediente;
    * referencia;
    * expresión regular.
* Revisar grupos antes de ejecutar.
* Reordenar PDFs.
* Excluir documentos.
* Generar un PDF por grupo.
* Evitar sobrescrituras.
* Mantener los originales intactos.
* Integrar progreso y cancelación.
* Generar resumen final.

## FASE 3 — CONVERSIÓN DOCUMENTAL

### Infraestructura

Estado: Implementada y consolidada.

#### Implementado

* Pestaña CONVERSIÓN.
* Integración con la navegación.
* Registro central de herramientas.
* Ejecución mediante ScriptRunner.
* Herramientas autocontenidas sin carpeta de trabajo previa.
* Imagen → PDF.
* PDF escaneado → PDF OCR.
* MBOX → EML.
* Extracción de adjuntos de MBOX.
* EML → PDF.
* Gestión homogénea de resultados completos, parciales, fallidos y cancelados.
* Conservación de carpeta de salida y resultados parciales tras cancelación.
* Herramientas MBOX integradas en CONVERSIÓN.
* Herramientas EML integradas en CONVERSIÓN.
* Eliminación de las pestañas independientes MBOX y EML.
* Eliminación de imports y módulos de UI obsoletos.
* Conservación íntegra de los scripts funcionales MBOX y EML.
* Validación manual de las herramientas migradas en macOS.

#### Arquitectura actual

DocFlow dispone de tres pestañas principales:

1. PDF.
2. RENOMBRADO.
3. CONVERSIÓN.

El registro central continúa siendo la fuente única de herramientas.

#### Criterio funcional de clasificación

* PDF: operaciones internas sobre documentos PDF que mantienen el formato PDF.
* RENOMBRADO: cambios de nombre, organización y tratamiento de nombres de archivo.
* CONVERSIÓN: transformación entre formatos o generación de una nueva representación documental.

#### Herramientas actuales de CONVERSIÓN

* Imagen → PDF.
* PDF escaneado → PDF OCR.
* MBOX → EML.
* Extraer adjuntos de MBOX.
* EML → PDF.

#### Evolución prevista

* PDF → Markdown.
* EML → Markdown.
* Word → PDF.
* PDF → Texto.
* PDF → Imágenes.
* Conversión entre formatos de correo.
* Cadenas de conversión reutilizables.

### 1. PDF escaneado → PDF OCR ✅

Estado: Cerrado en desarrollo, empaquetado y validado en macOS arm64.

#### Implementado

* Evaluación técnica de alternativas OCR.
* OCRmyPDF 17.8.1.
* Tesseract 5.5.3.
* pypdfium2 5.12.1.
* Funcionamiento sin Ghostscript.
* Procesamiento completamente local.
* Selección de uno o varios PDF.
* Selección de carpeta destino.
* Conservación estricta del archivo original.
* Generación de PDF independiente con capa OCR.
* Texto seleccionable y buscable.
* Idioma español.
* PDF estándar, sin conversión forzada a PDF/A.
* --mode skip.
* --optimize 0.
* --rasterizer pypdfium.
* Ejecución mediante subprocess.Popen.
* Progreso por archivo.
* Cancelación antes del proceso.
* Cancelación entre archivos.
* Cancelación durante el OCR.
* Terminación del grupo de procesos en macOS.
* Preparación de cancelación para Windows.
* Temporales en el mismo volumen que el destino.
* Limpieza tras éxito, error y cancelación.
* Promoción atómica mediante os.replace.
* Prevención de sobrescrituras.
* Gestión de colisiones mediante sufijos alternativos.
* Validación del número de páginas.
* Validación de texto extraíble.
* Verificación del archivo final antes de contarlo como procesado.
* Comprobación de que el resultado pertenece a la carpeta elegida.
* Protección frente a salida igual al original.
* Protección frente a symlinks y rutas equivalentes.
* Gestión correcta de resultados parciales y fallos totales.
* Contrato interno por archivo:
    * procesado;
    * omitido;
    * error;
    * cancelado.
* Lista real, única y validada de archivos generados.
* Coherencia entre procesados y archivos físicos existentes.
* Revalidación final del lote.
* Apertura de carpeta de resultado.
* Conservación de carpeta y estadísticas tras cancelación parcial.
* Logs sin rutas completas, nombres documentales ni contenido OCR.
* Integración en CONVERSIÓN.
* Integración con ScriptRunner.
* Validación manual completa en macOS.
* Selección múltiple validada.
* Colisiones validadas.
* Fallo parcial validado.
* Cancelación parcial validada.
* Ausencia de procesos huérfanos.
* Limpieza de temporales validada.
* Resultados visibles en Finder.
* Corrección del flag BSD UF_HIDDEN.
* GitHub Actions corregido para rutas multiplataforma.
* Build PyInstaller onedir + BUNDLE.
* Helper OCRmyPDF empaquetado.
* Tesseract y dylibs incluidos en la .app.
* spa.traineddata y configuraciones de Tesseract incluidas.
* Ejecución fuera del repositorio.
* Ejecución sin .venv.
* Ejecución sin Homebrew disponible en PATH.
* Ausencia de dependencias Mach-O activas hacia Homebrew.

#### Dependencias incorporadas

* ocrmypdf==17.8.1.
* pypdfium2==5.12.1.
* pikepdf==10.10.0.
* pdfminer.six==20260107.
* pdfplumber==0.11.10.
* Pillow==12.3.0.

#### Pendiente para distribución

* Firma de la aplicación en macOS.
* Notarización en macOS.
* Resolver warning de codesign relacionado con metadata/resource forks.
* Validar build macOS x86_64 o universal.
* Preparar runtime portable de Windows.
* Integrar Tesseract y tessdata en Windows.
* Validar ejecución real en Windows.
* Validar cancelación y terminación de procesos descendientes en Windows.
* Validar .exe fuera del entorno de desarrollo.
* Validar instalación en equipo limpio.
* Confirmar comportamiento con PDFs:
    * ya digitalizados;
    * mixtos;
    * girados;
    * de baja calidad;
    * de muchas páginas.

#### Mejoras futuras

* Inglés y combinación spa+eng.
* Selección de idioma.
* Corrección de inclinación.
* Rotación automática.
* OCR forzado.
* OCR por páginas.
* Conversión a PDF/A.
* Procesamiento por carpetas completas.
* Ajustes avanzados de calidad y rendimiento.

### 2. MBOX y EML dentro de CONVERSIÓN ✅

Estado: Cerrado en desarrollo y validado en macOS.

#### Implementado

* Inventario de herramientas MBOX y EML.
* Revisión de contratos y dependencias.
* Migración de registro a CONVERSIÓN.
* MBOX → EML integrado.
* Extraer adjuntos de MBOX integrado.
* EML → PDF integrado.
* Scripts existentes reutilizados sin duplicación.
* Contratos existentes conservados.
* Progreso conservado.
* Cancelación conservada.
* Selección de archivos y carpetas conservada.
* Resultados y apertura de carpeta conservados.
* Textos de ayuda actualizados.
* Pestaña MBOX eliminada.
* Pestaña EML eliminada.
* Imports y módulos de UI obsoletos eliminados.
* Tests antiguos de pestañas sustituidos por tests de la arquitectura nueva.
* Tests de registro añadidos.
* Tests de navegación añadidos.
* Validación manual de las tres herramientas migradas.
* Layout de CONVERSIÓN revisado.
* Grid final 2 + 2 + 1.
* Descripciones visibles en tamaño normal de ventana.
* Sin solapamientos visuales.

#### Diseño actual

Cinco ToolCards en grid de dos columnas:

* Imagen a PDF.
* PDF escaneado a PDF OCR.
* MBOX a EML.
* Extraer adjuntos de MBOX.
* EML a PDF.

No se utilizan agrupaciones visuales adicionales mientras el número de herramientas siga siendo reducido.

### 3. PDF → Markdown

Estado: Pendiente.

#### Objetivos

* Aprovechar PDFs digitales y PDFs procesados con OCR.
* Extraer texto sin servicios externos.
* Mantener títulos, párrafos y listas cuando sea posible.
* Conservar una estructura documental razonable.
* Optimizar la salida para IA y RAG.
* Evitar contenido duplicado.
* Exportar a Markdown.
* Mantener el PDF original intacto.
* Permitir selección múltiple.
* Progreso.
* Cancelación.
* Gestión de colisiones.
* Validación del archivo generado.
* Tests automáticos.
* Integración dentro de CONVERSIÓN.

## FASE 4 — EXPERIENCIA DE USUARIO

### 1. Simplificación de navegación ✅

Estado: Cerrada en desarrollo y validada en macOS.

#### Implementado

* Tres pestañas principales:
    * PDF;
    * RENOMBRADO;
    * CONVERSIÓN.
* Eliminación de MBOX como pestaña independiente.
* Eliminación de EML como pestaña independiente.
* Renombrado visible de ARCHIVOS como RENOMBRADO.
* Consolidación de herramientas de correo dentro de CONVERSIÓN.
* Eliminación de módulos UI obsoletos.
* Registro actualizado.
* Metadatos actualizados.
* Tests de navegación añadidos.
* Tests de registro actualizados.
* Tests de CONVERSIÓN actualizados.
* Interfaz validada manualmente.
* Layout de CONVERSIÓN corregido tras validación visual.
* Cards y descripciones correctamente visibles.
* ProgressPanel y StatusBar mantienen su composición.
* Captura de CONVERSIÓN actualizada.
* README actualizado.
* TESTING.md actualizado.

#### Validación

* Solo existen PDF, RENOMBRADO y CONVERSIÓN.
* Orden correcto validado.
* MBOX y EML no aparecen como pestañas.
* Las cinco herramientas de CONVERSIÓN están disponibles.
* Herramientas MBOX/EML probadas manualmente.
* Suite actual: 395 tests superados y 1 omitido.
* Validación visual realizada en macOS.

#### Pendiente multiplataforma

* Validar navegación final en Windows.
* Validar redimensionado en Windows.
* Validar herramientas migradas en Windows.

### 2. Iconos de pestañas

Estado: Pendiente.

#### Objetivo

Completar la coherencia visual de la navegación principal.

Actualmente la pestaña PDF dispone de icono propio, mientras RENOMBRADO y CONVERSIÓN no.

#### Objetivos

* Añadir icono a RENOMBRADO.
* Añadir icono a CONVERSIÓN.
* Mantener el mismo criterio visual que la pestaña PDF.
* Usar recursos coherentes con la identidad DocFlow.
* Mantener tamaño, alineación y espaciado homogéneos.
* Incluir los recursos en el empaquetado .app y .exe.
* Validar visualmente en macOS.
* Validar posteriormente en Windows.
* Evitar dependencias externas para cargar los iconos.
* Mantener navegación por teclado y comportamiento actual del Notebook.

### 3. Drag & Drop

Estado: Pendiente.

#### Objetivos

* Arrastrar archivos.
* Arrastrar carpetas.
* Selección múltiple.
* Zonas comunes.
* Validación automática.
* Mensajes claros.
* Componente reutilizable.
* Compatible con macOS y Windows.
* Integración progresiva por herramienta.
* Mantener como alternativa los selectores tradicionales.

### 4. Componentes comunes

Estado: Pendiente.

#### Objetivos

* Selector reutilizable de archivos.
* Selector reutilizable de carpetas.
* Carpetas recientes.
* Recordar últimas ubicaciones.
* Apertura rápida.
* Listas reutilizables de archivos.
* Resúmenes homogéneos.
* Mensajes de error comunes.
* Consistencia entre herramientas autocontenidas.
* Componentes de sección reutilizables para CONVERSIÓN.

### 5. Identidad visual ✅

Estado: Validada fuera del roadmap funcional.

#### Implementado

* Identidad visual revisada.
* Icono y logotipo aprobados.
* Aplicación visualmente coherente con la marca DocFlow.

#### Seguimiento

* Añadir iconos de pestaña para RENOMBRADO y CONVERSIÓN.
* Mantener identidad visual en nuevas herramientas.
* Validar recursos finales en .app y .exe.

## FASE 5 — SEGURIDAD

Estado: Parcialmente implementada.

### Implementado

* Conservación de originales en Renombrar y OCR.
* Gestión de colisiones mediante helpers comunes.
* Temporales seguros en OCR.
* Limpieza tras éxito, error y cancelación.
* Validación del resultado OCR antes de promoverlo.
* Revalidación de archivos físicos antes de contabilizarlos.
* Protección frente a salida igual al original.
* Protección frente a rutas fuera del destino.
* Protección frente a symlinks y rutas equivalentes.
* Logs OCR sin contenido documental, nombres ni rutas completas.
* Comprobación de pertenencia del archivo final al destino.
* Promoción atómica.
* Eliminación controlada del flag UF_HIDDEN en macOS.
* Conservación de otros flags y atributos extendidos.

### Pendiente

* Confirmación antes de modificar originales.
* Normalización común de entradas.
* Gestión completamente centralizada de colisiones.
* Limpieza transversal de temporales.
* Advertencias para PDFs firmados.
* Detección de archivos protegidos.
* Verificación opcional mediante hash.
* Política común de privacidad para logs.
* Revisión de licencias de dependencias para distribución comercial.

## FASE 6 — PRUEBAS Y CALIDAD

Estado: En progreso.

### Implementado

* Suite general con 395 tests superados y 1 omitido.
* Tests del núcleo OCR.
* Tests de integración OCR.
* Tests de selección múltiple.
* Tests de cancelación.
* Tests de cancelación parcial.
* Tests de temporales y promoción.
* Tests de colisiones.
* Tests de validación del resultado.
* Tests de protección del original.
* Tests de symlinks y rutas equivalentes.
* Tests de contabilidad por archivo.
* Tests de fallo parcial.
* Tests de unicidad de resultados.
* Tests de flag UF_HIDDEN.
* Tests de privacidad de logs.
* Tests de ScriptRunner.
* Tests de CONVERSIÓN.
* Tests del contrato común de resultados.
* Tests de rutas compatibles con macOS y Windows.
* Tests del runtime empaquetado.
* Tests de localización de OCRmyPDF, Tesseract y tessdata.
* Tests de migración MBOX/EML a CONVERSIÓN.
* Tests de ausencia de pestañas MBOX y EML.
* Tests de orden final de pestañas.
* Tests de navegación del Sprint 8.
* Tests de registro tras consolidación.
* GitHub Actions activo.
* Validación manual OCR completa en macOS.
* Validación manual MBOX/EML desde CONVERSIÓN.
* Validación visual de la navegación final en macOS.
* Validación de .app OCR fuera del repositorio.

### Pendiente

* Más tests PDF.
* Más tests MBOX.
* Más tests EML.
* Tests PDF → Markdown.
* Tests Drag & Drop.
* Tests de iconos de pestañas si procede.
* Validación real OCR en Windows.
* Tests del runtime portable Windows.
* Tests del .exe.
* Validación multiplataforma completa.
* Ejecución periódica de TESTING.md.
* Instalación limpia desde requirements.txt.
* Revisión de warnings de pytest y dependencias.
* Resolver o eliminar el test omitido dependiente de la fixture histórica del spike.

## FASE 7 — DISTRIBUCIÓN

Estado: Empaquetado OCR macOS arm64 completado. Distribución general pendiente.

### Implementado

* Migración macOS a PyInstaller onedir + BUNDLE.
* DocFlow.spec adaptado.
* Build definitivo .app con runtime OCR.
* Helper OCRmyPDF empaquetado.
* Tesseract empaquetado.
* Dylibs de Tesseract empaquetadas.
* spa.traineddata incluido.
* Configuraciones de Tesseract incluidas.
* Plugins y datos internos necesarios de OCRmyPDF incluidos.
* Ejecución fuera del repositorio.
* Ejecución sin .venv.
* Ejecución sin Homebrew disponible en PATH.
* Ausencia de referencias Mach-O activas a Homebrew.
* Arquitectura arm64 validada.
* Tamaño aproximado de distribución: 190 MB.
* BUILD.md actualizado.
* Referencia funcional de distribución Windows obtenida de EDV AppScript.

### Pendiente

* Firma de Windows.
* Firma de macOS.
* Notarización de macOS.
* Resolver metadata/resource forks para firma.
* Build macOS x86_64 o universal.
* Build definitivo .exe.
* Runtime OCR portable para Windows.
* Validar ejecución en equipo limpio.
* Recursos definitivos.
* Incorporar y validar iconos finales de RENOMBRADO y CONVERSIÓN en builds.
* Markdown empaquetado.
* Crear ZIP o instalador de distribución.
* Primera Release estable.

## FASE 8 — AUTOMATIZACIÓN DOCUMENTAL

### Visión de producto

Convertir DocFlow en una plataforma profesional de automatización documental local.

### 1. Extracción inteligente de datos

* NIF / CIF.
* IBAN.
* Fechas.
* Importes.
* Matrículas.
* Referencias.
* Número de procedimiento.
* Exportación a Excel/CSV.
* Uso de texto digital u OCR como fuente.
* Reglas configurables.
* Validación previa a exportación.

### 2. Clasificación documental

* Clasificación automática mediante reglas.
* Escrituras.
* Contratos.
* Facturas.
* Nóminas.
* DNI.
* Sentencias.
* Autos.
* Certificados.
* Organización automática por carpetas.

### 3. Carpetas vigiladas

* Monitorización de carpetas.
* Procesamiento automático.
* Ejecución de reglas.
* Registro de actividad.
* Gestión de errores.
* Prevención de procesamientos duplicados.

### 4. Flujos de automatización

* Encadenar herramientas.
* Guardar flujos reutilizables.
* Parámetros configurables.
* Ejecución con un clic.

Entrada ↓ OCR ↓ Renombrar ↓ Extraer datos ↓ Mover ↓ ZIP

### 5. Editor visual de flujos

Largo plazo.

* Constructor visual.
* Bloques reutilizables.
* Conexiones entre herramientas.
* Validación del flujo.
* Gestión de errores por bloque.
* Previsualización del resultado.

### 6. Buscador documental

* Indexación local.
* Búsqueda por contenido.
* Búsqueda por metadatos.
* Uso de PDFs OCR.
* Sin servicios externos.

### 7. Anonimización documental

Estado de ubicación: pendiente de decisión de producto.

#### Posibles ubicaciones

* Nueva pestaña específica si incorpora revisión visual, reglas y múltiples herramientas.
* Integración dentro de PDF si se limita a redacción de documentos PDF.
* Integración dentro de CONVERSIÓN si genera una copia anonimizada.

#### Funcionalidad prevista

* Detección y eliminación automática de:
    * DNI;
    * IBAN;
    * teléfonos;
    * direcciones;
    * correos electrónicos.
* Validación visual previa.
* Pensado para compartir documentación de forma segura.

### 8. IA local opcional

Largo plazo.

* Resumen de documentos.
* Explicación de contratos.
* Búsqueda semántica.
* Ayuda documental.
* Procesamiento completamente local cuando el hardware lo permita.

## PRIORIDADES

### Alta

1. Validación y empaquetado OCR en Windows.
2. PDF → Markdown.
3. Drag & Drop.

### Media

1. Añadir iconos a RENOMBRADO y CONVERSIÓN.
2. Agrupar y unir PDFs por patrón.
3. Mejoras del renombrado.
4. Componentes reutilizables.
5. Extracción inteligente de datos.
6. Auditoría de licencias y dependencias.
7. Firma y notarización de macOS.

### Baja

1. Clasificación documental.
2. Carpetas vigiladas.
3. Flujos de automatización.
4. Buscador documental.
5. Verificación mediante hash.
6. Deshacer operaciones.

### Largo plazo

1. Editor visual de flujos.
2. IA local.
3. Anonimización inteligente.

## SPRINT 6 — OCR ✅

Estado: Cerrado en desarrollo macOS.

Sin cambios respecto al cierre anterior.

## SPRINT 7 — EMPAQUETADO OCR EN MACOS ✅

Estado: Cerrado en desarrollo macOS arm64.

Sin cambios respecto al cierre anterior.

## SPRINT 8 — SIMPLIFICACIÓN DE NAVEGACIÓN ✅

Estado: Cerrado en desarrollo y validado en macOS.

### Fase 1 — Auditoría ✅

* Inventario de herramientas MBOX.
* Inventario de herramientas EML.
* Revisión de contratos y dependencias.
* Revisión del registro y metadatos.
* Revisión de tests.
* Localización de imports y módulos específicos.
* Análisis de CONVERSIÓN.
* Confirmación de arquitectura final:
    * PDF;
    * RENOMBRADO;
    * CONVERSIÓN.

### Fase 2 — Migración ✅

* Herramientas MBOX trasladadas a CONVERSIÓN.
* Herramientas EML trasladadas a CONVERSIÓN.
* ARCHIVOS renombrado visualmente como RENOMBRADO.
* Pestañas MBOX y EML eliminadas.
* Imports y módulos UI obsoletos eliminados.
* Scripts funcionales conservados.
* ScriptRunner conservado.
* Progreso y cancelación conservados.
* Resultados y apertura de carpeta conservados.
* Textos de ayuda actualizados.
* Registro central actualizado.
* Metadatos actualizados.
* CONVERSIÓN adaptada a cinco herramientas.

### Fase 3 — Pruebas y validación ✅

* Tests del registro.
* Tests del orden de pestañas.
* Tests de ausencia de MBOX/EML como pestañas.
* Tests de presencia de las herramientas migradas.
* Tests de unicidad del registro.
* Tests de executor correcto.
* Suite completa: 395 passed, 1 skipped.
* Imports validados.
* Ausencia de referencias UI obsoletas verificada.
* Arranque correcto.
* MBOX → EML validado manualmente.
* Extraer adjuntos de MBOX validado manualmente.
* EML → PDF validado manualmente.
* CONVERSIÓN validada visualmente.
* Solapamiento inicial del separador visual detectado y corregido.
* Altura de cards corregida.
* Descripciones visibles en tamaño normal.
* Grid final 2 + 2 + 1 validado.
* ProgressPanel y StatusBar correctamente integrados.
* README actualizado.
* TESTING.md actualizado.
* Captura de CONVERSIÓN actualizada.
* Commit y push realizados.

### Criterio de cierre ✅

DocFlow dispone únicamente de las pestañas:

PDF · RENOMBRADO · CONVERSIÓN

sin pérdida funcional, con las herramientas MBOX y EML integradas en CONVERSIÓN y validadas en macOS.

### Pendiente transversal

* Validación de la nueva navegación en Windows.
* Añadir iconos a RENOMBRADO y CONVERSIÓN.

## SIGUIENTE SPRINT RECOMENDADO

### SPRINT 9 — OCR EN WINDOWS

Lo mantendría como siguiente sprint porque es actualmente el mayor bloqueo técnico para que DocFlow pueda avanzar hacia una distribución verdaderamente multiplataforma. Los iconos de RENOMBRADO y CONVERSIÓN los trataría como un ajuste UX pequeño, posiblemente antes o después del Sprint 9, pero no retrasaría Windows por ellos.
