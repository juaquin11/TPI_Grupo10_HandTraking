# HandTracking

Este es un archivo que debe completarse con los datos utilizados en el TPI. Este archivo puede modificarse en el tiempo, no obstante siempre debe mantenerse en un estado consistente con el desarrollo.

**Importante:** Este archivo debe mantenerse en formato Markdown (.md) y sólo se tendrá en cuenta la versión disponible en GIT.

## Descripción del proyecto
### Alcance del Proyecto
El alcance de este proyecto comprende el diseño, desarrollo e implementación de una **aplicación de escritorio** capaz de traducir gestos manuales, capturados en tiempo real mediante la webcam de la propia computadora, en comandos de control del cursor del sistema operativo.

- **Módulo de Captura y Visión Artificial:** Componente responsable de capturar el flujo de video desde la webcam de la PC y ejecutar los algoritmos de visión artificial (MediaPipe) para extraer las coordenadas articulares de la mano en cada frame.

- **Módulo de Reconocimiento e Interpretación de Gestos:** Componente que analiza las coordenadas articulares extraídas y las traduce a gestos predefinidos (mover, clic izquierdo, clic derecho, scroll, drag & drop), aplicando además filtros de suavizado para reducir el temblor natural de la mano.

- **Módulo de Inyección de Eventos (Control del SO):** Componente que interactúa directamente con las APIs del sistema operativo para inyectar los eventos de hardware correspondientes (desplazamiento del cursor, clic izquierdo, clic derecho, scroll y drag & drop) a partir del gesto reconocido.

- **Interfaz de Administración (Dashboard):** Interfaz gráfica de la aplicación orientada al usuario, para calibrar la zona activa de movimiento (bounding box), ajustar parámetros de suavizado (filtros matemáticos para evitar el temblor) y reasignar atajos de gestos.

### Objetivos Específicos
- **Garantizar latencia mínima:** Procesar el video de la webcam y responder con el movimiento del cursor a una frecuencia de actualización de al menos 30 cuadros por segundo, asegurando que el movimiento se perciba en tiempo real.

- **Asegurar la usabilidad y ergonomía:** Aplicar principios de Design Thinking para diseñar mecanismos de corrección de temblor (filtros exponenciales) y áreas de movimiento relativas, minimizando la fatiga física del usuario (Gorilla Arm Effect).

- **Optimizar el uso de recursos locales:** Diseñar el pipeline de procesamiento (captura, detección e inyección de eventos) para que funcione de manera fluida en un equipo hogareño estándar, sin depender de hardware externo ni de conexión a red.

- **Integración transparente con el Sistema Operativo:** Construir la aplicación de manera que coexista sin interferencias con otros dispositivos de entrada físicos (mouse tradicional o trackpad), gestionando correctamente los permisos y llamadas al sistema.

## Modelo de Dominio

