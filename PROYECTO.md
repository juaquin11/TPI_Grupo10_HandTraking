# HandTracking

Este es un archivo que debe completarse con los datos utilizados en el TPI. Este archivo puede modificarse en el tiempo, no obstante siempre debe mantenerse en un estado consistente con el desarrollo.

**Importante:** Este archivo debe mantenerse en formato Markdown (.md) y sólo se tendrá en cuenta la versión disponible en GIT.

## Descripción del proyecto
### Alcance del Proyecto
El alcance de este proyecto comprende el diseño, desarrollo e implementación de un sistema cliente-servidor en red local capaz de traducir gestos manuales en comandos de control del cursor del sistema operativo en tiempo real.

-Módulo Cliente (Edge Processing): Una aplicación móvil responsable de capturar el flujo de video y ejecutar los algoritmos de visión artificial (MediaPipe) de forma local. Su función es extraer las coordenadas articulares y traducirlas a datos lógicos de interacción sin enviar video por la red.

-Módulo de Comunicación de Datos: Un protocolo de transmisión de baja latencia (basado en sockets UDP o WebSockets) para enviar los paquetes de datos de control desde el dispositivo móvil hacia la computadora anfitriona a través de una red Wi-Fi local.

-Módulo Servidor (Daemon/Servicio): Un proceso en segundo plano en la PC anfitriona que interpreta los paquetes de red entrantes e interactúa directamente con las APIs del sistema operativo para inyectar eventos de hardware (desplazamiento del cursor, clic izquierdo, clic derecho, scroll y drag & drop).

-Interfaz de Administración (Dashboard): Una interfaz gráfica orientada al usuario para calibrar la zona activa de movimiento (bounding box), ajustar parámetros de suavizado (filtros matemáticos para evitar el temblor) y reasignar atajos de gestos.

### Objetivos Específicos
-Desacoplar la carga computacional: Implementar el procesamiento de imágenes mediante redes neuronales en el dispositivo cliente, liberando a la computadora anfitriona del consumo intensivo de CPU/GPU asociado al procesamiento de video.

-Garantizar latencia mínima: Establecer un canal de comunicación de datos eficiente que permita una frecuencia de actualización de al menos 30 cuadros por segundo, asegurando que el movimiento del cursor se perciba en tiempo real.

-Asegurar la usabilidad y ergonomía: Aplicar principios de Design Thinking para diseñar mecanismos de corrección de temblor (filtros exponenciales) y áreas de movimiento relativas, minimizando la fatiga física del usuario (Gorilla Arm Effect).

-Integración transparente con el Sistema Operativo: Construir el servicio receptor de manera que coexista sin interferencias con otros dispositivos de entrada físicos (mouse tradicional o trackpad), gestionando correctamente los permisos y llamadas al sistema.

## Modelo de Dominio

Insertar el modelo de dominio aquí.

## Bosquejo de Arquitectura

Definir la arquitectura del sistema y como interactuan sus diferentes componentes. Utilizar el Paquete **Office** de Draw.io o similar. [Ejemplo Online]().

## Requerimientos

Definir los requerimientos del sistema.

### Funcionales

Listado y descripción breve de los requerimientos funcionales.

### No Funcionales

Listado y descripción breve de los requerimientos no funcionales. Utilizar las categorias dadas:

### Portability

**Obligatorios**

- El sistema debe funcionar correctamente en múltiples navegadores (Sólo Web).
- El sistema debe ejecutarse desde un único archivo .py llamado app.py (Sólo Escritorio).

### Security

**Obligatorios**

- Todas las contraseñas deben guardarse con encriptado criptográfico (SHA o equivalente).
- Todas los Tokens / API Keys o similares no deben exponerse de manera pública.

### Maintainability

**Obligatorios**

- El sistema debe diseñarse con la arquitectura en 3 capas. (Ver [checklist_capas.md](checklist_capas.md))
- El sistema debe utilizar control de versiones mediante GIT.
- El sistema debe estar programado en Python 3.8 o superior.

### Reliability

### Scalability

**Obligatorios**

- El sistema debe funcionar desde una ventana normal y una de incógnito de manera independiente (Sólo Web).
  - Aclaración: No se debe guardar el usuario en una variable local, deben usarse Tokens, Cookies o similares.

### Performance

**Obligatorios**

- El sistema debe funcionar en un equipo hogareño estándar.

### Reusability

### Flexibility

**Obligatorios**

- El sistema debe utilizar una base de datos SQL o NoSQL

## Stack Tecnológico

Definir que tecnologías se van a utilizar en cada capa y una breve descripción sobre por qué se escogió esa tecnologia.

### Capa de Datos

Definir que base de datos, ORM y tecnologías se utilizaron y por qué.

### Capa de Negocio

Definir que librerías e integraciones con terceros se utilizaron y por qué. En caso de consumir APIs, definir cúales se usaron.

### Capa de Presentación

Definir que framework se utilizó y por qué.
