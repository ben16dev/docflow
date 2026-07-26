# CURSOR.md

# Proyecto: DocFlow

## Misión

DocFlow es una aplicación de escritorio para automatización y gestión documental destinada a despachos de abogados, empresas y departamentos administrativos.

La aplicación es **Local First**.

Los documentos del usuario nunca deben abandonar su ordenador para realizar las funciones principales de la aplicación.

Antes de responder o implementar cualquier cambio, leer siempre:

1. CURSOR.md
2. ARCHITECTURE.md

No asumir arquitectura ni comportamiento sin revisar estos documentos.

---

# Prioridad absoluta

Siempre priorizar, en este orden:

1. Estabilidad
2. Mantenibilidad
3. Privacidad
4. Compatibilidad multiplataforma
5. Rendimiento
6. Nuevas funcionalidades

Si existe conflicto entre nuevas funcionalidades y estabilidad, elegir siempre la estabilidad.

---

# Optimización de Cursor

El objetivo es minimizar consumo de contexto y de modelos sin reducir la calidad.

## Regla 1

No explorar el repositorio completo salvo petición expresa.

Nunca recorrer directorios completos "por si acaso".

---

## Regla 2

Antes de modificar código:

- explicar el objetivo;
- indicar el modo recomendado;
- indicar el modelo recomendado;
- listar únicamente los archivos necesarios.

Formato:

Objetivo:
Modo:
Modelo:
Archivos afectados:

---

## Regla 3

No abrir archivos adicionales salvo necesidad justificada.

Si la ubicación del código es desconocida:

- realizar una búsqueda mínima;
- detener la exploración cuando se identifiquen los archivos relevantes.

---

## Regla 4

No realizar refactors fuera del alcance solicitado.

Si detectas mejoras adicionales:

- indicarlas;
- no implementarlas.

---

## Regla 5

Implementar siempre el cambio mínimo viable.

Preferir:

- varias mejoras pequeñas;
- varias conversaciones;

antes que una modificación masiva.

---

## Regla 6

Antes de usar Agent, comprobar si la tarea puede resolverse con Edit.

Prioridad:

Ask
↓

Edit
↓

Agent

Agent solo debe utilizarse cuando exista una razón objetiva.

---

# Política de modelos

## Uso diario

Preferir:

- Auto
- Composer Fast
- Sonnet

## Uso avanzado

Utilizar GPT-5.5 únicamente para:

- arquitectura;
- bugs difíciles;
- revisiones complejas;
- decisiones de diseño.

## Thinking

Usar modelos Thinking únicamente cuando se solicite expresamente o la tarea requiera razonamiento profundo.

---

# Filosofía del proyecto

DocFlow debe ser:

- Local First.
- Multiplataforma.
- Modular.
- Profesional.
- Fácil de mantener.
- Robusto.
- Predecible.

Nunca incorporar dependencias cloud para funciones principales.

Nunca enviar documentos del usuario a servicios externos.

---

# Arquitectura

Respetar siempre la separación entre:

## UI

Responsable únicamente de:

- interacción;
- presentación;
- mensajes.

Nunca contener lógica documental.

---

## Negocio

Responsable de:

- validaciones;
- reglas;
- coordinación.

---

## Servicios

Responsables de:

- PDF;
- EML;
- MBOX;
- renombrado;
- conversión;
- apertura de programas.

---

## Utilidades

Responsables de:

- logging;
- rutas;
- helpers;
- funciones reutilizables.

---

# Principios de implementación

Antes de implementar:

1. explicar el problema;
2. explicar la solución;
3. indicar archivos afectados;
4. indicar riesgos;
5. indicar validación.

Después:

- implementar únicamente lo solicitado;
- no modificar APIs públicas;
- no cambiar nombres sin autorización.

---

# Gestión de errores

Todos los errores deben:

- registrarse;
- ser comprensibles para el usuario;
- permitir recuperación.

Nunca utilizar:

except:
    pass

Capturar siempre excepciones específicas.

---

# Logs

Los logs deben contener:

- fecha;
- operación;
- herramienta;
- error;
- contexto técnico.

Nunca registrar:

- contenido documental;
- datos personales innecesarios.

---

# Compatibilidad

Todo cambio debe considerar:

- macOS;
- Windows;
- Linux.

Las diferencias de plataforma deben aislarse en utilidades específicas.

---

# Testing

Toda mejora debe indicar:

- pruebas manuales;
- posibles regresiones;
- tests afectados.

Ejecutar únicamente las pruebas necesarias.

No lanzar la suite completa salvo que el cambio lo justifique.

---

# Exclusiones

No utilizar como contexto salvo petición expresa:

- dist/
- build/
- release/
- logs/
- .venv/
- __pycache__/
- node_modules/
- coverage/
- artefactos generados
- iconos compilados
- imágenes
- instaladores

Estas exclusiones deben mantenerse también en `.cursorignore`.

---

# Política de cambios

Cada implementación debe responder:

- Qué problema resuelve.
- Qué archivos modifica.
- Qué riesgos existen.
- Cómo se valida.
- Cómo se revierte.

---

# Filosofía final

Cada cambio debe acercar DocFlow a ser:

- más estable;
- más simple;
- más privado;
- más mantenible;
- más profesional.

No sacrificar estos principios para introducir funcionalidades de valor limitado.

---

Versión: CURSOR Rules v2.0
Última revisión: 2026-07-05