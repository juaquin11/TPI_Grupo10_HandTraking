# HandTracking

Este es un archivo que debe completarse con los datos utilizados en el TPI. Este archivo puede modificarse en el tiempo, no obstante siempre debe mantenerse en un estado consistente con el desarrollo.

**Importante:** Este archivo debe mantenerse en formato Markdown (.md) y sólo se tendrá en cuenta la versión disponible en GIT.

## Descripción del proyecto
### Alcance del Proyecto
El alcance de este proyecto comprende el diseño, desarrollo e implementación de una **aplicación de escritorio** capaz de traducir gestos manuales, capturados en tiempo real mediante la webcam de la propia computadora, en comandos de control del cursor del sistema operativo.

- **Módulo de Captura y Visión Artificial:** Componente responsable de capturar el flujo de video desde la webcam de la PC y ejecutar los algoritmos de visión artificial (MediaPipe Tasks) para extraer las coordenadas articulares de la mano en cada frame, incorporando tolerancia a fallos y reconexión automática ante caídas del dispositivo.

- **Módulo de Reconocimiento e Interpretación de Gestos:** Componente que analiza las coordenadas articulares extraídas relativas al centro biomecánico de la palma y las traduce a gestos predefinidos (mover cursor, clic izquierdo, clic derecho, scroll vertical, drag & drop), aplicando filtros exponenciales de suavizado (EMA) para eliminar el temblor natural de la mano y una Máquina de Estados Finita (FSM) para el control confiable de arrastre.

- **Módulo de Inyección de Eventos (Control del SO):** Componente que interactúa directamente con las APIs del sistema operativo mediante `pynput` para inyectar eventos de hardware correspondientes (desplazamiento del cursor, clic izquierdo, clic derecho, scroll y arrastre/soltado) a partir del gesto reconocido.

- **Interfaz de Administración y Visualización (Dashboard):** Interfaz gráfica de usuario desarrollada en `CustomTkinter` que permite:
  - Iniciar, pausar y detener el seguimiento gestual.
  - Previsualizar en tiempo real el flujo de video con superposición visual del bounding box y landmarks articulares.
  - Calibración interactiva mediante un **Asistente Guiado (Wizard)** en 3 pasos (área activa, sensibilidad y factor de suavizado).
  - Modo **Picture-in-Picture (PiP)** automático que despliega una ventana flotante y arrastrable cuando la aplicación se minimiza.
  - Pausa global inmediata mediante combinación de teclado (`Ctrl + Alt + H`).
  - Personalización y reasignación de gestos y persistencia de perfiles de usuario.

### Objetivos Específicos
- **Garantizar latencia mínima:** Procesar el video de la webcam y responder con el movimiento del cursor a una frecuencia de actualización de al menos 30 cuadros por segundo, asegurando que el movimiento se perciba en tiempo real.

- **Asegurar la usabilidad y ergonomía:** Aplicar principios de diseño ergonómico para corregir el temblor involuntario (filtro EMA), calcular el cursor desde el centro de la palma para estabilidad al hacer clics, y delimitar zonas activas reducidas (bounding box) para evitar la fatiga muscular (*Gorilla Arm Effect*).

- **Optimizar el uso de recursos locales:** Diseñar el pipeline de procesamiento (captura, detección, colas seguras e inyección de eventos) para que funcione de manera fluida en un equipo hogareño estándar sobre CPU, sin requerir aceleración GPU dedicada ni conexión a internet tras la descarga inicial.

- **Integración transparente con el Sistema Operativo:** Construir la aplicación desacoplada y multihilo para coexistir sin interferencias con periféricos físicos de entrada (mouse tradicional o touchpad), con capacidad de suspensión instantánea mediante hotkeys globales.

## Modelo de Dominio

