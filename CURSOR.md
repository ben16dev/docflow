# CURSOR.md

# Proyecto: DocFlow

DocFlow es una aplicación de escritorio para automatización y gestión documental orientada a despachos de abogados, empresas y departamentos administrativos.

La aplicación trabaja de forma completamente local. Ningún documento debe salir del equipo del usuario.

Objetivos del producto:
- Automatizar tareas documentales repetitivas.
- Mantener una interfaz simple y profesional.
- Priorizar la estabilidad sobre las nuevas funcionalidades.
- Ser multiplataforma:
  - macOS
  - Windows
  - Linux

---

# Principios fundamentales

1. Local First
Toda la ejecución se realiza en el ordenador del usuario.

Nunca:
- enviar documentos a servicios externos;
- incorporar APIs en la nube para procesar archivos;
- requerir conexión a Internet para funciones principales.

2. Simplicidad
La aplicación está dirigida a usuarios no técnicos.

Toda nueva funcionalidad debe:
- requerir el menor número de pasos posible;
- ser intuitiva;
- tener mensajes de error claros.

3. Estabilidad antes que nuevas funciones
No introducir cambios que puedan romper funcionalidades existentes.

Antes de modificar:
- analizar dependencias;
- revisar flujos afectados;
- mantener compatibilidad hacia atrás.

4. Código mantenible
Priorizar:
- claridad;
- modularidad;
- bajo acoplamiento;
- funciones pequeñas.

Evitar:
- duplicidad;
- funciones gigantes;
- lógica mezclada entre UI y negocio.

---
## Optimización de consumo de API

* Priorizar cambios pequeños e incrementales.
* Analizar antes de modificar.
* Limitar la edición a los archivos estrictamente necesarios.
* Evitar exploraciones completas del repositorio salvo necesidad justificada.
* No realizar refactors fuera del alcance solicitado.
* Ejecutar únicamente las pruebas necesarias para validar el cambio.
* Preferir varias iteraciones pequeñas frente a una implementación masiva.
* Usar Agent solo cuando deban modificarse archivos; utilizar Ask para análisis y planificación.

## Uso eficiente de modelos en Cursor

Usar Auto o Ask para análisis, planificación, revisión de informes y documentación.
Usar Agent con un modelo potente solo cuando sea necesario modificar archivos, depurar errores complejos, tocar UI, arquitectura, validadores, tests o empaquetado.
Antes de usar Agent, acotar archivos, objetivo y verificación.
Evitar agentes largos, refactors amplios y exploraciones completas del repositorio salvo necesidad justificada.

# Arquitectura

Separación obligatoria:

## Capa de interfaz
Responsable únicamente de:
- mostrar información;
- recoger acciones del usuario.

Nunca debe contener:
- lógica de negocio compleja;
- manipulación directa de archivos.

## Capa de negocio
Responsable de:
- validaciones;
- reglas de procesamiento;
- orquestación de herramientas.

## Capa de infraestructura
Responsable de:
- sistema de archivos;
- conversión de documentos;
- apertura de programas;
- generación de PDFs.

---

# Principios de desarrollo

Antes de implementar:

1. Explicar:
- objetivo;
- archivos afectados;
- riesgos.

2. Implementar el cambio mínimo viable.

3. No realizar refactors no solicitados.

4. No cambiar nombres, rutas o APIs públicas salvo indicación expresa.

5. Si existen varias alternativas:
- proponerlas;
- recomendar una.

---

# Gestión de errores

Todos los errores deben:

- registrarse en el log;
- mostrar un mensaje comprensible al usuario;
- evitar cierres inesperados.

Nunca usar:

```python
except:
    pass

Siempre capturar excepciones específicas.

Logs

Los logs deben:

ser útiles para depuración;
incluir contexto suficiente;
evitar información innecesaria.

No registrar:

contenido de documentos;
datos personales completos;
información sensible.
Interfaz

La interfaz debe ser:

limpia;
profesional;
consistente;
pensada para despachos y empresas.

Evitar:

ventanas innecesarias;
diálogos redundantes;
configuraciones complejas.
Compatibilidad

Toda modificación debe considerar:

macOS
Windows
Linux

No introducir código específico de una plataforma sin contemplar las demás.

Testing

Toda mejora debe indicar:

pruebas manuales necesarias;
posibles regresiones;
tests automatizados que deben ejecutarse.

Cuando sea posible:

añadir tests;
no romper la suite existente.
Política de cambios

Antes de cada implementación, responder:

Qué problema se resuelve.
Qué archivos se modifican.
Qué riesgos existen.
Cómo se valida.
Cómo se revierte.
Filosofía de DocFlow

DocFlow es una herramienta profesional de automatización documental:

rápida;
robusta;
privada;
multiplataforma;
mantenible a largo plazo.

En caso de conflicto entre nuevas funcionalidades y estabilidad, elegir siempre la estabilidad.