[Link Draw.io](https://drive.google.com/file/d/1RaGK6FoMkQtqk2qnLgeMbdfWv-yt91gS/view?usp=sharing)

## Bosquejo de Arquitectura

[Link Bosquejo](https://mermaid.ai/app/projects/feba23e6-577e-492b-91c5-0af594166bfa/diagrams/162589bc-4361-42b8-8703-7db28afc7dd1/share/invite/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb2N1bWVudElEIjoiMTYyNTg5YmMtNDM2MS00MmI4LTg3MDMtN2RiMjhhZmM3ZGQxIiwiYWNjZXNzIjoiRWRpdCIsImlhdCI6MTc4NjQ3MDc5Nn0.NMtJru3iOJ_CGEEzumh_VjweilgGw-EIZxYiEI71GNc?entryPoint=share-modal).

## Requerimientos

Definir los requerimientos del sistema.

### Funcionales

- **RF01 - Captura de video:** El sistema debe capturar el flujo de video de la webcam de la PC en tiempo real.
- **RF02 - Detección de landmarks:** El sistema debe procesar cada frame con MediaPipe para extraer las coordenadas articulares de la mano del usuario.
- **RF03 - Suavizado de movimiento:** El sistema debe aplicar un filtro (exponencial o similar) a las coordenadas detectadas para reducir el temblor antes de interpretarlas.
- **RF04 - Reconocimiento de gestos:** El sistema debe interpretar la configuración de los landmarks suavizados para identificar gestos predefinidos (ej. pellizco para clic, mano abierta para mover cursor, dos dedos para scroll).
- **RF05 - Movimiento del cursor:** El sistema debe trasladar la posición relativa de la mano a un movimiento proporcional del cursor en la pantalla.
- **RF06 - Ejecución de clics:** El sistema debe soportar clic izquierdo y clic derecho mediante gestos específicos.
- **RF07 - Scroll:** El sistema debe permitir desplazamiento vertical (scroll) mediante un gesto dedicado.
- **RF08 - Drag & drop:** El sistema debe soportar la funcionalidad de arrastrar y soltar elementos mediante una combinación de gestos (sostener + mover + soltar).
- **RF09 - Calibración de zona activa:** El usuario debe poder definir, a través del dashboard, el área (bounding box) dentro del cual el movimiento de la mano se traduce a movimiento del cursor.
- **RF10 - Ajuste de suavizado:** El usuario debe poder ajustar, desde el dashboard, el nivel de filtrado aplicado al movimiento para reducir el temblor.
- **RF11 - Reasignación de gestos:** El usuario debe poder reasignar qué acción del sistema dispara cada gesto reconocido.
- **RF12 - Persistencia de configuración:** El sistema debe guardar el perfil de calibración del usuario (bounding box, suavizado, mapeo de gestos) para reutilizarlo en sesiones futuras.
- **RF13 - Convivencia con periféricos físicos:** El sistema debe permitir el uso simultáneo del mouse/trackpad físico sin conflictos ni bloqueos.
- **RF14 - Inicio/detención del servicio:** El usuario debe poder iniciar y detener el tracking desde la interfaz de la aplicación.

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

- **Base de datos:** SQLite.
  - *Por qué:* al ser una aplicación de escritorio mono-usuario que corre localmente, no se necesita un motor cliente-servidor como PostgreSQL o MySQL. SQLite no requiere instalación ni proceso adicional, cumple el requisito de "base de datos SQL o NoSQL" y es ideal para persistir perfiles de calibración, historial de sesiones y configuración de usuario en un único archivo portable.
- **ORM:** SQLAlchemy.
  - *Por qué:* es el ORM estándar de facto en Python, permite abstraer las consultas SQL, facilita el mantenimiento (arquitectura en 3 capas) y sería sencillo migrar a otro motor de base de datos en el futuro si fuera necesario.
  - 
### Capa de Negocio

- **MediaPipe (Google):** para la detección de landmarks de la mano a partir del video de la webcam. Es la librería de referencia para tracking de manos en tiempo real, con buen rendimiento en CPU y sin necesidad de hardware especializado.
- **OpenCV:** para la captura y preprocesamiento del flujo de video de la webcam antes de pasarlo a MediaPipe.
- **NumPy:** para las operaciones matemáticas del filtro de suavizado (filtro exponencial / Kalman) que corrige el temblor de la mano.
- **PyAutoGUI / pynput:** para la inyección de eventos de hardware (movimiento de cursor, clics, scroll, drag & drop) hacia el sistema operativo.

### Capa de Presentación

- **Dashboard de administración:** se propone construirlo con un framework liviano tipo **Tkinter** (incluido en la librería estándar de Python) o **PyQt/PySide** si se requiere una interfaz más rica.
  - *Por qué:* dado que el requisito no funcional obliga a que el sistema corra como un único archivo `app.py` sin depender de un navegador, se descarta un framework web (React, Vue, etc.) para la interfaz de escritorio, priorizando una librería nativa de Python que minimice dependencias externas y facilite el empaquetado final (ej. con PyInstaller).
