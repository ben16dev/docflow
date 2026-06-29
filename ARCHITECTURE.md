# ARCHITECTURE.md

# Arquitectura de DocFlow

DocFlow es una aplicación de escritorio para automatización y gestión documental, orientada a despachos de abogados, empresas y departamentos administrativos.

El principio central del proyecto es que todos los documentos se procesan localmente en el ordenador del usuario. La aplicación no debe depender de servicios externos para sus funciones principales.

---

# Objetivos técnicos

DocFlow debe ser:

* Local first.
* Multiplataforma: macOS, Windows y Linux.
* Fácil de mantener.
* Modular.
* Robusto ante errores de archivos, rutas y dependencias externas.
* Sencillo para usuarios no técnicos.

---

# Estructura general del proyecto

La estructura recomendada es:

```txt
DocFlow/
├── app/
│   ├── main.py
│   ├── ui/
│   ├── core/
│   ├── services/
│   └── utils/
│
├── scripts/
│   └── herramientas documentales independientes
│
├── assets/
│   ├── icon.png
│   ├── icon.ico
│   ├── icon.icns
│   └── logo.png
│
├── tests/
│   └── tests automatizados
│
├── logs/
│   └── archivos de log generados en ejecución
│
├── dist/
│   └── builds generadas
│
├── build/
│   └── archivos temporales de build
│
├── CURSOR.md
├── ARCHITECTURE.md
├── README.md
└── requirements.txt
```

---

# Capas de arquitectura

## 1. Interfaz de usuario

Responsabilidad:

* Mostrar herramientas disponibles.
* Permitir selección de archivos y carpetas.
* Mostrar mensajes de estado, éxito o error.
* Ejecutar acciones solicitadas por el usuario.

No debe contener:

* Lógica documental compleja.
* Manipulación directa avanzada de archivos.
* Reglas internas de negocio.

La interfaz debe delegar el trabajo en servicios o scripts especializados.

---

## 2. Capa de negocio

Responsabilidad:

* Validar entradas del usuario.
* Preparar parámetros.
* Coordinar herramientas.
* Gestionar errores controlados.
* Devolver resultados claros a la interfaz.

Ejemplos:

* Validar que un archivo existe.
* Validar que una carpeta tiene permisos de escritura.
* Validar que el número de nombres coincide con el número de archivos.
* Comprobar que una conversión se ha completado correctamente.

---

## 3. Capa de servicios

Responsabilidad:

* Conversión de documentos.
* Operaciones con PDFs.
* Procesamiento de EML/MBOX.
* Renombrado masivo.
* Apertura de logs.
* Detección de navegadores o aplicaciones externas.

Debe estar desacoplada de la interfaz.

---

## 4. Utilidades

Responsabilidad:

* Funciones reutilizables.
* Normalización de rutas.
* Logging.
* Limpieza de nombres de archivo.
* Comprobaciones de sistema operativo.
* Helpers multiplataforma.

---

# Reglas sobre scripts

Los scripts documentales deben poder ejecutarse de forma independiente cuando sea razonable.

Cada script debe tener:

* Una responsabilidad clara.
* Entrada definida.
* Salida definida.
* Manejo de errores.
* Logs útiles.
* Validaciones previas.

No se deben crear scripts enormes que mezclen varias herramientas no relacionadas.

---

# Gestión de archivos

Toda operación sobre archivos debe ser conservadora.

Reglas:

* No sobrescribir archivos sin confirmación o estrategia segura.
* Conservar extensiones originales cuando proceda.
* Evitar nombres inválidos en Windows, macOS y Linux.
* Gestionar duplicados de forma previsible.
* Validar rutas antes de operar.
* Evitar borrar archivos salvo que el usuario lo solicite expresamente.

---

# Privacidad

DocFlow trabaja con documentación potencialmente sensible.

Nunca debe:

* Subir documentos a APIs externas.
* Enviar contenido a servicios cloud.
* Registrar contenido completo de documentos.
* Registrar datos personales innecesarios.

Los logs deben registrar información técnica suficiente, pero no contenido sensible.

---

# Logs

Los logs deben servir para depurar errores reales.

Deben incluir:

* Fecha y hora.
* Herramienta ejecutada.
* Operación realizada.
* Error producido, si existe.
* Ruta afectada cuando sea necesario.

Deben evitar:

* Contenido completo de documentos.
* Datos personales extensos.
* Información irrelevante.

---

# Compatibilidad multiplataforma

Todo cambio debe considerar:

* macOS.
* Windows.
* Linux.

Cuando una función dependa del sistema operativo, debe aislarse en una utilidad específica.

