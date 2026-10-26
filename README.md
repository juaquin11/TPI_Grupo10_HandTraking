# 🖐️ HandTracking — Control del Cursor con la Mano

<div align="center">

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-Tasks%20v1.0%2B-00A67E?style=for-the-badge&logo=google&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.0%2B-1f6aa5?style=for-the-badge&logo=python&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![Architecture](https://img.shields.io/badge/Arquitectura-3%20Capas-blue?style=for-the-badge)

**Control inteligente y ergonómico del cursor del sistema operativo mediante visión artificial en tiempo real y reconocimiento de gestos.**

[Características](#-características-principales) • [Tabla de Gestos](#-esquema-de-gestos) • [Instalación](#-instalación-y-puesta-en-marcha) • [Arquitectura](#-arquitectura-del-sistema) • [Estructura](#-estructura-del-proyecto) • [Modo de Uso](#-controles-y-modo-de-uso)

</div>

---

## 📖 Descripción del Proyecto

**HandTracking** es una aplicación de escritorio desarrollada para el **Trabajo Práctico Integrador (TPI)**. Permite controlar el mouse de la computadora mediante gestos manuales capturados a través de cualquier webcam estándar, eliminando la necesidad de hardware costoso o sensores dedicados.

El sistema fue diseñado priorizando la **estabilidad**, la **ergonomía**, la **resiliencia** y la **baja latencia**, minimizando el efecto de fatiga de brazo (*Gorilla Arm Effect*) gracias al cálculo del cursor por centro de palma, mapeo de zonas activas y suavizado exponencial.

---

## ✨ Características Principales

- 🎯 **Rastreo por Centro de Palma:** La posición del cursor se calcula a partir del centro biomecánico de la palma (promedio de 5 articulaciones clave), garantizando que el cursor **no tiemble ni se desplace al flexionar los dedos o hacer clics**.
- 🧹 **Filtro de Suavizado Exponencial (EMA):** Elimina el temblor involuntario de la mano (*jitter*), logrando un movimiento suave y de alta precisión.
- 📐 **Zona Activa Ajustable (Bounding Box):** Permite recorrer toda la pantalla con movimientos cómodos y compactos de la mano, evitando la fatiga física.
- 🤖 **Drag & Drop Robusto con FSM:** Máquina de Estados Finita dedicada (`DragStateMachine`) con confirmación temporal de agarre, supresión de falsos clics y tolerancia ante oclusiones breves de la mano.
- 🪄 **Asistente de Calibración Guiado (Wizard):** Ventana interactiva en 3 pasos que guía al usuario para ajustar el área de movimiento, la sensibilidad y el suavizado con previsualización en vivo.
- 🪟 **Modo Picture-in-Picture (PiP) Automático:** Al minimizar el Dashboard principal, se despliega de forma automática una ventana flotante (*always-on-top*) y arrastrable para seguir viendo la cámara sin interferir con tu trabajo.
- 🛡️ **Resiliencia y Auto-Recuperación de Cámara:** Bucle de captura protegido contra fallos y desconexiones temporales, intentando reconectar el dispositivo automáticamente sin interrumpir la aplicación.
- ⌨️ **Atajo Global de Pausa (`Ctrl + Alt + H`):** Congela o reactiva el control del mouse al instante desde cualquier aplicación.
- 🎛️ **Soporte para Zurdos y Mapeo Completo:** Opción de inversión de eje horizontal para personas zurdas y personalización completa de las acciones asignadas a cada gesto.
- 💾 **Persistencia de Calibración:** Perfiles de usuario y configuración guardados de manera transparente en base de datos local **SQLite** mediante **SQLAlchemy ORM**.
- 🚀 **Descarga Automática de Modelos:** El modelo de visión artificial de MediaPipe (`hand_landmarker.task`) se descarga y configura automáticamente en la primera ejecución.

---

## ✋ Esquema de Gestos

| Gesto | Configuración de la Mano | Acción en el Sistema |
| :--- | :--- | :--- |
| 🖐️ **MANO_ABIERTA** | Mano extendida / relajada | **Mover Cursor** (rastreo de palma) |
| 🤏 **PELLIZCO_INDICE** | Juntar punta de Pulgar + Índice | **Clic Izquierdo** |
| 🤏 **PELLIZCO_MEDIO** | Juntar punta de Pulgar + Medio | **Clic Derecho** |
| 🤌 **PELLIZCO_TRIPLE** | Juntar Pulgar + Índice + Medio | **Drag & Drop** (Sostener + Arrastrar + Soltar) |
| ✌️ **DOS_DEDOS** | Índice + Medio levantados juntos | **Scroll Vertical** (arriba / abajo) |

---

## 🏗️ Arquitectura del Sistema

El proyecto implementa una **Arquitectura en 3 Capas** estricta, desacoplada y mantenible:

```
┌──────────────────────────────────────────────────────────┐
│             CAPA DE PRESENTACIÓN (views/)                │
│  ├── dashboard.py          → Panel de control principal  │
│  ├── calibracion_wizard.py → Asistente guiado de 3 pasos │
│  └── pip_window.py         → Widget flotante PiP         │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────┐
│              CAPA DE NEGOCIO (controller/)               │
│  ├── captura.py    → Video, resiliencia & MediaPipe      │
│  ├── suavizado.py  → Filtro EMA anti-temblor             │
│  ├── gestos.py     → Detección articular y centro palma  │
│  ├── fsm_drag.py   → Máquina de Estados de Drag & Drop   │
│  ├── acciones.py   → Inyección de eventos OS (pynput)    │
│  └── motor.py      → Orquestador central y colas de UI   │
└────────────────────────────┬─────────────────────────────┘
                             │ (Únicamente vía repositorio)
                             ▼
┌──────────────────────────────────────────────────────────┐
│                 CAPA DE DATOS (datos/)                   │
│  ├── conexion.py   → Sesión y Engine SQLite              │
│  ├── modelos.py    → Entidades ORM SQLAlchemy            │
│  └── repositorio.py→ CRUD y Perfiles de Calibración      │
└──────────────────────────────────────────────────────────┘
```

---

## 📁 Estructura del Proyecto

```text
TPI-HandTracking/
├── app.py                      # Punto de entrada principal
├── requirements.txt            # Dependencias del proyecto
├── README.md                   # Documentación principal
├── PROYECTO.md                 # Enunciado y requerimientos del TPI
├── checklist_capas.md          # Checklist de arquitectura en 3 capas
├── checklist_general.md        # Pautas generales de desarrollo
│
├── controller/                 # Capa de Negocio
│   ├── captura.py              # Captura OpenCV, resiliencia y MediaPipe Tasks
│   ├── suavizado.py            # Filtro exponencial (EMA)
│   ├── gestos.py               # Reconocimiento de gestos y centro de palma
│   ├── fsm_drag.py             # Máquina de Estados Finita (Drag & Drop)
│   ├── acciones.py             # Controlador de mouse del SO (pynput)
│   └── motor.py                # Pipeline orquestador, colas seguras y reconexión
│
├── datos/                      # Capa de Datos
│   ├── conexion.py             # Configuración SQLite y sesión SQLAlchemy
│   ├── modelos.py              # Modelos ORM (PerfilCalibracion, ConfiguracionGesto)
│   └── repositorio.py          # Consultas y operaciones de persistencia CRUD
│
├── views/                      # Capa de Presentación
│   ├── dashboard.py            # Panel de control principal (CustomTkinter)
│   ├── calibracion_wizard.py   # Asistente de calibración guiada en 3 pasos
│   └── pip_window.py           # Ventana flotante Picture-in-Picture (PiP)
│
└── models/                     # Modelos de Machine Learning (descarga automática)
    └── hand_landmarker.task
```

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el Repositorio
```bash
git clone https://github.com/juaquin11/TPI_Grupo10_HandTraking.git
cd TPI_Grupo10_HandTraking
```

### 2. Crear y Activar un Entorno Virtual (Recomendado)
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Ejecutar la Aplicación
```bash
python app.py
```

> **Nota:** En la primera ejecución, el sistema descargará de forma automática el modelo de MediaPipe (`hand_landmarker.task`) y creará la base de datos local SQLite (`handtracking.db`) con las configuraciones por defecto.

---

## 🎮 Controles y Modo de Uso

- **Panel de Control (Dashboard):**
  - **Iniciar / Detener Tracking:** Inicia o finaliza el hilo de captura y seguimiento.
  - **Asistente de Calibración:** Despliega el wizard de 3 pasos para ajustar visualmente la zona activa, sensibilidad y nivel de suavizado en vivo.
  - **Guardar Perfil:** Almacena los ajustes actuales en la base de datos para futuras sesiones.
- **Atajo Global de Pausa:**
  - Presiona **`Ctrl + Alt + H`** en cualquier momento para alternar entre pausado y activo, ideal para cuando necesites usar el mouse físico sin interferencias.
- **Ventana Flotante (Picture-in-Picture):**
  - Al **minimizar** la ventana principal del Dashboard, aparecerá automáticamente una miniatura flotante sin bordes en la esquina de la pantalla.
  - Puedes **moverla** arrastrando con el botón izquierdo del ratón a cualquier posición.
  - Haz **doble clic** sobre la miniatura para restaurar el Dashboard completo al instante.
- **Detención Limpia:**
  - Cierra la ventana del Dashboard o presiona el botón Detener para liberar la cámara y cerrar los hilos de ejecución de manera controlada.

---

## 👥 Equipo de Desarrollo — Grupo 10

Trabajo Práctico Integrador desarrollado para la cátedra de **Soporte**.

---

<div align="center">
Desarrollado con ❤️ y Python por el <b>Grupo 10</b>
</div>