[Link Draw.io](https://drive.google.com/file/d/1RaGK6FoMkQtqk2qnLgeMbdfWv-yt91gS/view?usp=sharing)

<img width="501" height="183" alt="image" src="https://github.com/user-attachments/assets/08cc51d7-dd4e-48e5-965c-2fa7d66f4d79" />


## Bosquejo de Arquitectura

[Link Bosquejo](https://mermaid.ai/app/projects/feba23e6-577e-492b-91c5-0af594166bfa/diagrams/162589bc-4361-42b8-8703-7db28afc7dd1/share/invite/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJkb2N1bWVudElEIjoiMTYyNTg5YmMtNDM2MS00MmI4LTg3MDMtN2RiMjhhZmM3ZGQxIiwiYWNjZXNzIjoiRWRpdCIsImlhdCI6MTc4NjQ3MDc5Nn0.NMtJru3iOJ_CGEEzumh_VjweilgGw-EIZxYiEI71GNc?entryPoint=share-modal).

## Requerimientos

Definir los requerimientos del sistema.

### Funcionales

- **RF01 - Captura de video:** El sistema debe capturar el flujo de video de la webcam de la PC en tiempo real.
- **RF02 - Detección de landmarks:** El sistema debe procesar cada frame con MediaPipe para extraer las coordenadas articulares de la mano del usuario.
- **RF03 - Suavizado de movimiento:** El sistema debe aplicar un filtro exponencial (EMA) a las coordenadas detectadas para reducir el temblor antes de interpretarlas.
- **RF04 - Reconocimiento de gestos:** El sistema debe interpretar la configuración de los landmarks suavizados para identificar gestos predefinidos (pellizco índice para clic izquierdo, pellizco medio para clic derecho, pellizco triple para drag & drop, mano abierta para mover cursor, dos dedos para scroll).
- **RF05 - Movimiento del cursor:** El sistema debe trasladar la posición relativa de la mano (basada en el centro biomecánico de la palma) a un movimiento proporcional del cursor en la pantalla.
- **RF06 - Ejecución de clics:** El sistema debe soportar clic izquierdo y clic derecho mediante gestos de pellizco específicos con tiempo de enfriamiento (cooldown) anti-rebote.
- **RF07 - Scroll:** El sistema debe permitir desplazamiento vertical continuo (scroll) proporcional al movimiento vertical de la mano con dos dedos levantados.
- **RF08 - Drag & drop:** El sistema debe soportar arrastrar y soltar elementos mediante una Máquina de Estados Finita (FSM) con confirmación temporal de agarre y soltado.
- **RF09 - Calibración de zona activa:** El usuario debe poder definir el área relativa (bounding box) dentro de la cual el movimiento de la mano cubre el 100% de la pantalla del monitor.
- **RF10 - Ajuste de suavizado:** El usuario debe poder calibrar el factor alfa de suavizado para balancear entre estabilidad (anti-temblor) y velocidad de respuesta.
- **RF11 - Reasignación de gestos:** El usuario debe poder reasignar qué acción del sistema dispara cada gesto reconocido y habilitar/deshabilitar gestos individuales.
- **RF12 - Persistencia de configuración:** El sistema debe guardar el perfil de calibración del usuario (bounding box, suavizado, modo zurdo, mapeo de gestos) en SQLite mediante SQLAlchemy ORM.
- **RF13 - Convivencia con periféricos físicos:** El sistema debe permitir el uso simultáneo y alternado del mouse o touchpad físico sin bloqueos.
- **RF14 - Inicio/detención del servicio:** El usuario debe poder iniciar y detener el tracking en cualquier momento desde la interfaz.
- **RF15 - Asistente de calibración guiada (Wizard):** El sistema debe proveer una ventana guiada interactiva de 3 pasos que guíe al usuario en la configuración del bounding box, la sensibilidad y el suavizado con preview en vivo.
- **RF16 - Modo Picture-in-Picture (PiP) flotante:** El sistema debe activar automáticamente una ventana compacta, flotante (always on top) y arrastrable al minimizar la interfaz principal, permitiendo monitorear la cámara sin estorbar otras tareas.
- **RF17 - Atajo global de pausa:** El usuario debe poder pausar o reanudar el control gestual de forma inmediata mediante el atajo de teclado global `Ctrl + Alt + H`.
- **RF18 - Soporte para personas zurdas:** El sistema debe permitir invertir el eje horizontal para adaptar el seguimiento a usuarios zurdos.
- **RF19 - Auto-descarga de modelos:** El sistema debe verificar y descargar automáticamente el archivo binario del modelo de MediaPipe (`hand_landmarker.task`) si no se encuentra presente al iniciar la aplicación.

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

- El sistema debe diseñarse con la arquitectura en 3 capas estricta (Presentación, Negocio, Datos). (Ver [checklist_capas.md](checklist_capas.md))
- El sistema debe utilizar control de versiones mediante GIT.
- El sistema debe estar programado en Python 3.8 o superior.
- Cada capa debe comunicarse únicamente con su capa adyacente inmediata mediante interfaces definidas (repositorio para datos, motor/controlador para negocio).

### Reliability

**Obligatorios**

- **Tolerancia a fallos de cámara:** El motor debe capturar excepciones en la lectura de frames y ejecutar un ciclo de auto-recuperación y reconexión automática sin abortar la ejecución del programa.
- **Concurrencia desacoplada:** El pipeline de visión por computadora debe ejecutarse en un hilo secundario (`threading.Thread`) y enviar los frames procesados a la UI a través de una cola segura (`queue.Queue`), evitando bloqueos o congelamiento (*freezing*) de la interfaz gráfica.
- **Robustez en Drag & Drop:** El estado de arrastre debe ser gestionado por una Máquina de Estados Finita (FSM) con histéresis de frames para evitar soltados involuntarios ante oclusiones o pérdidas momentáneas de detección.

### Scalability

**Obligatorios**

- El sistema debe funcionar desde una ventana normal y una de incógnito de manera independiente (Sólo Web).
  - Aclaración: No se debe guardar el usuario en una variable local, deben usarse Tokens, Cookies o similares.

### Performance

**Obligatorios**

- El sistema debe funcionar de forma fluida en un equipo hogareño estándar con webcam convencional, manteniendo una tasa de procesamiento de al menos 30 FPS y latencia imperceptible sin necesidad de placa gráfica dedicada (GPU).
- Las operaciones sobre la base de datos se deben despachar de manera asíncrona mediante un pool de hilos (`ThreadPoolExecutor`) en la interfaz para no interrumpir el refresco de pantalla.

### Reusability

- Los módulos de suavizado matemático (`FiltroEMA`), control de periféricos (`ControladorMouse`) y lógica de transiciones (`DragStateMachine`) están completamente desacoplados de la GUI y pueden reutilizarse en otros proyectos o interfaces.

### Flexibility

**Obligatorios**

- El sistema debe utilizar una base de datos SQL o NoSQL (implementado mediante SQLite + SQLAlchemy ORM).

## Stack Tecnológico

Definir que tecnologías se van a utilizar en cada capa y una breve descripción sobre por qué se escogió esa tecnologia.

### Capa de Datos

- **Base de datos:** SQLite.
  - *Por qué:* Al ser una aplicación de escritorio mono-usuario que corre localmente, no se requiere un motor cliente-servidor externo. SQLite no requiere instalación de servicios adicionales, cumple con el requisito de base de datos SQL y almacena la configuración y perfiles en un archivo único y portable (`handtracking.db`).
- **ORM:** SQLAlchemy (v2.0+).
  - *Por qué:* Es el estándar de la industria en Python. Proporciona mapeo objeto-relacional limpio, consultas seguras y desacopla la lógica de negocio de la sintaxis SQL específica, facilitando futuras migraciones si fuera necesario.

### Capa de Negocio

- **MediaPipe Tasks (Google):** Para la detección y seguimiento articular de la mano (21 landmarks tridimensionales) en tiempo real con alta eficiencia sobre CPU.
- **OpenCV:** Para la captura de video desde la cámara web, preprocesamiento de imágenes, conversiones de color y dibujo de guías visuales sobre los frames.
- **NumPy:** Para cálculos vectoriales y distancias euclidianas entre articulaciones.
- **pynput:** Para la inyección precisa de eventos de cursor, clics del mouse y desplazamientos de rueda de scroll hacia el sistema operativo anfitrión.
- **FSM dedicada (`DragStateMachine`):** Para resolver la ambigüedad y evitar rebotes en el gesto sostenido de Drag & Drop.
- **Python Threading & Queue:** Para ejecutar el pipeline de tracking en segundo plano y transmitir información a la interfaz de forma segura entre hilos.

### Capa de Presentación

- **CustomTkinter:** Framework moderno de interfaz gráfica para Python basado en Tkinter.
  - *Por qué:* Permite crear una interfaz moderna, limpia, con estética actual y soporte nativo de modo oscuro, cumpliendo estrictamente con el requerimiento de ejecutarse desde un único script (`app.py`) sin necesidad de navegador web ni de instalar pesados entornos C++ como PyQt. Soporta de forma nativa ventanas secundarias de alto nivel (`CTkToplevel`) utilizadas para el Asistente de Calibración guiado y la mini-ventana flotante Picture-in-Picture (PiP).
- **Pillow (PIL):** Para la conversión y renderizado en tiempo real de los cuadros de video procesados por OpenCV en componentes visuales de CustomTkinter.
- **Keyboard:** Para el registro del atajo de teclado global del sistema (`Ctrl+Alt+H`) que permite pausar y reanudar el tracking incluso cuando la ventana de la aplicación no tiene el foco activo.