Ejemplos:

* Apertura de archivos.
* Apertura de logs.
* Detección de navegadores.
* Rutas del sistema.
* Comandos externos.

---

# Dependencias externas

Las dependencias deben ser mínimas y justificadas.

Antes de añadir una dependencia:

1. Comprobar si ya existe una solución interna.
2. Valorar mantenimiento y compatibilidad.
3. Confirmar soporte en macOS, Windows y Linux.
4. Añadirla a `requirements.txt`.
5. Documentar su uso.

---

# Testing

El proyecto debe mantener tests automatizados para funciones críticas.

Prioridades de test:

* Validación de rutas.
* Limpieza de nombres de archivo.
* Renombrado masivo.
* Conversión EML/MBOX.
* Operaciones PDF.
* Compatibilidad multiplataforma cuando sea testeable.
* Gestión de errores.

Antes de cerrar una fase:

* Ejecutar suite completa.
* Validar manualmente los flujos principales.
* Revisar regresiones.

---

# Build y distribución

La aplicación debe poder empaquetarse para escritorio.

Objetivos:

* Generar ejecutable en macOS.
* Generar ejecutable en Windows.
* Mantener compatibilidad Linux si procede.
* Incluir iconos y assets correctamente.
* Evitar incluir archivos temporales, logs o tests en builds finales salvo necesidad expresa.

Los archivos `build/` y `dist/` son artefactos generados y no deben tratarse como código fuente principal.

---

# Fases actuales del proyecto

## Fase 1 — Estabilización funcional

Objetivo:

* Corregir errores existentes.
* Validar funcionamiento básico.
* Asegurar compatibilidad inicial.
* Añadir tests mínimos.
* Eliminar herramientas obsoletas.

Estado:

* Implementada.
* Pendiente de verificaciones complementarias en algunos sistemas.

---

## Fase 2 — Rediseño de herramientas

Objetivo:

* Revisar herramientas actuales.
* Eliminar herramientas poco útiles.
* Rediseñar flujos documentales.
* Simplificar la experiencia de usuario.
* Hacer las herramientas más generales y reutilizables.

Principio:

No añadir complejidad innecesaria. Cada herramienta debe resolver un problema documental concreto.

---

# Herramientas documentales

Cada herramienta debe documentarse con:

* Nombre.
* Problema que resuelve.
* Entrada.
* Proceso.
* Salida.
* Errores posibles.
* Validaciones.
* Pruebas necesarias.

Formato recomendado:

```md
## Nombre de herramienta

### Objetivo
Descripción breve.

### Entrada
Archivos, carpetas o parámetros necesarios.

### Proceso
Pasos principales.

### Salida
Resultado esperado.

### Validaciones
Condiciones que deben cumplirse.

### Errores
Errores previsibles.

### Pruebas
Pruebas manuales y automáticas recomendadas.
```

---

# Criterios para aceptar una mejora

Una mejora solo debe considerarse cerrada si:

* Resuelve el problema planteado.
* No rompe flujos existentes.
* Tiene mensajes de error claros.
* Está validada manualmente.
* Tiene tests si la lógica lo justifica.
* Está documentada si afecta al uso o arquitectura.

---

# Criterios para rechazar una mejora

Debe rechazarse o aplazarse una mejora si:

* Complica demasiado la aplicación.
* Duplica funcionalidad existente.
* Introduce dependencia externa innecesaria.
* Reduce privacidad.
* Rompe compatibilidad multiplataforma.
* No tiene un caso de uso claro.
* Aumenta el mantenimiento sin aportar valor suficiente.

---

# Convenciones de código

Recomendaciones generales:

* Nombres claros.
* Funciones pequeñas.
* Separación entre UI y lógica.
* Validaciones explícitas.
* Excepciones específicas.
* Comentarios solo cuando aporten contexto real.
* Evitar código muerto.
* Evitar refactors no solicitados.

---

# Política de commits

Los commits deben ser pequeños y descriptivos.

Formato recomendado:

```txt
feat: añade renombrado masivo por lista TXT
fix: corrige detección de Chrome en macOS
refactor: separa lógica de validación de archivos
test: añade tests para limpieza de nombres
docs: actualiza arquitectura del proyecto
```

---

# Filosofía técnica

DocFlow debe evolucionar como una herramienta profesional, no como una colección desordenada de scripts.

Cada cambio debe acercar el proyecto a estos objetivos:

* Más estabilidad.
* Mejor privacidad.
* Mejor experiencia de usuario.
* Menor deuda técnica.
* Mayor facilidad de mantenimiento.
